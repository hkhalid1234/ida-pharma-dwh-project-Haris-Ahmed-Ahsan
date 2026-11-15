"""Stand-alone automated file-watcher (the Python-based watcher required by the ingestion layer).

Polls the landing zone; every file that matches a known source and has stopped growing is loaded into
the Postgres staging area, measured, and moved to data/archive.   Usage:
    python scripts/run_watcher.py --interval 5
Airflow uses the same primitives (ingestion.expected_files_present / ingest_pending) through a PythonSensor.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "include"))
from sdi import config, ingestion  # noqa: E402
from sdi.db import Db  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--once", action="store_true", help="process what is there, then exit")
    a = ap.parse_args()
    db = Db(config.STAGING_DSN)
    ingestion.ensure_ops_tables(db)
    print(f"watching {config.INCOMING_DIR} every {a.interval}s ...")
    while True:
        try:
            for r in ingestion.ingest_pending(db, config.INCOMING_DIR, archive_dir=config.ARCHIVE_DIR):
                print(time.strftime("%H:%M:%S"), r)
        except Exception as exc:  # logged in ops_batch_load_log already; keep watching
            print("ERROR", exc)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
