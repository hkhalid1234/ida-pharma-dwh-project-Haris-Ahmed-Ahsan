#!/usr/bin/env bash
# Init (idempotent) + start Airflow natively: scheduler + webserver on :8080. Login: admin / admin
set -e
source "$(dirname "$0")/airflow_env.sh"
mkdir -p "$AIRFLOW_HOME/logs"
pg_isready -q -h localhost || { echo "Postgres is not running: brew services start postgresql@16"; exit 1; }
airflow db migrate > "$AIRFLOW_HOME/logs/migrate.log" 2>&1
airflow users create --username admin --password admin --firstname SDI --lastname Admin \
  --role Admin --email admin@example.com > /dev/null 2>&1 || true
nohup airflow scheduler > "$AIRFLOW_HOME/logs/scheduler.out" 2>&1 &
nohup airflow webserver > "$AIRFLOW_HOME/logs/webserver.out" 2>&1 &
for i in $(seq 1 60); do
  curl -sf http://localhost:8080/health > /dev/null && { echo "Airflow is up: http://localhost:8080  (admin / admin)"; exit 0; }
  sleep 3
done
echo "Webserver did not come up in time - see $AIRFLOW_HOME/logs/webserver.out"; exit 1
