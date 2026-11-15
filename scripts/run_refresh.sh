#!/usr/bin/env bash
# Trigger one pipeline run and wait for it.  Usage: scripts/run_refresh.sh <refresh_no 0|1|2>
source "$(dirname "$0")/airflow_env.sh"
N="${1:-0}"; RUN="refresh_${N}_$(date +%H%M%S)"
airflow dags trigger sdi_phase1_pipeline -r "$RUN" -c "{\"refresh_no\": $N}" >/dev/null 2>"$AIRFLOW_HOME/logs/trigger.err" \
  || { cat "$AIRFLOW_HOME/logs/trigger.err"; exit 1; }
echo "triggered $RUN"
PREV=""
while true; do
  S=$(airflow dags list-runs -d sdi_phase1_pipeline -o plain 2>/dev/null | awk -v r="$RUN" '$2==r {print $3}')
  CUR=$(airflow tasks states-for-dag-run sdi_phase1_pipeline "$RUN" -o plain 2>/dev/null \
        | awk 'NR>1 && $4!="" && $4!="None" && $4!="queued" && $4!="scheduled" {print $3" "$4}' | sort)
  comm -13 <(echo "$PREV") <(echo "$CUR") | sed "s/^/$(date +%H:%M:%S)  /"; PREV="$CUR"
  case "$S" in success|failed) break;; esac; sleep 8
done
echo "RUN $RUN -> $S"
airflow tasks states-for-dag-run sdi_phase1_pipeline "$RUN" -o plain 2>/dev/null | awk 'NR>1 {print $3, $4}'
[ "$S" = success ]
