-- Views for the Grafana dashboards (Postgres). Created by scripts/create_ops_views.sh or psql manually.
CREATE OR REPLACE VIEW v_batch_success_rate AS
SELECT source_table, COUNT(*) AS attempts, SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS ok,
       100.0 * SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) / COUNT(*) AS success_rate_pct
FROM ops_batch_load_log GROUP BY source_table;

CREATE OR REPLACE VIEW v_query_stats AS
SELECT query_id, variant, COUNT(*) AS executions, AVG(duration_ms) AS avg_ms, MAX(duration_ms) AS max_ms,
       100.0 * SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) / COUNT(*) AS error_rate_pct
FROM ops_query_log GROUP BY query_id, variant;

CREATE OR REPLACE VIEW v_daily_query_count AS
SELECT CAST(executed_at AS DATE) AS day, COUNT(*) AS queries FROM ops_query_log GROUP BY 1;
