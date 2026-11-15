"""Minimal ingestion API (FastAPI).  Run:  uvicorn api.ingest_api:app --port 8000
  POST /files   - upload a CSV into the landing zone (name must follow <source>__<batch>.csv)
  POST /ingest  - load everything pending in the landing zone into staging
  GET  /health  - liveness
Airflow/file-watcher do the same work automatically; the API is the manual/external entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "include"))
from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402

from sdi import config, ingestion  # noqa: E402
from sdi.db import Db  # noqa: E402

app = FastAPI(title="SDI ingestion API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/files")
async def upload(file: UploadFile = File(...)):
    target = config.INCOMING_DIR / Path(file.filename).name
    if ingestion.source_stem(target) is None:
        raise HTTPException(400, f"unknown source file; expected one of {list(config.SOURCES)}")
    config.INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    target.write_bytes(await file.read())
    return {"stored": target.name}


@app.post("/ingest")
def ingest():
    db = Db(config.STAGING_DSN)
    try:
        ingestion.ensure_ops_tables(db)
        return {"loaded": ingestion.ingest_pending(db, config.INCOMING_DIR, archive_dir=config.ARCHIVE_DIR)}
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    finally:
        db.close()
