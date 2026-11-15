#!/usr/bin/env bash
# Environment for running Airflow natively (no Docker). Usage:  source scripts/airflow_env.sh
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export AIRFLOW_HOME="$PROJECT_DIR/airflow_home"
export AIRFLOW__CORE__DAGS_FOLDER="$PROJECT_DIR/dags"
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__CORE__MP_START_METHOD=fork   # macOS defaults to spawn, which LocalExecutor workers cannot use
export AIRFLOW__CORE__EXECUTE_TASKS_NEW_PYTHON_INTERPRETER=True   # each task in a fresh interpreter (no in-process fork)
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=False
export AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=30
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT=8080
export PYTHONPATH="$PROJECT_DIR/include${PYTHONPATH:+:$PYTHONPATH}"
export SDI_DATA_DIR="$PROJECT_DIR/data"
export SDI_STAGING_DSN="postgresql://sdi:sdi@localhost:5432/staging"
# macOS: forked task processes crash without these
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export no_proxy="*"
export PGGSSENCMODE=disable   # libpq + Kerberos after fork() segfaults on macOS
export PATH="$PROJECT_DIR/.venv/bin:/opt/homebrew/opt/postgresql@16/bin:$PATH"
