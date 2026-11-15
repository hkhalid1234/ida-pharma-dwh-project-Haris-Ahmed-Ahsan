"""Transformation & dimensional modelling layer (staging -> star schema / fact constellation).

Implements the design of the Excel workbook:
  * DimDate (generated), DimLocation (outrigger shared by pharmacy & hospital)
  * DimMedicine / DimPharmacy / DimHospital with SCD Type 1 + Type 2 columns
  * DimSalesJunk / DimDemandJunk (junk dimensions)
  * DimDate role-playing (SalesDate + DeliveryDate keys on the same fact)
  * FactPharmacySales (transactional) and FactHospitalDemand (periodic snapshot)
Loads are incremental and idempotent: facts are append-only, dimensions keep their surrogate keys.
"""
import pandas as pd

from . import config
from .ingestion import now
from .validation import clean_batch

OPEN_END = "9999-12-31"
NEVER = "N/A"

STATE_INFO = {  # code: (name, region)
    "AL": ("Alabama", "South"), "AK": ("Alaska", "West"), "AZ": ("Arizona", "West"), "AR": ("Arkansas", "South"),
    "CA": ("California", "West"), "CO": ("Colorado", "West"), "CT": ("Connecticut", "Northeast"),
    "DE": ("Delaware", "South"), "DC": ("District of Columbia", "South"), "FL": ("Florida", "South"),
    "GA": ("Georgia", "South"), "HI": ("Hawaii", "West"), "ID": ("Idaho", "West"), "IL": ("Illinois", "Midwest"),
    "IN": ("Indiana", "Midwest"), "IA": ("Iowa", "Midwest"), "KS": ("Kansas", "Midwest"), "KY": ("Kentucky", "South"),
    "LA": ("Louisiana", "South"), "ME": ("Maine", "Northeast"), "MD": ("Maryland", "South"),
    "MA": ("Massachusetts", "Northeast"), "MI": ("Michigan", "Midwest"), "MN": ("Minnesota", "Midwest"),
    "MS": ("Mississippi", "South"), "MO": ("Missouri", "Midwest"), "MT": ("Montana", "West"),
    "NE": ("Nebraska", "Midwest"), "NV": ("Nevada", "West"), "NH": ("New Hampshire", "Northeast"),
    "NJ": ("New Jersey", "Northeast"), "NM": ("New Mexico", "West"), "NY": ("New York", "Northeast"),
    "NC": ("North Carolina", "South"), "ND": ("North Dakota", "Midwest"), "OH": ("Ohio", "Midwest"),
    "OK": ("Oklahoma", "South"), "OR": ("Oregon", "West"), "PA": ("Pennsylvania", "Northeast"),
    "RI": ("Rhode Island", "Northeast"), "SC": ("South Carolina", "South"), "SD": ("South Dakota", "Midwest"),
    "TN": ("Tennessee", "South"), "TX": ("Texas", "South"), "UT": ("Utah", "West"), "VT": ("Vermont", "Northeast"),
    "VA": ("Virginia", "South"), "WA": ("Washington", "West"), "WV": ("West Virginia", "South"),
    "WI": ("Wisconsin", "Midwest"), "WY": ("Wyoming", "West"),
}
DOSE_CODES = {"tablet": "TAB", "capsule": "CAP", "solution for injection": "INJ", "oral solution": "SOL"}
TRUE_SET = {"Y", "YES", "TRUE", "1", "T"}


# ----------------------------------------------------------------- helpers
def _s(x: pd.Series) -> pd.Series:
    return x.astype("string").str.strip()


def _iso(x: pd.Series) -> pd.Series:
    return pd.to_datetime(x, format="mixed", errors="coerce").dt.strftime("%Y-%m-%d")


def _datekey(iso: pd.Series) -> pd.Series:
    return iso.str.replace("-", "", regex=False).astype("Int64")


def _truthy(x: pd.Series) -> pd.Series:
    return _s(x).str.upper().isin(TRUE_SET)


def _gln(df: pd.DataFrame, col: str) -> pd.Series:
    """13-digit GLN kept as text (leading zero). Values mangled by Excel (9.506E+11) become NULL."""
    if col not in df:
        return pd.Series([None] * len(df), index=df.index, dtype="object")
    v = _s(df[col])
    ok = v.str.fullmatch(r"\d{12,13}").fillna(False)
    return v.str.zfill(13).where(ok, None).astype("object")


def _next_key(dim: pd.DataFrame, key: str) -> int:
    return 1 if dim.empty else int(dim[key].max()) + 1


# ----------------------------------------------------------------- DimDate
def build_dim_date() -> pd.DataFrame:
    d = pd.DataFrame({"d": pd.date_range(config.DATE_DIM_START, config.DATE_DIM_END, freq="D")})
    season = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
              6: "Summer", 7: "Summer", 8: "Summer", 9: "Fall", 10: "Fall", 11: "Fall"}
    return pd.DataFrame({
        "DateKey": d.d.dt.strftime("%Y%m%d").astype(int), "FullDate": d.d.dt.strftime("%Y-%m-%d"),
        "Year": d.d.dt.year, "Quarter": "Q" + d.d.dt.quarter.astype(str), "MonthNumber": d.d.dt.month,
        "MonthName": d.d.dt.month_name(), "Day": d.d.dt.day, "DayName": d.d.dt.day_name(),
        "IsWeekend": (d.d.dt.dayofweek >= 5).map({True: "Y", False: "N"}), "Season": d.d.dt.month.map(season)})


# ----------------------------------------------------------------- generic SCD engine
def apply_scd(dim: pd.DataFrame, incoming: pd.DataFrame, nk: str, key: str,
              type1: list[str], type2: list[str], eff_new: pd.Series | str) -> tuple[pd.DataFrame, int]:
    """Return (updated full dimension, number of new versions inserted).
    Type 1 columns are overwritten on ALL versions of the member; any change in a Type 2 column closes the
    current version (EffectiveToDate = new effective date - 1 day) and inserts a new version with a new surrogate key.
    `eff_new` = effective-from date (ISO string, scalar or Series aligned with incoming) of versions created now."""
    incoming = incoming.drop_duplicates(nk, keep="last").reset_index(drop=True)
    if isinstance(eff_new, str):
        eff_new = pd.Series(eff_new, index=incoming.index)
    else:
        eff_new = eff_new.reset_index(drop=True)
    dim = dim.copy()
    cur = dim[dim["IsCurrent"] == "Y"].set_index(nk)
    inc = incoming.set_index(nk)
    existing_ids = inc.index.intersection(cur.index)
    new_ids = inc.index.difference(cur.index)

    # --- Type 1: overwrite in place on every version
    for c in type1:
        if len(existing_ids):
            newvals = inc.loc[existing_ids, c]
            dim.loc[dim[nk].isin(existing_ids), c] = dim.loc[dim[nk].isin(existing_ids), nk].map(newvals)

    # --- Type 2: detect changes on current rows
    changed = []
    for i in existing_ids:
        a = cur.loc[i, type2].astype(str).fillna("") if type2 else []
        b = inc.loc[i, type2].astype(str).fillna("") if type2 else []
        if type2 and list(a) != list(b):
            changed.append(i)
    eff_by_id = dict(zip(incoming[nk], eff_new))
    rows = []
    next_key = _next_key(dim, key)
    for i in changed:   # close old version, open new one
        end = (pd.Timestamp(eff_by_id[i]) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        mask = (dim[nk] == i) & (dim["IsCurrent"] == "Y")
        dim.loc[mask, ["EffectiveToDate", "IsCurrent"]] = [end, "N"]
        r = inc.loc[[i]].reset_index()
        r[key], r["EffectiveFromDate"], r["EffectiveToDate"], r["IsCurrent"] = next_key, eff_by_id[i], OPEN_END, "Y"
        rows.append(r); next_key += 1
    for i in new_ids:
        r = inc.loc[[i]].reset_index()
        r[key], r["EffectiveFromDate"], r["EffectiveToDate"], r["IsCurrent"] = next_key, eff_by_id[i], OPEN_END, "Y"
        rows.append(r); next_key += 1
    if rows:
        add = pd.concat(rows, ignore_index=True)[list(dim.columns)]
        dim = pd.concat([dim, add], ignore_index=True)
    return dim, len(rows)


def asof_lookup(fact: pd.DataFrame, dim: pd.DataFrame, nk: str, key: str, date_col: str) -> pd.Series:
    """Surrogate key of the dimension version valid on `date_col` (ISO strings compare lexicographically).
    Falls back to the earliest version when the fact pre-dates the first version. NaN = member unknown."""
    left = fact[[nk, date_col]].copy()
    left["_i"] = range(len(left))
    cand = left.merge(dim[[nk, key, "EffectiveFromDate", "EffectiveToDate"]], on=nk, how="inner")
    valid = cand[(cand[date_col] >= cand["EffectiveFromDate"]) & (cand[date_col] <= cand["EffectiveToDate"])]
    res = pd.Series(pd.NA, index=range(len(left)), dtype="Int64")
    res.loc[valid["_i"].values] = valid[key].values
    missing = cand[~cand["_i"].isin(valid["_i"])]
    if len(missing):
        first = missing.sort_values("EffectiveFromDate").drop_duplicates("_i", keep="first")
        res.loc[first["_i"].values] = first[key].values
    res.index = fact.index
    return res


# ----------------------------------------------------------------- dimension builders
def medicine_incoming(master: pd.DataFrame) -> pd.DataFrame:
    m = master.copy()
    form = _s(m["DosageForm"]).str.lower().map(DOSE_CODES).fillna(_s(m["DosageForm"]).str.upper().str[:3])
    out = pd.DataFrame({
        "MedicineID": _s(m["MedicineID"]), "InternalSKU": _s(m["InternalSKU"]),
        "GTIN14": _s(m["GTIN14"]).str.replace(r"\.0$", "", regex=True).str.zfill(14),
        "MedName": _s(m["GenericName"]).str.title(), "BrandName": _s(m["FictionalBrandName"]),
        "DiseaseCategory": _s(m["DiseaseCategory"]).str.title(), "ICD10Category": _s(m["ICD10Category"]).str.upper().str[:3],
        "TherapeuticClass": _s(m["TherapeuticClass"]).str.title(),
        "DoseFormStrength": (form.fillna("") + " " + _s(m["Strength"]).fillna("")).str.strip(),
        "Route": _s(m["RouteOfAdministration"]), "PackSize": pd.to_numeric(m["PackSize"], errors="coerce").astype("Int64"),
        "PrescriptionClass": _s(m["PrescriptionClass"]).replace({"OTC": "Over the counter"}),
        "ControlledFlag": _truthy(m["ControlledMedicineFlag"]).map({True: "Controlled", False: "Not controlled"}),
        "ColdStorageFlag": _truthy(m["ColdChainFlag"]).map({True: "Keep cold", False: "Room temp"}),
        "ProductStatus": _s(m["ProductStatus"])})
    out["_eff"] = _iso(m["EffectiveFromDate"]) if "EffectiveFromDate" in m else config.DATE_DIM_START
    return out


MED_T1 = ["InternalSKU", "GTIN14", "MedName", "BrandName", "ICD10Category", "DoseFormStrength", "Route", "ColdStorageFlag"]
MED_T2 = ["DiseaseCategory", "TherapeuticClass", "PackSize", "PrescriptionClass", "ControlledFlag", "ProductStatus"]


def upsert_locations(dim: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    p = pairs.dropna().drop_duplicates()
    p = pd.DataFrame({"City": _s(p["City"]).str.title(), "StateCode": _s(p["StateCode"]).str.upper()}).drop_duplicates()
    known = set(zip(dim["City"], dim["StateCode"]))
    p = p[[t not in known for t in zip(p["City"], p["StateCode"])]].reset_index(drop=True)
    if p.empty:
        return dim
    k0 = _next_key(dim, "LocationKey")
    p["LocationKey"] = range(k0, k0 + len(p))
    p["StateName"] = p["StateCode"].map(lambda c: STATE_INFO.get(c, ("Unknown", "Unknown"))[0])
    p["Region"] = p["StateCode"].map(lambda c: STATE_INFO.get(c, ("Unknown", "Unknown"))[1])
    p["Country"] = "United States"
    return pd.concat([dim, p[list(dim.columns)]], ignore_index=True)


def pharmacy_incoming(sales: pd.DataFrame, loc: pd.DataFrame) -> pd.DataFrame:
    latest = sales.sort_values("SalesDate").drop_duplicates("PharmacyID", keep="last")
    name = (_s(latest["PharmacyName"]).str.replace("Pharmacy", "Phcy", regex=False)
            .str.replace("Community", "Comm", regex=False))
    out = pd.DataFrame({
        "PharmacyID": _s(latest["PharmacyID"]), "PharmacyGLN": _gln(latest, "PharmacyGLN"),
        "PharmacyName": name, "PharmacyType": _s(latest["PharmacyType"]).str.replace(" Pharmacy", "", regex=False).str.strip(),
        "HospitalID": _s(latest["HospitalID"]).fillna(NEVER),
        "_city": _s(latest["PharmacyCity"]).str.title(), "_st": _s(latest["PharmacyState"]).str.upper()})
    out = out.merge(loc[["LocationKey", "City", "StateCode"]], left_on=["_city", "_st"], right_on=["City", "StateCode"], how="left")
    return out.drop(columns=["_city", "_st", "City", "StateCode"])


PH_T1 = ["PharmacyGLN", "PharmacyName", "HospitalID"]
PH_T2 = ["PharmacyType", "LocationKey"]


def hospital_incoming(hosp: pd.DataFrame, loc: pd.DataFrame) -> pd.DataFrame:
    latest = hosp.sort_values("DemandMonth").drop_duplicates("HospitalID", keep="last")
    beds = pd.to_numeric(latest["LicensedBeds"], errors="coerce")
    out = pd.DataFrame({
        "HospitalID": _s(latest["HospitalID"]), "HospitalGLN": _gln(latest, "HospitalGLN"),
        "HospitalName": _s(latest["HospitalName"]), "HospitalType": _s(latest["HospitalType"]),
        "HospitalPharmacyID": _s(latest["HospitalPharmacyID"]), "TraumaLevel": _s(latest["TraumaLevel"]).replace({"None": pd.NA, "": pd.NA}).fillna("Not rated"),
        "LicensedBeds": beds.astype("Int64"),
        "BedSizeBand": pd.cut(beds, [-1, 399, 700, 10**9], labels=["Small", "Medium", "Large"]).astype("string"),
        "ICUBeds": pd.to_numeric(latest["ICUBeds"], errors="coerce").astype("Int64"),
        "OccupancyPct": pd.to_numeric(latest["AverageOccupancyRatePct"], errors="coerce"),
        "CatchmentPopulation": pd.to_numeric(latest["CatchmentPopulation"], errors="coerce").astype("Int64"),
        "_city": _s(latest["City"]).str.title(), "_st": _s(latest["State"]).str.upper()})
    out = out.merge(loc[["LocationKey", "City", "StateCode"]], left_on=["_city", "_st"], right_on=["City", "StateCode"], how="left")
    return out.drop(columns=["_city", "_st", "City", "StateCode"])


HO_T1 = ["HospitalGLN", "HospitalName", "HospitalPharmacyID", "TraumaLevel", "LicensedBeds", "BedSizeBand", "ICUBeds",
         "OccupancyPct", "CatchmentPopulation"]
HO_T2 = ["HospitalType", "LocationKey"]


def sales_junk_frame(s: pd.DataFrame) -> pd.DataFrame:
    days = pd.to_numeric(s["DaysToExpiryAtSale"], errors="coerce")
    band = pd.cut(days, [-10**9, 179, 365, 10**9], labels=["Under 180 days", "180 to 365 days", "Over 365 days"]).astype("string")
    promo = _s(s["PromotionCode"]).fillna("No promo")
    promo = promo.where(~promo.str.lower().isin(["none", "", "nan"]), "No promo")
    chan = _s(s["SalesChannel"]).replace({"Physical Pharmacy": "In store", "Ecommerce": "Online"})
    return pd.DataFrame({
        "SalesChannel": chan, "CustomerSegment": _s(s["CustomerSegment"]).str.title(), "PayerType": _s(s["PayerType"]),
        "PaymentMethod": _s(s["PaymentMethod"]), "PromotionCode": promo,
        "RxRequired": _truthy(s["PrescriptionRequiredFlag"]).map({True: "Required", False: "Not required"}),
        "ReturnFlag": _truthy(s["ReturnFlag"]).map({True: "Returned", False: "Not returned"}),
        "SaleStatus": _s(s["SaleStatus"]), "OnlineDeliveryStatus": _s(s["EcommerceDeliveryStatus"]).fillna("N/A"),
        "ExpiryBand": band.fillna("Unknown")}, index=s.index)


def demand_junk_frame(h: pd.DataFrame) -> pd.DataFrame:
    ls = _s(h["FormularyStatus"]).replace({"Formulary": "On approved list", "Restricted": "Limited use",
                                           "Non-formulary exception": "Special approval"})
    return pd.DataFrame({"RequestStatus": _s(h["MedicationRequestStatus"]), "ListStatus": ls}, index=h.index)


def upsert_junk(dim: pd.DataFrame, key: str, combos: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in dim.columns if c != key]
    combos = combos[cols].fillna("N/A").drop_duplicates()
    if dim.empty:
        new = combos
    else:
        new = combos.merge(dim[cols], on=cols, how="left", indicator=True)
        new = new[new["_merge"] == "left_only"][cols]
    if new.empty:
        return dim
    k0 = _next_key(dim, key)
    new = new.copy(); new.insert(0, key, range(k0, k0 + len(new)))
    return pd.concat([dim, new], ignore_index=True)


def junk_lookup(frame: pd.DataFrame, dim: pd.DataFrame, key: str) -> pd.Series:
    cols = [c for c in dim.columns if c != key]
    f = frame[cols].fillna("N/A").copy()
    f["_i"] = range(len(f))
    m = f.merge(dim, on=cols, how="left").sort_values("_i")
    return pd.Series(m[key].values, index=frame.index, dtype="Int64")


# ----------------------------------------------------------------- orchestration
def _read_dim(wh, table: str, key: str) -> pd.DataFrame:
    """Read a dimension with DATE columns as ISO text (DuckDB's 9999-12-31 overflows pandas datetime64)."""
    cols = list(wh.query(f"SELECT * FROM {table} LIMIT 0").columns)
    sel = ", ".join(f"CAST({c} AS VARCHAR) AS {c}" if c in ("EffectiveFromDate", "EffectiveToDate") else c for c in cols)
    df = wh.query(f"SELECT {sel} FROM {table}")
    for c in ("EffectiveFromDate", "EffectiveToDate"):
        if c in df.columns:
            df[c] = df[c].astype("object").where(df[c].notna(), None)
            df[c] = df[c].map(lambda v: None if v is None else str(v)[:10])
    return df


def run_transform(db, wh, batch_id: str) -> dict:
    """Load one validated batch from staging into the star schema. Safe to re-run."""
    wh.ensure_schema()
    done = wh.query("SELECT COUNT(*) AS n FROM EtlBatchLog WHERE BatchID = ?", [batch_id])
    if int(done["n"][0]) > 0:
        return {"batch": batch_id, "skipped": True}
    wh.drop_indexes()   # ART/B-tree indexes are rebuilt by the query layer after the load

    master = clean_batch(db, "stg_master_data", batch_id)
    sales = clean_batch(db, "stg_pharmacy_sales", batch_id)
    hosp = clean_batch(db, "stg_hospital_demand", batch_id)

    # DimDate (static, extended to cover generated 2026 months)
    if not wh.table_exists_nonempty("DimDate"):
        wh.append("DimDate", build_dim_date())

    # DimLocation
    loc = _read_dim_plain(wh, "DimLocation")
    pairs = pd.concat([
        sales[["PharmacyCity", "PharmacyState"]].rename(columns={"PharmacyCity": "City", "PharmacyState": "StateCode"}) if len(sales) else None,
        hosp[["City", "State"]].rename(columns={"State": "StateCode"}) if len(hosp) else None], ignore_index=True)
    if pairs is not None and len(pairs):
        new_loc = upsert_locations(loc, pairs)
        if len(new_loc) != len(loc):
            wh.append("DimLocation", new_loc.iloc[len(loc):])
        loc = new_loc

    # DimMedicine (SCD 1 + 2)
    med_added = 0
    if len(master):
        inc = medicine_incoming(master)
        eff = inc.pop("_eff")
        dim = _read_dim(wh, "DimMedicine", "MedicineKey")
        first_load = dim.empty
        upd, med_added = apply_scd(dim, inc, "MedicineID", "MedicineKey", MED_T1, MED_T2,
                                   eff if first_load else eff.fillna(config.DATE_DIM_START))
        wh.replace("DimMedicine", upd)
    dim_med = _read_dim(wh, "DimMedicine", "MedicineKey")

    # DimPharmacy / DimHospital
    batch_start = config.DATE_DIM_START
    if len(sales) and batch_id != "INIT":
        batch_start = _iso(sales["SalesDate"]).min()
    if len(sales):
        dim = _read_dim(wh, "DimPharmacy", "PharmacyKey")
        upd, _ = apply_scd(dim, pharmacy_incoming(sales, loc), "PharmacyID", "PharmacyKey", PH_T1, PH_T2, batch_start)
        wh.replace("DimPharmacy", upd)
    if len(hosp):
        dim = _read_dim(wh, "DimHospital", "HospitalKey")
        hstart = config.DATE_DIM_START if batch_id == "INIT" else _iso(hosp["DemandMonth"]).min()
        upd, _ = apply_scd(dim, hospital_incoming(hosp, loc), "HospitalID", "HospitalKey", HO_T1, HO_T2, hstart)
        wh.replace("DimHospital", upd)
    dim_ph, dim_ho = _read_dim(wh, "DimPharmacy", "PharmacyKey"), _read_dim(wh, "DimHospital", "HospitalKey")

    # Junk dimensions
    orphan_s = orphan_h = loaded_s = loaded_h = 0
    if len(sales):
        sj = sales_junk_frame(sales)
        dj = wh.query("SELECT * FROM DimSalesJunk")
        newj = upsert_junk(dj, "SalesJunkKey", sj)
        if len(newj) != len(dj):
            wh.append("DimSalesJunk", newj.iloc[len(dj):])
        dj = wh.query("SELECT * FROM DimSalesJunk")
        loaded_s, orphan_s = _load_sales_fact(db, wh, sales, sj, dj, dim_med, dim_ph, batch_id)
    if len(hosp):
        hj = demand_junk_frame(hosp)
        dd = wh.query("SELECT * FROM DimDemandJunk")
        newd = upsert_junk(dd, "DemandJunkKey", hj)
        if len(newd) != len(dd):
            wh.append("DimDemandJunk", newd.iloc[len(dd):])
        dd = wh.query("SELECT * FROM DimDemandJunk")
        loaded_h, orphan_h = _load_demand_fact(db, wh, hosp, hj, dd, dim_med, dim_ho, batch_id)

    wh.execute("INSERT INTO EtlBatchLog VALUES (?,?,?,?,?,?,?)",
               [batch_id, now(), loaded_s, loaded_h, med_added, orphan_s, orphan_h])
    return {"batch": batch_id, "sales_loaded": loaded_s, "demand_loaded": loaded_h, "medicine_versions_added": med_added,
            "sales_orphans": orphan_s, "demand_orphans": orphan_h}


def _read_dim_plain(wh, table):
    return wh.query(f"SELECT * FROM {table}")


def _record_orphans(db, batch_id, table, keys: pd.Series):
    if len(keys):
        db.bulk_insert("stg_rejects", pd.DataFrame({
            "batch_id": batch_id, "source_table": table, "record_key": keys.astype(str).values,
            "rule": "orphan_dimension_key", "rejected_at": now()}))


def _load_sales_fact(db, wh, s, sj, dj, dim_med, dim_ph, batch_id):
    f = pd.DataFrame(index=s.index)
    f["SalesDateIso"] = _iso(s["SalesDate"])
    f["DeliveryDateIso"] = _iso(s["PharmacyDeliveryDate"]).fillna(f["SalesDateIso"])
    f["MedicineID"], f["PharmacyID"] = _s(s["MedicineID"]), _s(s["PharmacyID"])
    f["MedicineKey"] = asof_lookup(f, dim_med, "MedicineID", "MedicineKey", "SalesDateIso")
    f["PharmacyKey"] = asof_lookup(f, dim_ph, "PharmacyID", "PharmacyKey", "SalesDateIso")
    f["SalesJunkKey"] = junk_lookup(sj, dj, "SalesJunkKey")
    f["SalesTransactionID"] = _s(s["SalesTransactionID"])
    # idempotency / no double counting: skip transactions already in the fact
    existing = set(wh.query("SELECT SalesTransactionID FROM FactPharmacySales")["SalesTransactionID"])
    f = f[~f["SalesTransactionID"].isin(existing)]
    orphan = f["MedicineKey"].isna() | f["PharmacyKey"].isna() | f["SalesJunkKey"].isna()
    _record_orphans(db, batch_id, "stg_pharmacy_sales", f.loc[orphan, "SalesTransactionID"])
    f = f[~orphan]
    s = s.loc[f.index]
    start = int(wh.query("SELECT COALESCE(MAX(SalesKey),0) AS m FROM FactPharmacySales")["m"][0]) + 1
    n = lambda c: pd.to_numeric(s[c], errors="coerce")
    out = pd.DataFrame({
        "SalesKey": range(start, start + len(f)), "SalesDateKey": _datekey(f["SalesDateIso"]).values,
        "DeliveryDateKey": _datekey(f["DeliveryDateIso"]).values,
        "MedicineKey": f["MedicineKey"].astype(int).values, "PharmacyKey": f["PharmacyKey"].astype(int).values,
        "SalesJunkKey": f["SalesJunkKey"].astype(int).values, "SalesTransactionID": f["SalesTransactionID"].values,
        "PharmacyOrderID": _s(s["PharmacyOrderID"]).values, "PharmacyDeliveryID": _s(s["PharmacyDeliveryID"]).values,
        "PrescriptionID": _s(s["PrescriptionID"]).fillna("N/A").values, "WarehouseLotID": _s(s["WarehouseLotID"]).values,
        "ProductionBatchID": _s(s["ProductionBatchID"]).values,
        "QuantitySoldPacks": n("QuantitySoldPacks").astype(int).values,
        "NetSalesAmount": n("NetSalesAmountUSD").round(2).values, "DiscountAmount": n("DiscountAmountUSD").round(2).values,
        "CostOfGoodsSold": n("CostOfGoodsSoldUSD").round(2).values,
        "ReturnedQuantityPacks": n("ReturnedQuantityPacks").fillna(0).astype(int).values, "BatchID": batch_id})
    wh.append("FactPharmacySales", out)
    return len(out), int(orphan.sum())


def _load_demand_fact(db, wh, h, hj, dd, dim_med, dim_ho, batch_id):
    f = pd.DataFrame(index=h.index)
    first = pd.to_datetime(h["DemandMonth"], format="mixed", errors="coerce").dt.to_period("M").dt.to_timestamp()
    f["MonthIso"] = first.dt.strftime("%Y-%m-%d")
    f["MedicineID"], f["HospitalID"] = _s(h["MedicineID"]), _s(h["HospitalID"])
    f["MedicineKey"] = asof_lookup(f, dim_med, "MedicineID", "MedicineKey", "MonthIso")
    f["HospitalKey"] = asof_lookup(f, dim_ho, "HospitalID", "HospitalKey", "MonthIso")
    f["DemandJunkKey"] = junk_lookup(hj, dd, "DemandJunkKey")
    f["RecId"] = _s(h["HospitalDemandRecordID"])
    existing = set(wh.query("SELECT HospitalDemandRecordID FROM FactHospitalDemand")["HospitalDemandRecordID"])
    f = f[~f["RecId"].isin(existing)]
    orphan = f["MedicineKey"].isna() | f["HospitalKey"].isna() | f["DemandJunkKey"].isna()
    _record_orphans(db, batch_id, "stg_hospital_demand", f.loc[orphan, "RecId"])
    f = f[~orphan]
    h = h.loc[f.index]
    start = int(wh.query("SELECT COALESCE(MAX(DemandKey),0) AS m FROM FactHospitalDemand")["m"][0]) + 1
    n = lambda c: pd.to_numeric(h[c], errors="coerce")
    out = pd.DataFrame({
        "DemandKey": range(start, start + len(f)), "MonthDateKey": _datekey(f["MonthIso"]).values,
        "HospitalKey": f["HospitalKey"].astype(int).values, "MedicineKey": f["MedicineKey"].astype(int).values,
        "DemandJunkKey": f["DemandJunkKey"].astype(int).values, "HospitalDemandRecordID": f["RecId"].values,
        "ForecastDemandPacks": n("ForecastDemandPacks").fillna(0).astype(int).values,
        "RequestedQuantityPacks": n("RequestedQuantityPacks").fillna(0).astype(int).values,
        "ConsumedQuantityPacks": n("ConsumedQuantityPacks").fillna(0).astype(int).values,
        "UnfulfilledDemandPacks": n("UnfulfilledDemandPacks").fillna(0).astype(int).values,
        "ClosingStockPacks": n("ClosingStockPacks").fillna(0).astype(int).values, "BatchID": batch_id})
    wh.append("FactHospitalDemand", out)
    return len(out), int(orphan.sum())
