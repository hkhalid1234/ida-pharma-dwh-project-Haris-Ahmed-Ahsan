"""Data-quality gate between staging and the warehouse.
Rejected rows are written to stg_rejects (never silently dropped) and excluded from the transform."""
import pandas as pd

from .db import Db
from .ingestion import now

REQUIRED = {
    "stg_pharmacy_sales": ["SalesTransactionID", "MedicineID", "PharmacyID", "SalesDate", "QuantitySoldPacks", "NetSalesAmountUSD"],
    "stg_hospital_demand": ["HospitalDemandRecordID", "MedicineID", "HospitalID", "DemandMonth", "RequestedQuantityPacks"],
    "stg_master_data": ["MedicineID", "PackSize"],
}
PK = {"stg_pharmacy_sales": "SalesTransactionID", "stg_hospital_demand": "HospitalDemandRecordID", "stg_master_data": "MedicineID"}


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def _bad_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="mixed", errors="coerce").isna()


def rules_for(table: str, df: pd.DataFrame) -> dict[str, pd.Series]:
    """Return {rule_name: boolean mask of violating rows}."""
    num = lambda c: pd.to_numeric(df[c], errors="coerce")
    if table == "stg_pharmacy_sales":
        return {
            "sku_not_null": _blank(df["MedicineID"]),
            "pharmacy_not_null": _blank(df["PharmacyID"]),
            "valid_sales_date": _bad_date(df["SalesDate"]),
            "quantity_positive": ~(num("QuantitySoldPacks") > 0),
            "net_sales_positive": ~(num("NetSalesAmountUSD") > 0),   # "price > 0"
            "duplicate_in_batch": df.duplicated("SalesTransactionID", keep="first"),
        }
    if table == "stg_hospital_demand":
        return {
            "sku_not_null": _blank(df["MedicineID"]),
            "hospital_not_null": _blank(df["HospitalID"]),
            "valid_demand_month": _bad_date(df["DemandMonth"]),
            "requested_non_negative": ~(num("RequestedQuantityPacks") >= 0),
            "duplicate_in_batch": df.duplicated("HospitalDemandRecordID", keep="first"),
        }
    return {
        "sku_not_null": _blank(df["MedicineID"]),
        "pack_size_positive": ~(num("PackSize") > 0),
        "duplicate_in_batch": df.duplicated("MedicineID", keep="first"),
    }


def validate_batch(db: Db, batch_id: str) -> dict:
    summary = {}
    for table, pk in PK.items():
        df = db.read_df(f'SELECT * FROM {table} WHERE batch_id={{ph}}', (batch_id,))
        if df.empty:
            summary[table] = {"rows": 0, "rejected": 0, "by_rule": {}}
            continue
        missing = [c for c in REQUIRED[table] if c not in df.columns]
        if missing:
            raise ValueError(f"{table}: required columns missing from source: {missing}")
        db.execute("DELETE FROM stg_rejects WHERE batch_id={ph} AND source_table={ph}", (batch_id, table))  # re-run safe
        rejected, by_rule = pd.Series(False, index=df.index), {}
        for rule, mask in rules_for(table, df).items():
            first_hit = mask & ~rejected          # attribute each bad row to the first rule it breaks
            if first_hit.any():
                by_rule[rule] = int(first_hit.sum())
                out = pd.DataFrame({"batch_id": batch_id, "source_table": table,
                                    "record_key": df.loc[first_hit, pk].astype(str).values,
                                    "rule": rule, "rejected_at": now()})
                db.bulk_insert("stg_rejects", out)
            rejected |= mask
        summary[table] = {"rows": len(df), "rejected": int(rejected.sum()), "by_rule": by_rule}
    return summary


def clean_batch(db: Db, table: str, batch_id: str) -> pd.DataFrame:
    """Staging rows of one batch that pass every rule (duplicates: first occurrence survives).
    Uses the same rule functions as validate_batch, so reject table and clean set always agree."""
    df = db.read_df(f"SELECT * FROM {table} WHERE batch_id={{ph}}", (batch_id,))
    if df.empty:
        return df
    bad = pd.Series(False, index=df.index)
    for mask in rules_for(table, df).values():
        bad |= mask
    return df[~bad].reset_index(drop=True)
