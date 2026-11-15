import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(11, 5.2)); ax.set_xlim(0, 11); ax.set_ylim(0, 5.2); ax.axis("off")
def box(x, y, w, h, title, sub, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08", fc=color, ec="#333", lw=1.2))
    ax.text(x + w/2, y + h - 0.22, title, ha="center", va="top", fontsize=9, fontweight="bold")
    ax.text(x + w/2, y + h - 0.55, sub, ha="center", va="top", fontsize=7.2, color="#222", linespacing=1.35)
def arrow(x1, y1, x2, y2, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, lw=1.4, color="#444"))

y = 2.7; h = 1.9
box(0.1, y, 1.9, h, "1  Oversampling", "Python generator\n7 CSV sources\n(Phase 1: 3 files)\nAirflow TaskGroup", "#fde9d9")
box(2.3, y, 1.9, h, "2  Ingestion", "Landing zone\nfile-watcher (sensor)\nbatch loader + API\nmetrics logged", "#dbe9f6")
box(4.5, y, 1.9, h, "3  Staging / ODS", "PostgreSQL stg_*\nvalidation rules\nstg_rejects table", "#dbe9f6")
box(6.8, y, 1.9, h, "4  Transform", "SCD 1/2, junk dims\nas-of key lookup\nincremental fact load", "#e4dff0")
box(9.0, y, 1.9, h, "5  Data mart", "DuckDB star schema\n2 facts + 7 dims\n(fact constellation)", "#e4dff0")
for a, b in [(2.0, 2.3), (4.2, 4.5), (6.4, 6.8), (8.7, 9.0)]:
    arrow(a + 0.02, y + h/2, b - 0.02, y + h/2)
box(6.8, 0.5, 4.1, 1.5, "6  Analytical query layer", "indexes · pre-aggregated tables · partitioned Parquet\ninstrumented query runner (ms, rows, errors)", "#e2efd9")
arrow(9.95, y, 9.95, 2.02)
box(0.1, 0.5, 6.3, 1.5, "ops_* observability tables (Postgres)  ->  Grafana / BI (Milestone 2)", "ops_batch_load_log · ops_query_log · ops_storage_metrics · ops_pipeline_runs · stg_rejects", "#fff2cc")
arrow(6.8, 1.25, 6.42, 1.25)
ax.text(5.5, 5.0, "Orchestrated end-to-end by one Apache Airflow DAG: sdi_phase1_pipeline", ha="center", fontsize=10, fontweight="bold")
plt.savefig("architecture.png", dpi=170, bbox_inches="tight"); print("ok")
