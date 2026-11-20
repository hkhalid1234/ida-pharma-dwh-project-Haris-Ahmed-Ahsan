"""Phase 1 - Sales & Demand Intelligence (SDI) data mart.   Milestone 1: pipeline up to the query layer.

  choose_path --(refresh_no = 0)--> seed_historical ------------------------------\\
              \\--(refresh_no = 1,2)--> oversampling[sales|hospital|master] ---------+--> wait_for_files
  wait_for_files -> ingestion[master|sales|hospital] -> validate -> transform_load
                 -> query_layer[optimise -> benchmark] -> storage_metrics -> end

Trigger with config {"refresh_no": 0}  (initial historical load),  then 1, then 2 (refreshes).
All business logic lives in include/sdi/*; this file only wires tasks together (modular DAG).
"""
import json
import shutil
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, get_current_context
from airflow.sensors.python import PythonSensor
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

from airflow.utils.dag_parsing_context import get_parsing_context


# The sdi package pulls in pandas, numpy and duckdb. The scheduler's DAG-file processor only needs the DAG
# structure, so it does not import them (faster parsing; on macOS the forked processor segfaults loading them).
# When Airflow runs a task, the package is imported here, before the task runner forks the task process,
# because importing native libraries after that fork can deadlock.
def _sdi():
    from sdi import config, generator, ingestion, query_layer, transform, validation
    from sdi.db import Db
    from sdi.warehouse import DuckWarehouse
    return config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse


if get_parsing_context().dag_id is not None:   # set only while `airflow tasks run` loads this file
    _sdi()

DEFAULT_ARGS = {"owner": "sdi-team", "retries": 2, "retry_delay": timedelta(seconds=30)}


def _batch_id() -> str:
    n = int(get_current_context()["params"]["refresh_no"])
    return "INIT" if n == 0 else f"R{n:02d}"


def _log_stage(db, stage: str, status: str, detail) -> None:
    from sdi import ingestion
    ctx = get_current_context()
    db.execute("INSERT INTO ops_pipeline_runs VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
               (ctx["run_id"], int(ctx["params"]["refresh_no"]), stage, status, json.dumps(detail, default=str)[:2000],
                ingestion.now()))


@dag(dag_id="sdi_phase1_pipeline", start_date=datetime(2026, 11, 1), schedule=None, catchup=False,
     default_args=DEFAULT_ARGS, max_active_runs=1, tags=["phase1", "sdi", "idata"],
     params={"refresh_no": Param(0, type="integer", minimum=0, maximum=2,
                                 description="0 = initial historical load, 1/2 = oversampled refresh")})
def sdi_phase1_pipeline():

    @task
    def init_infrastructure():
        config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
        db = Db(config.STAGING_DSN)
        ingestion.ensure_ops_tables(db)
        db.script((config.SQL_DIR / "ops_views.sql").read_text(encoding="utf-8"))   # dashboard views (Grafana, Milestone 2)
        wh = DuckWarehouse(config.DUCKDB_PATH); wh.ensure_schema(); wh.close()
        for d in (config.INCOMING_DIR, config.ARCHIVE_DIR, config.PARQUET_DIR):
            d.mkdir(parents=True, exist_ok=True)
        db.close()

    def _choose(**ctx):
        if int(ctx["params"]["refresh_no"]) == 0:
            return "seed_historical"
        return ["oversampling.generate_sales", "oversampling.generate_hospital", "oversampling.generate_master"]

    choose_path = BranchPythonOperator(task_id="choose_path", python_callable=_choose)

    @task
    def seed_historical():
        """Initial load: drop the original CSVs into the landing zone as batch INIT."""
        config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
        for stem in config.SOURCES:
            shutil.copy(config.RAW_DIR / f"{stem}.csv", config.INCOMING_DIR / f"{stem}__INIT.csv")

    # ---------------------------------------------------------------- oversampling layer
    with TaskGroup("oversampling") as oversampling:
        def _gen(stem):
            config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
            n = int(get_current_context()["params"]["refresh_no"])
            st = generator.generate_one(stem, config.RAW_DIR, config.INCOMING_DIR, n)
            db = Db(config.STAGING_DSN); _log_stage(db, f"generate:{stem}", "success", st); db.close()
            return st

        @task
        def generate_sales():
            return _gen("05_pharmacy_sales_data")

        @task
        def generate_hospital():
            return _gen("06_hospital_demand_data")

        @task
        def generate_master():
            return _gen("01_master_data")

        [generate_sales(), generate_hospital(), generate_master()]

    # ---------------------------------------------------------------- file-watcher
    def _files_ready() -> bool:
        config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
        batch = _batch_id()
        db = Db(config.STAGING_DSN)
        try:
            return ingestion.batch_already_ingested(db, batch) or ingestion.expected_files_present(config.INCOMING_DIR, batch)
        finally:
            db.close()

    wait_for_files = PythonSensor(task_id="wait_for_files", python_callable=_files_ready, poke_interval=5, timeout=600,
                                  mode="reschedule", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    # ---------------------------------------------------------------- ingestion layer (Postgres staging)
    with TaskGroup("ingestion") as ingestion_group:
        def _ingest(stem):
            config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
            db = Db(config.STAGING_DSN)
            try:
                res = ingestion.ingest_pending(db, config.INCOMING_DIR, _batch_id(), config.ARCHIVE_DIR, stem=stem)
                _log_stage(db, f"ingest:{stem}", "success", res)
                return res
            finally:
                db.close()

        @task
        def ingest_master():
            return _ingest("01_master_data")

        @task
        def ingest_sales():
            return _ingest("05_pharmacy_sales_data")

        @task
        def ingest_hospital():
            return _ingest("06_hospital_demand_data")

        [ingest_master(), ingest_sales(), ingest_hospital()]

    @task
    def validate_data():
        config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
        db = Db(config.STAGING_DSN)
        try:
            summary = validation.validate_batch(db, _batch_id())
            _log_stage(db, "validate", "success", summary)
            return summary
        finally:
            db.close()

    @task
    def transform_load():
        config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
        db, wh = Db(config.STAGING_DSN), DuckWarehouse(config.DUCKDB_PATH)
        try:
            res = transform.run_transform(db, wh, _batch_id())
            _log_stage(db, "transform_load", "success", res)
            return res
        finally:
            wh.close(); db.close()

    # ---------------------------------------------------------------- analytical query layer
    with TaskGroup("query_layer") as query_group:
        @task
        def optimise():
            config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
            wh = DuckWarehouse(config.DUCKDB_PATH)
            try:
                return query_layer.optimise(wh, config.PARQUET_DIR)
            finally:
                wh.close()

        @task
        def benchmark():
            config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
            db, wh = Db(config.STAGING_DSN), DuckWarehouse(config.DUCKDB_PATH)
            try:
                res = query_layer.run_benchmark(wh, db, get_current_context()["run_id"])
                _log_stage(db, "benchmark", "success", res)
                if res["mismatches"]:
                    raise ValueError(f"base and optimised queries disagree: {res['mismatches']}")
                return res
            finally:
                wh.close(); db.close()

        optimise() >> benchmark()

    @task
    def storage_metrics():
        config, generator, ingestion, query_layer, transform, validation, Db, DuckWarehouse = _sdi()
        db, wh = Db(config.STAGING_DSN), DuckWarehouse(config.DUCKDB_PATH)
        try:
            return query_layer.collect_storage_metrics(db, wh, config.DUCKDB_PATH, config.PARQUET_DIR)
        finally:
            wh.close(); db.close()

    end = EmptyOperator(task_id="end")

    seed = seed_historical()
    init_infrastructure() >> choose_path >> [seed, oversampling]
    [seed, oversampling] >> wait_for_files >> ingestion_group >> validate_data() >> transform_load() \
        >> query_group >> storage_metrics() >> end


sdi_phase1_pipeline()
