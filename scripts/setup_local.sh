#!/usr/bin/env bash
# One-time local setup (no Docker): Python 3.11 venv with Airflow 2.10.5 + Postgres 16 databases.
# Needs: Homebrew, uv (https://docs.astral.sh/uv/).   Usage: bash scripts/setup_local.sh
set -e
cd "$(dirname "$0")/.."
AF=2.10.5; PY=3.11
CONSTRAINTS="https://raw.githubusercontent.com/apache/airflow/constraints-${AF}/constraints-${PY}.txt"

brew list postgresql@16 >/dev/null 2>&1 || brew install postgresql@16
brew services start postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
until pg_isready -q -h localhost; do sleep 1; done
psql -d postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='sdi'"     | grep -q 1 || psql -d postgres -c "CREATE ROLE sdi LOGIN PASSWORD 'sdi'"
psql -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='staging'" | grep -q 1 || psql -d postgres -c "CREATE DATABASE staging OWNER sdi"
psql -d postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='airflow'" | grep -q 1 || psql -d postgres -c "CREATE ROLE airflow LOGIN PASSWORD 'airflow'"
psql -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='airflow'" | grep -q 1 || psql -d postgres -c "CREATE DATABASE airflow OWNER airflow"

[ -d .venv ] || uv venv --python "$PY" .venv
uv pip install --python .venv/bin/python "apache-airflow[postgres]==${AF}" -r requirements.txt --constraint "$CONSTRAINTS"

if [ "$(uname)" = Darwin ]; then   # see scripts/macos_shim/setproctitle/__init__.py
  uv pip uninstall --python .venv/bin/python setproctitle >/dev/null 2>&1 || true
  SITE=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
  cp -R scripts/macos_shim/setproctitle "$SITE/"
  cp scripts/macos_shim/sitecustomize.py "$SITE/"
fi
# the sales file is stored gzipped in git (GitHub's 100 MB file limit); unpack it once
if [ ! -f data/raw/05_pharmacy_sales_data.csv ] && [ -f data/raw/05_pharmacy_sales_data.csv.gz ]; then
  gunzip -k data/raw/05_pharmacy_sales_data.csv.gz
fi
echo "Setup done. Next: bash scripts/start_airflow.sh"
