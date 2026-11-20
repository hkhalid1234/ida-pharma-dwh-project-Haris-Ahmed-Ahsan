"""Builds Milestone.1.SDI.DWH.Report.pdf (strictly max 5 pages).
Run from docs/ folder: python build_report.py
"""
import shutil
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

ss = getSampleStyleSheet()
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=8.2, leading=10.2, spaceAfter=3)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=10.5, leading=12.5, spaceBefore=5, spaceAfter=2, keepWithNext=1, textColor=colors.HexColor("#1F3864"))
T = ParagraphStyle("T", parent=B, fontSize=7.4, leading=8.8, spaceAfter=0)
TH = ParagraphStyle("TH", parent=T, textColor=colors.white, fontName="Helvetica-Bold")
CODE = ParagraphStyle("C", parent=B, fontName="Courier", fontSize=7.2, leading=8.5)
BUL = ParagraphStyle("BUL", parent=B, leftIndent=9, bulletIndent=2, spaceAfter=1)

def P(t, s=B): return Paragraph(t, s)
def bullets(items): return [Paragraph(i, BUL, bulletText="•") for i in items]
def mono(t): return f"<font face='Courier'>{t}</font>"

def table(rows, widths, header=True):
    data = [[Paragraph(str(c), TH if (header and r == 0) else T) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9AA5B1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")])]
    t.setStyle(TableStyle(st))
    return t

def footer(c, d):
    c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.grey)
    c.drawString(1.3 * cm, 0.8 * cm, "Intelligent Data Architectures | SDI Data Mart - Milestone 1 Report")
    c.drawRightString(A4[0] - 1.3 * cm, 0.8 * cm, f"Page {d.page}"); c.restoreState()

out_pdf = "../Milestone.1.SDI.DWH.Report.pdf"
doc = SimpleDocTemplate(out_pdf, pagesize=A4, leftMargin=1.3 * cm, rightMargin=1.3 * cm,
                        topMargin=1.0 * cm, bottomMargin=1.1 * cm, title="Milestone 1 SDI DWH Report")
S = []
S += [P("Sales &amp; Demand Intelligence (SDI) Data Mart",
        ParagraphStyle("t", parent=ss["Title"], fontSize=16, leading=18, textColor=colors.HexColor("#1F3864"))),
      P("Phase 1, Milestone 1: Automated Airflow Pipeline up to Query Layer with Double Refresh", ParagraphStyle("st", parent=B, fontSize=10, leading=12, alignment=1)),
      P("Course: Intelligent Data Architectures (Fall 2026) &nbsp;|&nbsp; Team: Ahsan Imran (28376), Haris Khalid, Syed Ahmed Farrukh &nbsp;|&nbsp; "
        "GitHub: github.com/hkhalid1234/ida-pharma-dwh-project-Haris-Ahmed-Ahsan",
        ParagraphStyle("m", parent=B, alignment=1, textColor=colors.grey, fontSize=8, leading=10)), Spacer(1, 3)]

# 1. Problem-solving approach for DWH
S += [P("1. Problem-Solving Approach for the DWH (Requirement d)", H1),
      P("The enterprise manufactures and distributes temperature-sensitive pharmaceuticals across chain stores, independent pharmacies, hospital pharmacies, and online channels in major US metropolitan areas. Daily transactional sales (500,000 records) and monthly hospital demand requisitions (27,216 records) were historically trapped in isolated transactional silos at differing levels of granularity. Leadership could not view actual patient consumption alongside unfulfilled hospital demand, product shelf life, or gross margin across distribution channels."),
      P("<b>Our Architectural Solution:</b> We built the Sales &amp; Demand Intelligence (SDI) data mart as a unified Kimball Fact Constellation in DuckDB, orchestrated by a centralized Apache Airflow pipeline (DAG: " + mono("sdi_phase1_pipeline") + "). The pipeline ingests source files into a PostgreSQL staging ODS, enforces strict data validation, loads dimensional tables with point-in-time Slowly Changing Dimensions (SCD Type 2), populates transactional and periodic snapshot fact tables, and provides an optimized analytical query layer. History is strictly preserved; incremental refreshes append new data without truncation."),
      P("<b>Submitted Deliverables:</b> (1) GitHub repository with modular Airflow DAG and codebase; (2) Completed design workbook (" + mono("Milestone.1.SDI.DWH.Excel.xlsx") + "); (3) This report (" + mono("Milestone.1.SDI.DWH.Report.pdf") + "); (4) Walkthrough video (" + mono("Milestone.1.SDI.DWH.Video") + " linked in README); (5) Oversampled data folder with full data dictionary.")]

# 2. Dimensional Model
S += [P("2. Dimensional Modeling &amp; Star Schema Design", H1),
      Image("star_schema.png", width=9.2 * cm, height=9.2 * cm * 1529 / 1749),
      Spacer(1, 2),
      table([["Component", "Implementation Details", "Business Justification"],
             ["FactPharmacySales", "Transactional fact. Grain: 1 row per sales transaction (product, store, day). Measures: Packs sold, net sales, discount, cost of goods, returned packs.", "Provides granular revenue, volume, and customer lineage. Retains Lot and Production Batch IDs for cold chain traceability."],
             ["FactHospitalDemand", "Periodic snapshot fact. Grain: 1 row per hospital x product x month. Measures: Forecast, requested, consumed, unfulfilled packs, closing stock.", "Reconciles demand forecasting with clinical fulfillment. Closing stock is semi-additive across facilities but not across time."],
             ["DimMedicine", "Conformed product dimension (63 medicines). Attributes: Generic name, brand, therapeutic class, pack size, prescription class, cold chain flag.", "Implements SCD Type 2 on PackSize and PrescriptionClass with EffectiveFromDate, EffectiveToDate, and IsCurrent flag."],
             ["DimDate & Location", "DimDate role-plays for sales date, delivery date, and demand month. DimLocation is an outrigger shared by pharmacies and hospitals.", "Ensures consistent temporal and geographic rollups across both retail sales and institutional demand."],
             ["Junk Dimensions", "DimSalesJunk (channel, customer segment, payer, payment, promo, Rx flag) and DimDemandJunk (request status, formulary status).", "Removes low-cardinality flags and text statuses from high-volume fact tables, drastically shrinking fact row width."]],
            [3.2, 8.8, 6.4])]

# 3. Oversampling Strategy
S += [P("3. Data Oversampling Strategy &amp; Statistics (Requirement e)", H1),
      P("To simulate a live 24/7 automated pipeline, we developed a Python data generator (" + mono("include/sdi/generator.py") + ") that synthesizes new monthly batch files for all Phase 1 sources. Each refresh represents one new chronological month, appending new data to the warehouse while preserving historical lineage."),
      *bullets([
          "<b>Refresh 1 (R01 - Jan 2026):</b> Historical sales show a massive seasonal surge in January (winter respiratory peak). The generator preserves this seasonality, applying a 3.41 seasonal multiplier and 1.03 annual growth factor to historical January distributions, generating 48,737 sales rows.",
          "<b>Refresh 2 (R02 - Feb 2026):</b> February historical sales drop significantly. Applying a 0.46 seasonal multiplier yields 7,144 sales rows. In addition, 3 medicines (" + mono("MED014") + ", " + mono("MED023") + ", " + mono("MED058") + ") undergo pack size and prescription class changes to trigger SCD Type 2 logic.",
          "<b>Hospital Demand Grid:</b> Exactly 756 records per month (12 hospitals x 63 medicines) with stochastic Gaussian noise (~6%) applied to forecast, requested, and consumed quantities. Unfulfilled demand is mathematically constrained never to exceed requested packs.",
          "<b>Deliberate Dirt Injection:</b> To test staging validation, 0.5% of generated sales rows are corrupted with negative quantities, missing medicine IDs, or impossible calendar dates."]),
      table([["Source Domain", "Baseline History (2023-2025)", "Refresh 1 (Jan 2026)", "Refresh 2 (Feb 2026)", "Oversampling Methodology"],
             ["Pharmacy Sales", "500,000 rows (36 months)", "48,737 rows (factor 3.41)", "7,144 rows (factor 0.46)", "Bootstrapped from same-month historical transactions with price/margin preservation."],
             ["Hospital Demand", "27,216 rows (12x63x36)", "756 rows", "756 rows", "Full matrix of facilities x medicines with stochastic fulfillment variance."],
             ["Master Data", "63 active medicines", "0 modified rows", "3 modified rows (SCD-2)", "Injects regulatory pack size updates to test dimension versioning."]],
            [2.8, 3.6, 3.6, 3.6, 4.8])]

# 4. Design of Airflow pipeline
S += [P("4. Design of the Airflow Pipeline &amp; Ingestion (Requirement a)", H1),
      Image("architecture.png", width=14.5 * cm, height=14.5 * cm * 0.4856),
      Spacer(1, 2),
      P(mono("init_infra &gt; choose_path &gt; [seed_historical | oversampling] &gt; wait_for_files &gt; ingestion &gt; validate_data &gt; transform_load &gt; query_layer &gt; storage_metrics &gt; end"),
        ParagraphStyle("c", parent=CODE, fontSize=7.4)),
      *bullets([
          "<b>Modular Architecture:</b> The DAG file (" + mono("dags/sdi_phase1_dag.py") + ") purely handles orchestration and task dependencies. All business logic is strictly encapsulated within the " + mono("sdi") + " Python package.",
          "<b>Execution Branching:</b> The DAG accepts parameter " + mono("refresh_no") + ". When 0, it seeds baseline CSVs; when 1 or 2, it branches to the oversampling generator task group.",
          "<b>File-Watcher &amp; Ingestion:</b> An Airflow " + mono("PythonSensor") + " monitors " + mono("data/incoming/") + " with a 2-second file-size stabilization window to ensure completely written files. A standalone script and FastAPI endpoint (" + mono("api/ingest_api.py") + ") offer external ingestion triggers. Staging uses PostgreSQL COPY for maximum throughput, moving processed files to " + mono("data/archive/") + ".",
          "<b>Data Quality &amp; Rejection:</b> Staging validation catches null keys, non-positive prices/quantities, and duplicate transaction IDs. Rejected rows are routed to " + mono("stg_rejects") + " with specific rule codes, leaving the warehouse unpolluted.",
          "<b>Idempotent Loading:</b> The " + mono("EtlBatchLog") + " tracks processed batch IDs. If an execution is re-triggered, already transformed batches are skipped automatically."])]

# 5. Implementation problems faced
S += [P("5. Implementation Problems Faced and Solutions (Requirement b)", H1),
      table([["Challenge / Problem Faced", "Root Cause Analysis", "Engineered Solution"],
             ["Worker Process Deadlocks &amp; Segfaults on macOS", "Python 3.11 default 'spawn' on macOS, fork-safety crashes with setproctitle, and pre-fork imports of native C-extensions (numpy/pandas).", "Implemented a no-op shim for setproctitle, configured fork-safe environment flags in scripts/airflow_env.sh, and deferred heavy library imports until task execution."],
             ["Historical Sales Key Mutation on SCD Type 2 Updates", "Initial transform logic performed natural key lookups against current dimension records (IsCurrent='Y'), which would rewrite historical sales attribution.", "Re-engineered transformation to perform point-in-time 'as-of' lookups matching SalesDate between EffectiveFromDate and EffectiveToDate."],
             ["DuckDB SmallInt Overflow in Pre-Aggregation", "DuckDB stores Year as SMALLINT; Year * 100 in the pre-aggregation script overflowed the 16-bit integer boundary.", "Explicitly cast Year to INTEGER (CAST(Year AS INTEGER) * 100 + MonthNumber) in aggregate DDL."],
             ["Cross-Platform Date Formatting Failures", "Unit tests used POSIX-only '%-m' date formatting in strftime, raising ValueError on Windows environments.", "Engineered an OS-agnostic helper extracting date components dynamically via pandas datetime series, guaranteeing 100% portability."]],
            [4.6, 6.8, 7.0])]

# 6. Explanation of data engineering dashboards
S += [P("6. Explanation of Data Engineering Observability Dashboards (Requirement c)", H1),
      P("To monitor pipeline reliability, data quality, and query performance in real time (feeding Grafana and Milestone 2 BI tools), our staging and query layers continuously log observability metrics into dedicated PostgreSQL tables:"),
      table([["Dashboard Domain", "Underlying Table / View", "Tracked Metrics &amp; Computation", "Analytical Purpose &amp; Story Told"],
             ["Batch Ingestion", "ops_batch_load_log<br/>v_batch_success_rate", "Batch Load Duration (seconds), Rows Loaded, Batch Success Rate (100.0 * ok / total).", "Identifies file ingestion bottlenecks and guarantees zero unhandled pipeline failures across source domains."],
             ["Data Validation &amp; Quality", "stg_rejects", "Rejection counts grouped by rule (e.g. quantity_positive, price_positive, sku_not_null).", "Monitors source data quality trends, proving that corrupted records are caught before contaminating OLAP facts."],
             ["Storage &amp; Staging Footprint", "ops_storage_metrics", "Table row counts, PostgreSQL ODS size (MB), DuckDB file size, Parquet directory size, Date span.", "Tracks warehouse storage consumption over time and confirms full historical temporal coverage (2023 to 2026)."],
             ["Query Optimization &amp; Latency", "ops_query_log<br/>v_query_stats", "Query execution duration (ms), executed query counts, error rates, base vs. opt performance.", "Surfaces slow analytical queries, monitors dashboard visual response times, and validates index/aggregate efficiency."]],
            [3.2, 3.8, 5.4, 6.0])]

# 7. Analytical Query Layer & Results
S += [P("7. Analytical Query Layer, Optimization &amp; Benchmark Results", H1),
      P("We implemented all 3 stakeholder queries from our design workbook (Q1 regional sales, Q2 hospital forecast vs. actual, Q3 unfulfilled hospital demand vs. store sales) and 3 dashboard KPIs (K4 channel margin, K5 fast movers, K6 service level). Every query is implemented in two variants: a <b>base</b> multi-fact star join and an <b>opt</b> variant utilizing pre-aggregated summary tables (" + mono("AggSalesMonthly") + ", " + mono("AggDemandMonthly") + ") and compound B-tree indexes. On every run, the benchmark suite programmatically verifies that both variants yield identical result sets."),
      table([["Query Identifier &amp; Business Target", "Base Fact Join (ms)", "Optimized Pre-Aggregate (ms)", "Performance Gain", "Optimization Analysis"],
             ["Q1: Net sales and packs by region, month &amp; channel (2025)", "4.93 ms", "3.28 ms", "33% faster", "AggSalesMonthly reduces scanned rows from 555,603 to 31,000."],
             ["Q2: Hospital forecast vs actual by category &amp; quarter", "2.35 ms", "4.35 ms", "Join overhead", "AggDemandMonthly has identical grain to fact; extra join adds slight latency."],
             ["Q3: Unfulfilled hospital demand vs store sales by city", "7.20 ms", "4.57 ms", "37% faster", "Correlated subquery scan accelerated significantly by summary table."],
             ["K4: Channel revenue split &amp; gross margin percentage", "3.75 ms", "2.85 ms", "24% faster", "Pre-computed net sales and COGS eliminates fact table aggregation."],
             ["K5: Top 10 fast-moving medicines by therapeutic class", "7.15 ms", "3.14 ms", "56% faster", "Compound index on AggSalesMonthly (Year, LocationKey) provides instant grouping."],
             ["K6: Hospital fulfillment service level percentage", "1.32 ms", "2.79 ms", "Sub-second", "Direct fact scan remains faster due to DuckDB's in-memory columnar vectorization."]],
            [5.4, 3.0, 3.2, 2.6, 4.2]),
      Spacer(1, 2),
      P("<b>Empirical Pipeline Verification:</b> Across initial load and both refreshes, 100% of tasks succeeded (0 orphan keys, 100% batch success rate). Warehouse totals reached 555,603 rows in FactPharmacySales and 28,728 rows in FactHospitalDemand. All baseline and optimized queries returned identical answers across 108 test executions.")]

doc.build(S, onFirstPage=footer, onLaterPages=footer)
shutil.copy(out_pdf, "../SDI_Phase1_Milestone1_Report.pdf")
print("Report built successfully at", out_pdf)
