"""Central configuration. Everything is overridable through environment variables so the
same code runs in Docker/Airflow, on a laptop, and in the unit tests."""
import os
from pathlib import Path

SQL_DIR = Path(__file__).parent / "sql"
DATA_DIR = Path(os.getenv("SDI_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data")))
RAW_DIR = DATA_DIR / "raw"            # original 7 CSVs from the course dataset
INCOMING_DIR = DATA_DIR / "incoming"  # landing zone watched by the file-watcher
ARCHIVE_DIR = DATA_DIR / "archive"    # files move here after a successful load
PARQUET_DIR = DATA_DIR / "parquet"    # partitioned fact exports (query layer)
DUCKDB_PATH = os.getenv("SDI_DUCKDB_PATH", str(DATA_DIR / "warehouse" / "sdi_mart.duckdb"))

# Staging area / ODS (PostgreSQL). Also hosts the ops_* observability tables.
STAGING_DSN = os.getenv("SDI_STAGING_DSN", "postgresql://sdi:sdi@localhost:5432/staging")

# Phase-1 source files -> staging table, business key(s) in the source
SOURCES = {
    "01_master_data":          {"table": "stg_master_data",     "pk": ["MedicineID"]},
    "05_pharmacy_sales_data":  {"table": "stg_pharmacy_sales",  "pk": ["SalesTransactionID"]},
    "06_hospital_demand_data": {"table": "stg_hospital_demand", "pk": ["HospitalDemandRecordID"]},
}

# Oversampling plan: one refresh = one new calendar month after the historical range.
REFRESH_PLAN = {
    1: {"month": "2026-01-01", "sales_growth": 1.03, "hospital_noise": 0.06},
    2: {"month": "2026-02-01", "sales_growth": 1.05, "hospital_noise": 0.06},
}
DIRTY_RATE = float(os.getenv("SDI_DIRTY_RATE", "0.005"))  # share of deliberately bad rows
DATE_DIM_START, DATE_DIM_END = "2023-01-01", "2026-12-31"
