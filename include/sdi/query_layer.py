"""Analytical query layer: aggregates, indexes, partitioned Parquet export, instrumented query runner
and storage metrics. All measurements go to the ops_* tables in Postgres (dashboard source)."""
import os
import re
import time
from pathlib import Path

import pandas as pd

from .ingestion import now
from .warehouse import SqliteWarehouse

SQL_DIR = Path(__file__).parent / "sql"
FACT_TABLES = ["FactPharmacySales", "FactHospitalDemand"]
DIM_TABLES = ["DimDate", "DimLocation", "DimMedicine", "DimPharmacy", "DimHospital", "DimSalesJunk", "DimDemandJunk"]


def _run_script(wh, path: Path):
    from .warehouse import _statements
    for stmt in _statements(path.read_text()):
        wh.execute(stmt)


def build_aggregates(wh):
    wh.drop_indexes()   # tables with dependent indexes cannot be dropped in DuckDB
    _run_script(wh, SQL_DIR / "aggregates.sql")
    return {t: int(wh.query(f"SELECT COUNT(*) AS n FROM {t}")["n"][0]) for t in ("AggSalesMonthly", "AggDemandMonthly")}


def create_indexes(wh):
    _run_script(wh, SQL_DIR / "indexes.sql")


def export_partitioned_parquet(wh, out_dir: Path) -> dict:
    """Physical partitioning: DuckDB has no native table partitions, so facts are also written as
    Hive-partitioned Parquet (year=/month=) that scans can prune by partition."""
    if isinstance(wh, SqliteWarehouse):
        return {"skipped": "sqlite"}
    out_dir.mkdir(parents=True, exist_ok=True)
    exports = {
        "FactPharmacySales": "SELECT f.*, d.Year AS year, d.MonthNumber AS month FROM FactPharmacySales f JOIN DimDate d ON d.DateKey = f.SalesDateKey",
        "FactHospitalDemand": "SELECT f.*, d.Year AS year FROM FactHospitalDemand f JOIN DimDate d ON d.DateKey = f.MonthDateKey",
    }
    for name, sql in exports.items():
        part = "(year, month)" if name == "FactPharmacySales" else "(year)"
        target = out_dir / name
        wh.execute(f"COPY ({sql}) TO '{target}' (FORMAT PARQUET, PARTITION_BY {part}, OVERWRITE_OR_IGNORE)")
    return {"exported": list(exports)}


def optimise(wh, parquet_dir: Path | None = None) -> dict:
    agg = build_aggregates(wh)
    create_indexes(wh)
    pq = export_partitioned_parquet(wh, parquet_dir) if parquet_dir else {}
    return {"aggregates": agg, "parquet": pq}


# ------------------------------------------------------------------ query catalogue + benchmark
def load_queries() -> dict[str, dict[str, str]]:
    text = (SQL_DIR / "queries.sql").read_text()
    out: dict[str, dict[str, str]] = {}
    for block in re.split(r"(?m)^-- name: ", text)[1:]:
        header, _, body = block.partition("\n")
        qid, variant = [x.strip() for x in header.split("|")]
        sql = "\n".join(l for l in body.splitlines() if not l.strip().startswith("--")).strip().rstrip(";")
        out.setdefault(qid, {})[variant] = sql
    return out


def timed_query(wh, db, run_id: str, qid: str, variant: str, sql: str) -> pd.DataFrame | None:
    """Wrap one analytical query: measure ms, count rows, record errors (feeds the Querying dashboard)."""
    t0 = time.perf_counter()
    status, err, df = "success", None, None
    try:
        df = wh.query(sql)
    except Exception as exc:  # noqa: BLE001
        status, err = "failed", str(exc)[:500]
    ms = (time.perf_counter() - t0) * 1000
    db.execute("INSERT INTO ops_query_log VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
               (run_id, qid, variant, round(ms, 3), 0 if df is None else len(df), status, err, now()))
    return df


def run_benchmark(wh, db, run_id: str, repeats: int = 3) -> dict:
    """Run every query in both variants `repeats` times; verify base == optimised results."""
    summary, mismatches = {}, []
    for qid, variants in load_queries().items():
        results = {}
        for variant, sql in variants.items():
            times = []
            for _ in range(repeats):
                before = time.perf_counter()
                df = timed_query(wh, db, run_id, qid, variant, sql)
                times.append((time.perf_counter() - before) * 1000)
                results[variant] = df
            summary[f"{qid}|{variant}"] = round(sum(times) / len(times), 2)
        b, o = results.get("base"), results.get("opt")
        if b is not None and o is not None and not _same(b, o):
            mismatches.append(qid)
    return {"avg_ms": summary, "mismatches": mismatches}


def _same(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    if a.shape != b.shape:
        return False
    a, b = a.reset_index(drop=True), b.reset_index(drop=True)
    for c in a.columns:
        if pd.api.types.is_numeric_dtype(a[c]):
            if not (pd.to_numeric(a[c]).sub(pd.to_numeric(b[c])).abs().fillna(0) < 1e-6).all():
                return False
        elif not (a[c].astype(str) == b[c].astype(str)).all():
            return False
    return True


# ------------------------------------------------------------------ storage metrics
def collect_storage_metrics(db, wh, duckdb_path: str | None, parquet_dir: Path | None) -> dict:
    ts, rows = now(), []
    for t in ("stg_master_data", "stg_pharmacy_sales", "stg_hospital_demand", "stg_rejects"):
        try:
            n = int(db.read_df(f"SELECT COUNT(*) AS n FROM {t}")["n"][0])
        except Exception:  # table not created yet
            db.conn.rollback(); continue
        size = None
        if not db.is_sqlite:
            size = float(db.read_df("SELECT pg_total_relation_size({ph}) AS s", (t,))["s"][0]) / 1e6
        rows.append((ts, "staging", t, n, size, None, None))
    for t in DIM_TABLES + FACT_TABLES + ["AggSalesMonthly", "AggDemandMonthly"]:
        try:
            n = int(wh.query(f"SELECT COUNT(*) AS n FROM {t}")["n"][0])
        except Exception:
            continue
        rows.append((ts, "warehouse", t, n, None, None, None))
    cov = wh.query("SELECT MIN(d.FullDate) AS lo, MAX(d.FullDate) AS hi FROM FactPharmacySales f JOIN DimDate d ON d.DateKey=f.SalesDateKey")
    rows.append((ts, "coverage", "FactPharmacySales.SalesDate", None, None, str(cov["lo"][0])[:10], str(cov["hi"][0])[:10]))
    cov = wh.query("SELECT MIN(d.FullDate) AS lo, MAX(d.FullDate) AS hi FROM FactHospitalDemand f JOIN DimDate d ON d.DateKey=f.MonthDateKey")
    rows.append((ts, "coverage", "FactHospitalDemand.Month", None, None, str(cov["lo"][0])[:10], str(cov["hi"][0])[:10]))
    if duckdb_path and os.path.exists(duckdb_path):
        rows.append((ts, "warehouse", "duckdb_file", None, os.path.getsize(duckdb_path) / 1e6, None, None))
    if parquet_dir and parquet_dir.exists():
        total = sum(p.stat().st_size for p in parquet_dir.rglob("*") if p.is_file())
        rows.append((ts, "warehouse", "parquet_partitions", None, total / 1e6, None, None))
    if not db.is_sqlite:
        s = float(db.read_df("SELECT pg_database_size(current_database()) AS s")["s"][0]) / 1e6
        rows.append((ts, "staging", "postgres_database_total", None, s, None, None))
    for r in rows:
        db.execute("INSERT INTO ops_storage_metrics VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})", r)
    return {"metrics_written": len(rows)}
