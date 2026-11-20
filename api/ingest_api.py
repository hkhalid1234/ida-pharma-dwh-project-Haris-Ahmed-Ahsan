"""Minimal ingestion API (FastAPI).  Run:  uvicorn api.ingest_api:app --port 8000
  POST /files   - upload a CSV into the landing zone (name must follow <source>__<batch>.csv)
  POST /ingest  - load everything pending in the landing zone into staging
  GET  /health  - liveness
Airflow/file-watcher do the same work automatically; the API is the manual/external entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "include"))
from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import HTMLResponse

from sdi import config, ingestion  # noqa: E402
from sdi.db import Db  # noqa: E402

app = FastAPI(title="SDI Pipeline & Ingestion Portal")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    db = Db(config.STAGING_DSN)
    ingestion.ensure_ops_tables(db)
    load_logs = db.read_df("SELECT source_table, COUNT(*) AS batches, SUM(rows_loaded) AS total_rows FROM ops_batch_load_log GROUP BY source_table")
    rows_html = "".join(f"<tr><td><b>{r['source_table']}</b></td><td>{r['batches']}</td><td>{r['total_rows']:,}</td></tr>" for _, r in load_logs.iterrows()) if not load_logs.empty else "<tr><td colspan='3'>No batches logged yet. Trigger an initial load or refresh below.</td></tr>"
    db.close()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SDI Data Mart - Pipeline Portal</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 30px; }}
    .container {{ max-width: 900px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }}
    h1 {{ color: #38bdf8; margin-top: 0; display: flex; align-items: center; justify-content: space-between; font-size: 24px; }}
    .badge {{ background: #0284c7; color: white; font-size: 12px; padding: 4px 10px; border-radius: 20px; font-weight: normal; }}
    .sub {{ color: #94a3b8; font-size: 14px; margin-bottom: 25px; }}
    .card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
    .card {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 15px; text-align: center; }}
    .card h3 {{ margin: 0 0 8px 0; color: #94a3b8; font-size: 13px; font-weight: 500; text-transform: uppercase; }}
    .card .val {{ font-size: 26px; font-weight: bold; color: #38bdf8; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155; }}
    th {{ background: #0f172a; color: #94a3b8; }}
    .actions {{ display: flex; gap: 10px; margin-top: 25px; flex-wrap: wrap; }}
    .btn {{ background: #0284c7; color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 14px; border: none; cursor: pointer; transition: 0.2s; }}
    .btn:hover {{ background: #0369a1; }}
    .btn-secondary {{ background: #334155; }}
    .btn-secondary:hover {{ background: #475569; }}
    .footer {{ margin-top: 30px; font-size: 12px; color: #64748b; text-align: center; border-top: 1px solid #334155; padding-top: 15px; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Sales & Demand Intelligence (SDI) Portal <span class="badge">Milestone 1 Active</span></h1>
    <div class="sub">Intelligent Data Architectures - Pharmaceutical Cold Supply Chain Data Mart</div>

    <div class="card-grid">
      <div class="card">
        <h3>Architecture</h3>
        <div class="val" style="font-size: 18px; color: #34d399;">Fact Constellation</div>
      </div>
      <div class="card">
        <h3>Primary Storage</h3>
        <div class="val" style="font-size: 18px;">DuckDB + Postgres</div>
      </div>
      <div class="card">
        <h3>Pipeline State</h3>
        <div class="val" style="font-size: 18px; color: #38bdf8;">Ready</div>
      </div>
    </div>

    <h2 style="font-size: 16px; color: #e2e8f0; margin-top: 25px;">Logged Batch Ingestion Metrics</h2>
    <table>
      <thead>
        <tr><th>Source Table</th><th>Batches Processed</th><th>Total Rows Loaded</th></tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <div class="actions">
      <a class="btn" href="/docs" target="_blank">Open Interactive API Docs (Swagger UI)</a>
      <a class="btn btn-secondary" href="/health" target="_blank">Liveness Health Check (/health)</a>
    </div>

    <div class="footer">
      Team: Ahsan Imran, Haris Khalid, Syed Ahmed Farrukh | SDI Phase 1 Milestone 1
    </div>
  </div>
</body>
</html>"""


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
