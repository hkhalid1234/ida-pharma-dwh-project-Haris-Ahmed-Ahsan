"""Ingestion layer: file-watcher + batch loader into the Postgres staging area (ODS).

Every load is measured (duration, rows, success) and written to ops_batch_load_log, which feeds the
Batch-Ingestion dashboard (Milestone 2).
"""
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import config
from .db import Db

OPS_DDL = """
CREATE TABLE IF NOT EXISTS ops_batch_load_log (
    source_file TEXT, source_table TEXT, batch_id TEXT, rows_loaded INTEGER,
    duration_seconds DOUBLE PRECISION, status TEXT, error_message TEXT, loaded_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS stg_rejects (
    batch_id TEXT, source_table TEXT, record_key TEXT, rule TEXT, rejected_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS ops_query_log (
    run_id TEXT, query_id TEXT, variant TEXT, duration_ms DOUBLE PRECISION, rows_returned INTEGER,
    status TEXT, error_message TEXT, executed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS ops_storage_metrics (
    measured_at TIMESTAMP, layer TEXT, object_name TEXT, row_count BIGINT, size_mb DOUBLE PRECISION,
    min_date TEXT, max_date TEXT);
CREATE TABLE IF NOT EXISTS ops_pipeline_runs (
    run_id TEXT, refresh_no INTEGER, stage TEXT, status TEXT, detail TEXT, logged_at TIMESTAMP);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_ops_tables(db: Db):
    db.script(OPS_DDL)


# ------------------------------------------------------------------ file watcher
def source_stem(path: Path) -> str | None:
    """'05_pharmacy_sales_data__R01.csv' -> '05_pharmacy_sales_data'."""
    stem = path.stem.split("__")[0]
    return stem if stem in config.SOURCES else None


def batch_of(path: Path) -> str:
    m = re.search(r"__(R\d+|INIT)$", path.stem)
    return m.group(1) if m else "ADHOC"


def stable_files(incoming: Path, settle_seconds: float = 2.0) -> list[Path]:
    """Files that match a known source and have not been written to for `settle_seconds`
    (protects against reading half-written files)."""
    out = []
    for p in sorted(incoming.glob("*.csv")):
        if source_stem(p) and time.time() - p.stat().st_mtime >= settle_seconds:
            out.append(p)
    return out


def expected_files_present(incoming: Path, batch_id: str) -> bool:
    need = {f"{stem}__{batch_id}.csv" for stem in config.SOURCES}
    have = {p.name for p in stable_files(incoming, settle_seconds=0.5)}
    return need.issubset(have)


# ------------------------------------------------------------------ staging load
def _ensure_stg_table(db: Db, table: str, df: pd.DataFrame):
    cols = list(df.columns)  # already includes batch_id, source_file, loaded_at
    if db.is_sqlite:
        existing = {r[1] for r in db.conn.execute(f"PRAGMA table_info({table})")}
    else:
        existing = set(db.read_df(
            "SELECT column_name FROM information_schema.columns WHERE table_name={ph}", (table,))["column_name"])
    if not existing:
        db.script(f'CREATE TABLE {table} (' + ", ".join(f'"{c}" TEXT' for c in cols) + ")")
    else:  # schema drift: new source column appears -> add it instead of failing
        for c in cols:
            if c not in existing:
                db.script(f'ALTER TABLE {table} ADD COLUMN "{c}" TEXT')


def _log(db, path, table, batch, rows, dur, status, err=None):
    db.execute("INSERT INTO ops_batch_load_log VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
               (path.name, table, batch, rows, round(dur, 4), status, err, now()))


def already_loaded(db: Db, path: Path) -> bool:
    r = db.read_df("SELECT COUNT(*) AS n FROM ops_batch_load_log WHERE source_file={ph} AND status='success'", (path.name,))
    return int(r["n"][0]) > 0


def ingest_file(db: Db, path: Path, archive_dir: Path | None = None) -> dict:
    stem = source_stem(path)
    table = config.SOURCES[stem]["table"]
    batch = batch_of(path)
    if already_loaded(db, path):   # idempotent: re-running a DAG never double-loads a file
        return {"file": path.name, "skipped": True}
    t0 = time.perf_counter()
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        df["batch_id"], df["source_file"], df["loaded_at"] = batch, path.name, now()
        _ensure_stg_table(db, table, df)
        db.bulk_insert(table, df)
        dur = time.perf_counter() - t0
        _log(db, path, table, batch, len(df), dur, "success")
        if archive_dir is not None:
            archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(archive_dir / path.name))
        return {"file": path.name, "rows": len(df), "seconds": round(dur, 3), "table": table}
    except Exception as exc:  # noqa: BLE001 - we want every failure on the dashboard
        db.conn.rollback()
        _log(db, path, table, batch, 0, time.perf_counter() - t0, "failed", str(exc)[:500])
        raise


def ingest_pending(db: Db, incoming: Path, batch_id: str | None = None, archive_dir: Path | None = None,
                   stem: str | None = None) -> list[dict]:
    results, errors = [], []
    for p in stable_files(incoming):
        if batch_id and batch_of(p) != batch_id:
            continue
        if stem and source_stem(p) != stem:
            continue
        try:
            results.append(ingest_file(db, p, archive_dir))
        except Exception as exc:  # collect, keep loading the remaining files
            errors.append(f"{p.name}: {exc}")
    if errors:
        raise RuntimeError("Ingestion failures -> " + " | ".join(errors))
    return results


def batch_already_ingested(db: Db, batch_id: str) -> bool:
    """True when all Phase-1 files of the batch were loaded before (makes DAG re-runs/sensors idempotent)."""
    r = db.read_df("SELECT COUNT(DISTINCT source_table) AS n FROM ops_batch_load_log WHERE batch_id={ph} AND status='success'", (batch_id,))
    return int(r["n"][0]) >= len(config.SOURCES)
