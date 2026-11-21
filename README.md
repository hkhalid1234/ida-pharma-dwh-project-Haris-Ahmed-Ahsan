# SDI Data Mart - Phase 1 (Sales & Demand Intelligence)

Intelligent Data Architectures (Fall 2026) - Pharmaceutical Cold Supply Chain Project.  
**Milestone 1:** Automated Apache Airflow pipeline up to analytical query layer with double refresh.

### Group Members:
* **Ahsan Imran** (ERP: 28376 | a.imran.28376@khi.iba.edu.pk)
* **Haris Khalid** (ERP: 28557 | h.khalid.28557@khi.iba.edu.pk)
* **Syed Ahmed Farrukh** (ERP: 28543 | s.farrukh.28543@khi.iba.edu.pk)

---

## Milestone 1 Required Deliverables

| Deliverable Name | File / Location | Description |
| :--- | :--- | :--- |
| **1) Milestone.1.SDI.DWH.Report** | [`Milestone.1.SDI.DWH.Report.pdf`](Milestone.1.SDI.DWH.Report.pdf) | Technical report (3 pages, strictly under 5) covering Airflow pipeline design, implementation problems and solutions, data engineering dashboards, DWH approach, and oversampling strategy. |
| **2) Milestone.1.SDI.DWH.Excel** | [`Milestone.1.SDI.DWH.Excel.xlsx`](Milestone.1.SDI.DWH.Excel.xlsx) | Comprehensive Kimball DWH design workbook (Business & OLTP X-Ray, transforms, dimensions, facts, star schema). |
| **3) Milestone.1.SDI.DWH.Video** | [`Milestone 1 Demo.mp4`](Milestone%201%20Demo.mp4) | Demo walkthrough (under 5 mins) explaining end-to-end pipeline execution and results. Video file included directly in repo: **Milestone 1 Demo**. |
| **4) All Code** | [`dags/`](dags/), [`include/sdi/`](include/sdi/), [`api/`](api/) | Modular Airflow DAG, DDL, SQL queries, ingestion file-watcher, validation rules, transforms, and query benchmarks. |
| **5) Oversampled Data Folder & Dictionary** | [`data/generated/`](data/generated/), [`data/generated/DATA_DICTIONARY.md`](data/generated/DATA_DICTIONARY.md) | Generated refresh batches (R01 Jan 2026, R02 Feb 2026) along with comprehensive column data dictionary. |

```
Oversampling -> Ingestion (file-watcher) -> Postgres staging/ODS + validation -> Transform (SCD 1/2, junk, role-playing)
  -> DuckDB star schema / fact constellation (2 facts, 7 dims) -> Query layer (indexes, aggregates, Parquet, timed queries)
```

- **Demo Video:** [`Milestone 1 Demo.mp4`](Milestone%201%20Demo.mp4) (Milestone 1 Demo)

## Repository layout
| Path | Purpose |
|---|---|
| `dags/sdi_phase1_dag.py` | The Airflow DAG (task wiring only) |
| `include/sdi/` | All logic: `generator`, `ingestion`, `validation`, `transform`, `query_layer`, `warehouse`, `db`, `config` |
| `include/sdi/sql/` | `star_schema.sql` (DDL), `aggregates.sql`, `indexes.sql`, `queries.sql` (Q1-Q3, K4-K6, base + optimised), `ops_views.sql` |
| `scripts/` | `setup_local.sh`, `start_airflow.sh`, `stop_airflow.sh`, `run_refresh.sh`, `run_watcher.py` (stand-alone file-watcher) |
| `api/ingest_api.py` | FastAPI ingestion endpoint (upload a batch file / trigger ingestion) |
| `tests/` | End-to-end test on synthetic data (`python tests/test_pipeline.py`) |
| `data/raw/` | Phase 1 source data from the course dataset (01, 05 gzipped, 06) |
| `data/generated/` | The batches our generator produced for refresh 1 (Jan 2026) and refresh 2 (Feb 2026), kept as evidence for the oversampling layer |

## Run it locally (no Docker)
Runs natively on macOS (tested on Apple Silicon). Needs [Homebrew](https://brew.sh) and [uv](https://docs.astral.sh/uv/).

1. **Data.** The three Phase 1 source files are already in `data/raw/`: `01_master_data.csv`,
   `06_hospital_demand_data.csv` and `05_pharmacy_sales_data.csv.gz`. The sales file is gzipped because
   218 MB is over GitHub's 100 MB file limit; `setup_local.sh` unpacks it. The other four dataset files
   belong to Phases 2-3.
2. **One-time setup.** Installs Postgres 16 (Homebrew service) with the `staging` and `airflow` databases,
   and a Python 3.11 virtualenv with Airflow 2.10.5:
   ```bash
   bash scripts/setup_local.sh
   ```
3. **Start Airflow** (scheduler + webserver). UI: http://localhost:8080, login `admin` / `admin`:
   ```bash
   bash scripts/start_airflow.sh
   ```
4. **Initial historical load** (2023-2025). Trigger `sdi_phase1_pipeline` in the UI with config `{"refresh_no": 0}`, or:
   ```bash
   bash scripts/run_refresh.sh 0
   ```
5. **Double refresh.** Each refresh generates one new month (Jan 2026, then Feb 2026), then ingests, validates,
   loads it on top of the existing history and re-optimises and benchmarks the query layer:
   ```bash
   bash scripts/run_refresh.sh 1
   ```
   ```bash
   bash scripts/run_refresh.sh 2
   ```
6. **Stop Airflow:**
   ```bash
   bash scripts/stop_airflow.sh
   ```

### Where to look at the results
- **Postgres staging / ops** (`postgresql://sdi:sdi@localhost:5432/staging`): `stg_*` tables, `stg_rejects`,
  `ops_batch_load_log`, `ops_query_log`, `ops_storage_metrics`, `ops_pipeline_runs`, plus views
  `v_batch_success_rate`, `v_query_stats`, `v_daily_query_count` (dashboard sources for Milestone 2).
- **DuckDB data mart:** `data/warehouse/sdi_mart.duckdb`. Hive-partitioned Parquet copies of the facts are in `data/parquet/`.
- **Airflow UI:** Graph view of each run, with task logs and XCom return values (row counts, rejects, timings).

### macOS notes
`scripts/airflow_env.sh` sets the environment Airflow needs on macOS (`fork` start method,
`OBJC_DISABLE_INITIALIZE_FORK_SAFETY`, `PGGSSENCMODE=disable`). `setup_local.sh` also swaps the `setproctitle`
C extension for a no-op shim (`scripts/macos_shim/`): on recent macOS versions it segfaults in every forked Airflow
process. The shim only changes how process names appear in `ps`.

## Tests without Airflow
```bash
.venv/bin/python tests/test_pipeline.py
```
SQLite stands in for Postgres and DuckDB. The test covers the initial load and two refreshes, SCD Type 2,
idempotency, and checks that the base and optimised queries return the same results.

## Verified results (real dataset, Airflow 2.10.5 on macOS)
| Run | Sales loaded / rejected | Hospital rows | FactPharmacySales total | Notes |
|---|---|---|---|---|
| `refresh_no=0` (INIT) | 500,000 / 0 | 27,216 | 500,000 | 63 medicines, 60 pharmacies, 12 hospitals, 18 locations |
| `refresh_no=1` (Jan 2026) | 48,494 / 243 | 756 | 548,494 | January seasonal peak (factor 3.41) |
| `refresh_no=2` (Feb 2026) | 7,109 / 35 | 756 | 555,603 | 3 medicines get SCD Type 2 versions |

All tasks succeeded in all three runs. Batch success rate is 100%, there are 0 orphan keys and 0 failed queries,
and the base and optimised queries always returned identical results. Full numbers are in the report, section 11.
