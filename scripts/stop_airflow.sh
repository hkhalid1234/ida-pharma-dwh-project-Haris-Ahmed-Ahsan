#!/usr/bin/env bash
# Stop the native Airflow scheduler + webserver started by start_airflow.sh
source "$(dirname "$0")/airflow_env.sh"
pkill -f "$PROJECT_DIR/.venv/bin/airflow" 2>/dev/null
pkill -f "gunicorn: master \[airflow-webserver\]" 2>/dev/null
sleep 2; rm -f "$AIRFLOW_HOME"/*.pid "$AIRFLOW_HOME"/*.pid.*
echo "Airflow stopped"
