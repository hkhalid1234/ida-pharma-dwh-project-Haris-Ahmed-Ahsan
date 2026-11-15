"""Oversampling layer: synthesises new batch files for the three Phase-1 sources.

Design rules (documented in the report):
  * Every refresh simulates ONE new calendar month after the historical range (Jan-26, Feb-26).
  * Sales volume = historical monthly average x growth factor x seasonality of that calendar month.
  * Rows are bootstrapped from the same calendar month of earlier years, then perturbed
    (quantity, amount, dates) so statistical shape (mix of products, stores, channels) is preserved.
  * IDs continue the existing sequence, so primary keys never collide with history.
  * ~0.5% of rows are deliberately corrupted so the validation layer has something to catch.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

DATE_FMT = "%Y-%m-%d"  # source CSVs store dates as ISO text (YYYY-MM-DD)


def _parse(s):
    return pd.to_datetime(s, format="mixed", errors="coerce")


def _fmt_date(s: pd.Series) -> pd.Series:
    return s.dt.strftime(DATE_FMT)


def _next_ids(existing: pd.Series, n: int) -> list:
    """Continue an ID sequence like 'SALE0000123' -> 'SALE0000124'..."""
    last = existing.dropna().astype(str).iloc[-1]
    m = re.match(r"^(\D*)(\d+)$", last)
    if not m:
        return [f"{last}_G{i}" for i in range(n)]
    prefix, num = m.group(1), m.group(2)
    top = max(int(re.match(r"^\D*(\d+)$", x).group(1)) for x in existing.astype(str) if re.match(r"^\D*\d+$", x))
    return [f"{prefix}{top + 1 + i:0{len(num)}d}" for i in range(n)]


def generate_sales(hist: pd.DataFrame, refresh_no: int, seed: int | None = None):
    plan = config.REFRESH_PLAN[refresh_no]
    rng = np.random.default_rng(seed if seed is not None else 1000 + refresh_no)
    month = pd.Timestamp(plan["month"])
    d = hist.copy()
    d["_sd"] = _parse(d["SalesDate"])
    d["_dd"] = _parse(d["PharmacyDeliveryDate"])
    # never bootstrap from rows that earlier refreshes deliberately corrupted
    d = d[d["_sd"].notna() & d["MedicineID"].notna() & (pd.to_numeric(d["QuantitySoldPacks"], errors="coerce") > 0)]
    months = d["_sd"].dt.to_period("M")
    monthly_avg = d.groupby(months).size().mean()
    same_month = d[d["_sd"].dt.month == month.month]
    season = (same_month.groupby(same_month["_sd"].dt.to_period("M")).size().mean() / monthly_avg) if len(same_month) else 1.0
    n = int(round(monthly_avg * plan["sales_growth"] * season))
    pool = same_month if len(same_month) >= 100 else d
    s = pool.sample(n=n, replace=True, random_state=int(rng.integers(1e9))).copy()

    days_in_month = month.days_in_month
    lag = (s["_dd"] - s["_sd"]).dt.days.fillna(1).clip(0, 14)
    new_sd = month + pd.to_timedelta(rng.integers(0, days_in_month, n), unit="D")
    s["SalesDate"] = _fmt_date(pd.Series(new_sd, index=s.index))
    s["PharmacyDeliveryDate"] = _fmt_date(pd.Series(new_sd, index=s.index) - pd.to_timedelta(lag, unit="D"))
    if "SalesTimestampUTC" in s:   # keep the time of day, move the date
        tod = pd.to_datetime(s["SalesTimestampUTC"], errors="coerce", utc=True)
        secs = (tod.dt.hour * 3600 + tod.dt.minute * 60 + tod.dt.second).fillna(43200).astype(int).values
        s["SalesTimestampUTC"] = (pd.Series(new_sd, index=s.index) + pd.to_timedelta(secs, unit="s")).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "DaysToExpiryAtSale" in s and "BatchExpiryDate" in s:
        exp = _parse(s["BatchExpiryDate"])
        shift = (pd.Series(new_sd, index=s.index) - s["_sd"]).dt.days
        s["BatchExpiryDate"] = _fmt_date(exp + pd.to_timedelta(shift, unit="D"))   # same shelf life left at sale

    old_q = s["QuantitySoldPacks"].astype(float).clip(lower=1)
    new_q = np.maximum(1, np.round(old_q * rng.normal(1.0, 0.15, n))).astype(int)
    f = new_q / old_q
    for col in ["NetSalesAmountUSD", "DiscountAmountUSD", "CostOfGoodsSoldUSD"]:
        if col in s:
            s[col] = np.round(s[col].astype(float) * f, 2)
    if "SalesTaxUSD" in s:
        s["SalesTaxUSD"] = np.round(s["SalesTaxUSD"].astype(float) * f, 2)
    s["ReturnedQuantityPacks"] = np.minimum(s["ReturnedQuantityPacks"].fillna(0).astype(int), new_q)
    s["QuantitySoldPacks"] = new_q
    s["SalesTransactionID"] = _next_ids(hist["SalesTransactionID"], n)
    s = s.drop(columns=["_sd", "_dd"]).reset_index(drop=True)
    return _corrupt_sales(s, rng), {"rows": n, "month": plan["month"], "season_factor": round(float(season), 3)}


def _corrupt_sales(df, rng):
    k = max(1, int(len(df) * config.DIRTY_RATE))
    idx = rng.choice(len(df), size=k, replace=False)
    third = max(1, k // 3)
    df = df.copy()
    df.loc[idx[:third], "QuantitySoldPacks"] = -1               # rule: qty > 0
    df.loc[idx[third:2 * third], "MedicineID"] = None           # rule: non-null SKU
    df.loc[idx[2 * third:], "SalesDate"] = "13/45/2026"         # rule: valid date
    return df


def generate_hospital(hist: pd.DataFrame, refresh_no: int, seed: int | None = None):
    plan = config.REFRESH_PLAN[refresh_no]
    rng = np.random.default_rng(seed if seed is not None else 2000 + refresh_no)
    month = pd.Timestamp(plan["month"])
    h = hist.copy()
    h["_m"] = _parse(h["DemandMonth"])
    base = h[h["_m"].dt.month == month.month]
    last_year = base[base["_m"] == base["_m"].max()] if len(base) else h[h["_m"] == h["_m"].max()]
    n = len(last_year)
    out = last_year.copy()
    g = rng.normal(1.0, plan["hospital_noise"], n).clip(0.7, 1.4)
    for c in ["ForecastDemandPacks", "RequestedQuantityPacks", "ConsumedQuantityPacks", "ClosingStockPacks"]:
        out[c] = np.round(out[c].astype(float) * g).astype(int)
    unf = out["UnfulfilledDemandPacks"].fillna(0).astype(float) * g * rng.normal(1.0, 0.2, n).clip(0.3, 2)
    out["UnfulfilledDemandPacks"] = np.minimum(np.round(unf), out["RequestedQuantityPacks"]).astype(int)
    out["DemandMonth"] = month.strftime(DATE_FMT)
    out["HospitalDemandRecordID"] = _next_ids(hist["HospitalDemandRecordID"], n)
    out = out.drop(columns=["_m"]).reset_index(drop=True)
    return out, {"rows": n, "month": plan["month"]}


def generate_master_changes(hist: pd.DataFrame, refresh_no: int, seed: int | None = None):
    """Refresh 2 only: a few attribute changes so SCD Type 2 is demonstrable.
    Refresh 1 emits an empty (header-only) delta - nothing changed in master data."""
    plan = config.REFRESH_PLAN[refresh_no]
    if refresh_no != 2:
        return hist.iloc[0:0].copy(), {"rows": 0, "month": plan["month"]}
    rng = np.random.default_rng(seed if seed is not None else 3000)
    ch = hist.sample(n=min(3, len(hist)), random_state=int(rng.integers(1e9))).copy()
    ch["PackSize"] = ch["PackSize"].astype(int).apply(lambda x: x * 2 if x < 100 else x)          # Type 2 attribute
    ch["PrescriptionClass"] = ch["PrescriptionClass"].replace({"Prescription": "OTC"}, regex=False)  # Type 2 attribute
    ch["GTIN14"] = ch["GTIN14"].astype(str)                                                        # Type 1 stays
    ch["EffectiveFromDate"] = pd.Timestamp(plan["month"]).strftime(DATE_FMT)
    return ch.reset_index(drop=True), {"rows": len(ch), "month": plan["month"]}


GENERATORS = {"05_pharmacy_sales_data": generate_sales,
              "06_hospital_demand_data": generate_hospital,
              "01_master_data": generate_master_changes}


def generate_one(stem: str, raw_dir: Path, out_dir: Path, refresh_no: int) -> dict:
    """Generate the delta file for ONE source and return its statistics (one Airflow task per source)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    hist = _read_history(raw_dir, stem)
    df, st = GENERATORS[stem](hist, refresh_no)
    path = out_dir / f"{stem}__R{refresh_no:02d}.csv"
    df.to_csv(path, index=False)
    st.update({"source": stem, "file": path.name, "historical_rows": len(hist),
               "pct_of_history": round(100 * len(df) / max(len(hist), 1), 2)})
    return st


def generate_all(raw_dir: Path, out_dir: Path, refresh_no: int) -> dict:
    return {stem: generate_one(stem, raw_dir, out_dir, refresh_no) for stem in GENERATORS}


def _read_history(raw_dir: Path, stem: str) -> pd.DataFrame:
    """History = original file plus any earlier refresh already archived."""
    parts = [pd.read_csv(raw_dir / f"{stem}.csv", dtype=str)]
    arch = raw_dir.parent / "archive"
    if arch.exists():
        parts += [pd.read_csv(p, dtype=str) for p in sorted(arch.glob(f"{stem}__R*.csv"))]
    return pd.concat(parts, ignore_index=True)
