#!/usr/bin/env bash
# Wipe all pipeline data (staging DB, DuckDB mart, Parquet, landing/archive files, DAG run history)
# so the demo can start again from the initial load. Raw CSVs in data/raw are kept.
source "$(dirname "$0")/airflow_env.sh"
cd "$PROJECT_DIR"
psql -q "$SDI_STAGING_DSN" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
rm -f data/warehouse/*.duckdb data/warehouse/*.duckdb.wal data/archive/*.csv data/incoming/*.csv
rm -rf data/parquet/Fact*
# stop unfinished runs, then drop all runs of the DAG (max_active_runs=1 would block new ones)
psql -q "postgresql://airflow:airflow@localhost:5432/airflow" -c "UPDATE task_instance SET state='failed' WHERE dag_id='sdi_phase1_pipeline' AND state NOT IN ('success','failed','skipped','upstream_failed'); UPDATE dag_run SET state='failed' WHERE dag_id='sdi_phase1_pipeline' AND state IN ('running','queued');"
airflow dags delete sdi_phase1_pipeline -y > /dev/null 2>&1 || true
airflow dags reserialize > /dev/null 2>&1 || true
echo "Pipeline reset. Next: bash scripts/run_refresh.sh 0"
