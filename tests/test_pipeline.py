"""End-to-end test on synthetic data: initial load + 2 refreshes through every layer.
Staging = SQLite stand-in for Postgres, warehouse = SQLite stand-in for DuckDB (same portable SQL)."""
import os, shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "include"))
sys.path.insert(0, str(Path(__file__).parent))
tmp = Path(tempfile.mkdtemp())
os.environ["SDI_DATA_DIR"] = str(tmp)

import pandas as pd
from make_fake_data import make
from sdi import config, generator, ingestion, query_layer, transform, validation
from sdi.db import Db
from sdi.warehouse import SqliteWarehouse


def run_batch(db, wh, batch):
    ing = ingestion.ingest_pending(db, config.INCOMING_DIR, batch, config.ARCHIVE_DIR)
    val = validation.validate_batch(db, batch)
    tr = transform.run_transform(db, wh, batch)
    opt = query_layer.optimise(wh)
    return ing, val, tr, opt


def main():
    make(config.RAW_DIR); config.INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    db = Db(f"sqlite:///{tmp/'staging.db'}"); ingestion.ensure_ops_tables(db)
    wh = SqliteWarehouse(str(tmp / "mart.db"))
    # --- INIT: seed landing zone with the historical files
    for stem in config.SOURCES:
        shutil.copy(config.RAW_DIR / f"{stem}.csv", config.INCOMING_DIR / f"{stem}__INIT.csv")
    import time; time.sleep(2.1)
    ing, val, tr, _ = run_batch(db, wh, "INIT")
    print("INIT", tr)
    n_sales0 = int(wh.query("SELECT COUNT(*) n FROM FactPharmacySales")["n"][0])
    assert n_sales0 == 20000 and tr["sales_orphans"] == 0
    assert int(wh.query("SELECT COUNT(*) n FROM DimMedicine")["n"][0]) == 63
    assert int(wh.query("SELECT COUNT(*) n FROM FactHospitalDemand")["n"][0]) == 63 * 12 * 36
    assert int(wh.query("SELECT COUNT(*) n FROM DimLocation")["n"][0]) == 18
    # idempotency: same batch twice must not duplicate anything
    assert transform.run_transform(db, wh, "INIT").get("skipped")

    prev = n_sales0
    for r in (1, 2):
        stats = generator.generate_all(config.RAW_DIR, config.INCOMING_DIR, r)
        print(f"R{r} generated", {k: v["rows"] for k, v in stats.items()})
        time.sleep(2.1)
        ing, val, tr, opt = run_batch(db, wh, f"R{r:02d}")
        print(f"R{r:02d}", tr, val["stg_pharmacy_sales"]["by_rule"])
        total = int(wh.query("SELECT COUNT(*) n FROM FactPharmacySales")["n"][0])
        assert total == prev + tr["sales_loaded"] > prev           # history kept, new rows appended
        assert val["stg_pharmacy_sales"]["rejected"] > 0            # validation caught the injected dirt
        assert tr["sales_loaded"] + val["stg_pharmacy_sales"]["rejected"] == stats["05_pharmacy_sales_data"]["rows"]
        prev = total
    # --- facts must have unique business keys & valid FKs
    assert wh.query("SELECT COUNT(*)-COUNT(DISTINCT SalesTransactionID) d FROM FactPharmacySales")["d"][0] == 0
    assert wh.query("SELECT COUNT(*) n FROM FactPharmacySales f LEFT JOIN DimMedicine m ON m.MedicineKey=f.MedicineKey WHERE m.MedicineKey IS NULL")["n"][0] == 0
    # --- SCD2: refresh 2 changed 3 medicines -> versions exist, old sales still point to old version
    v = wh.query("SELECT MedicineID, COUNT(*) c FROM DimMedicine GROUP BY MedicineID HAVING COUNT(*)>1")
    assert len(v) == 3, v
    mid = v["MedicineID"][0]
    old = wh.query("SELECT MedicineKey, PackSize FROM DimMedicine WHERE MedicineID=? AND IsCurrent='N'", [mid])
    new = wh.query("SELECT MedicineKey, PackSize FROM DimMedicine WHERE MedicineID=? AND IsCurrent='Y'", [mid])
    assert old["PackSize"][0] != new["PackSize"][0]
    hist_old = wh.query("SELECT COUNT(*) n FROM FactPharmacySales WHERE MedicineKey=?", [int(old["MedicineKey"][0])])["n"][0]
    hist_new = wh.query("SELECT COUNT(*) n FROM FactPharmacySales f JOIN DimDate d ON d.DateKey=f.SalesDateKey WHERE f.MedicineKey=? AND d.Year<2026", [int(new["MedicineKey"][0])])["n"][0]
    assert hist_old > 0 and hist_new == 0, (hist_old, hist_new)
    # --- date coverage extends past 2025 after refreshes
    cov = wh.query("SELECT MAX(d.FullDate) hi FROM FactPharmacySales f JOIN DimDate d ON d.DateKey=f.SalesDateKey")["hi"][0]
    assert cov.startswith("2026-02"), cov
    # --- query layer: both variants return identical answers, all queries succeed, metrics logged
    bench = query_layer.run_benchmark(wh, db, "testrun", repeats=2)
    print("benchmark avg ms:", bench["avg_ms"]); assert bench["mismatches"] == [], bench
    log = db.read_df("SELECT status, COUNT(*) n FROM ops_query_log GROUP BY status")
    assert set(log["status"]) == {"success"}
    bad = query_layer.timed_query(wh, db, "testrun", "BAD", "base", "SELECT nope FROM nowhere")
    assert bad is None and db.read_df("SELECT COUNT(*) n FROM ops_query_log WHERE status='failed'")["n"][0] == 1
    print(query_layer.collect_storage_metrics(db, wh, None, None))
    lg = db.read_df("SELECT source_table, SUM(rows_loaded) rows, ROUND(AVG(duration_seconds),3) s FROM ops_batch_load_log GROUP BY 1")
    print(lg.to_string(index=False))
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
