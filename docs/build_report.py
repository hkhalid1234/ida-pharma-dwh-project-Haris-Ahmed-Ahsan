"""Builds SDI_Phase1_Milestone1_Report.pdf (run from the docs/ folder: python build_report.py)."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

ss = getSampleStyleSheet()
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=9.5, leading=13, spaceAfter=5)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=14, spaceBefore=10, spaceAfter=5, keepWithNext=1, textColor=colors.HexColor("#1F3864"))
T = ParagraphStyle("T", parent=B, fontSize=8.3, leading=10.5, spaceAfter=0)
TH = ParagraphStyle("TH", parent=T, textColor=colors.white, fontName="Helvetica-Bold")
CODE = ParagraphStyle("C", parent=B, fontName="Courier", fontSize=8, leading=10)
BUL = ParagraphStyle("BUL", parent=B, leftIndent=12, bulletIndent=2, spaceAfter=2)


def P(t, s=B): return Paragraph(t, s)
def bullets(items): return [Paragraph(i, BUL, bulletText="•") for i in items]
def mono(t): return f"<font face='Courier'>{t}</font>"


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), TH if (header and r == 0) else T) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA5B1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")])]
    t.setStyle(TableStyle(st))
    return t


def footer(c, d):
    c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(colors.grey)
    c.drawString(2 * cm, 1.1 * cm, "Intelligent Data Architectures, Phase 1 (SDI Data Mart), Milestone 1 report")
    c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Page {d.page}"); c.restoreState()


doc = SimpleDocTemplate("../SDI_Phase1_Milestone1_Report.pdf", pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                        topMargin=1.8 * cm, bottomMargin=1.8 * cm, title="SDI Data Mart Milestone 1 Report")
S = []
S += [P("Sales &amp; Demand Intelligence (SDI) Data Mart",
        ParagraphStyle("t", parent=ss["Title"], fontSize=21, textColor=colors.HexColor("#1F3864"))),
      P("Phase 1, Milestone 1: Airflow pipeline up to the query layer", ParagraphStyle("st", parent=B, fontSize=12, alignment=1)),
      P("Intelligent Data Architectures, Fall 2026 &nbsp;|&nbsp; Team: Ahsan Imran, Haris Khalid, Syed Ahmed Farrukh &nbsp;|&nbsp; "
        "GitHub: github.com/hkhalid1234/ida-pharma-dwh-project-Haris-Ahmed-Ahsan",
        ParagraphStyle("m", parent=B, alignment=1, textColor=colors.grey)), Spacer(1, 6)]

# ------------------------------------------------------------------ 1
S += [P("1. What we built", H1),
      P("For Phase 1 we built the Sales and Demand Intelligence (SDI) data mart, which is the first of the three marts in the project. "
        "Everything runs as one Apache Airflow DAG called " + mono("sdi_phase1_pipeline") + ". It covers all the layers we need for Milestone 1: "
        "generating new data (oversampling), picking up files with a file watcher, loading them into a PostgreSQL staging area, "
        "checking data quality, transforming the data into a star schema in DuckDB, and finally a query layer where we optimise and time our queries."),
      P("The pipeline only ever adds data. The first run loads the 2023 to 2025 history from the CSV files. After that, each refresh run "
        "generates one new month and puts it on top of what is already in the warehouse, so nothing is deleted and we keep the full history. "
        "We ran the first load and both refreshes on the real dataset and all three runs finished without any failed task. The numbers are in section 11."),
      P("<b>What we are submitting:</b> the GitHub repository with all the code, the Excel design workbook (" + mono("docs/SDI_DWH_Design_Phase1.xlsx") +
        "), this report, and a demo video <i>[add link]</i>. The BI dashboards come in Milestone 2, but the tables that will feed them are already filled by this pipeline.")]

# ------------------------------------------------------------------ 2
S += [P("2. The business problem", H1),
      P("The company sells medicines through chain pharmacies, independent pharmacies, hospital pharmacies and an online store. "
        "Sales are recorded per transaction (500,000 rows), while hospitals send a separate monthly report of what they forecast, asked for, used and did not get. "
        "Because these sit in different files at different levels of detail, nobody can see real demand next to what was actually supplied. "
        "Our stakeholders (CEO, CFO, CMO, COO and the Supply Chain Manager) want net sales, margin, a channel comparison, forecast accuracy and unfulfilled demand in one place."),
      P("Phase 1 uses three of the seven source files: " + mono("01_master_data") + " (63 medicines), " + mono("05_pharmacy_sales_data") +
        " (500,000 sales) and " + mono("06_hospital_demand_data") + " (27,216 monthly records). The other four files belong to Phases 2 and 3. "
        "The Business.Req.XRay and OLTP.XRay sheets of our workbook list every KPI and show which source column goes where."),
      P("In the workbook we picked three questions the mart has to answer:"),
      *bullets(["<b>Q1:</b> net sales and packs sold per region and month in 2025, split by in store and online.",
                "<b>Q2:</b> how close forecast demand was to what hospitals actually used, per product category and quarter.",
                "<b>Q3:</b> which cities and products had the most unfulfilled hospital demand, and how store sales of the same products looked in those cities."]),
      P("We also added three KPIs that we plan to show on the dashboards: <b>K4</b> revenue and gross margin per channel, "
        "<b>K5</b> the top 10 fast moving medicines by therapeutic class, and <b>K6</b> service level per hospital.")]

# ------------------------------------------------------------------ 3
S += [P("3. Architecture and tools", H1),
      Image("architecture.png", width=17 * cm, height=17 * cm * 0.4856),
      Spacer(1, 4),
      table([["Layer", "Tool", "Why we chose it"],
             ["Orchestration", "Apache Airflow 2.10.5", "Required by the course. One DAG with task groups. A parameter tells the same DAG whether to do the first load or a refresh. We run it directly on our laptop with the LocalExecutor, no Docker."],
             ["Staging (ODS)", "PostgreSQL 16", "Required by the course. Good for raw append-only staging tables and for the ops_* tables that log our pipeline metrics."],
             ["Data mart", "DuckDB 1.1", "Suggested by the instructor for OLAP. It is a columnar database in a single file, so star joins and group-bys are fast and we do not need a server."],
             ["Transformation", "Python (pandas) and SQL", "The SCD logic and key lookups are easier to write and test in Python. The SQL is kept standard so the same scripts run on DuckDB and on SQLite in our tests."],
             ["Dashboards", "Grafana (Milestone 2)", "The data source is already set up and will read the ops_* tables."]],
            [3.0, 3.6, 10.4])]

# ------------------------------------------------------------------ 4
S += [P("4. How we generate new data (oversampling)", H1),
      P("To act like a live system we need new data arriving, so we wrote a Python generator that makes new batch files for the three sources. "
        "In Airflow this is a task group with one task per source. It only runs when " + mono("refresh_no") + " is 1 or 2. For the first load a branch skips it."),
      P("<b>How it works:</b>"),
      *bullets([
          "<b>One refresh is one new month.</b> Refresh 1 is January 2026 and refresh 2 is February 2026. We picked a month because the hospital data is monthly and the dashboards show monthly trends.",
          "<b>Sales:</b> number of rows = average rows per month in the history x a growth factor (1.03, then 1.05) x the seasonality of that month. "
          "Seasonality is how big that calendar month was in earlier years compared to an average month. We copy random rows from the same month in earlier years and then change them a bit: "
          "the quantity is multiplied by a random factor around 1, the amounts are scaled the same way so the price and margin still make sense, and the dates are moved into the new month.",
          "<b>Hospital demand:</b> we take the same 756 hospital and medicine pairs (12 x 63) for the new month and add about 6% random noise to forecast, requested, consumed and closing stock. Unfulfilled demand can never be more than what was requested.",
          "<b>Master data:</b> nothing changes in refresh 1. In refresh 2 three medicines get a new pack size and prescription class, so we can show that SCD Type 2 works.",
          "<b>IDs</b> continue from the last ID in the history, so they never clash. Each refresh uses a fixed random seed, so running it again gives the same data.",
          "<b>Some bad rows on purpose:</b> 0.5% of the new sales rows are broken (negative quantity, missing medicine ID or an impossible date) so that the validation step has something to catch.",
      ]),
      table([["Source", "History", "Refresh 1 (Jan 2026)", "Refresh 2 (Feb 2026)", "Reason"],
             ["Pharmacy sales", "500,000 rows (36 months)", "48,737 rows (season factor 3.41)", "7,144 rows (season factor 0.46)",
              "The real data has a big January peak (46,804 sales in Jan 2024 and 95,144 in Jan 2025) and a quiet February (11,184 and 7,773). Our generator follows that, so January is large and February is small."],
             ["Hospital demand", "27,216 rows (12 x 63 x 36)", "756 rows", "756 rows", "Exactly one month of the full hospital x medicine grid."],
             ["Master data", "63 rows", "0 rows", "3 changed rows", "Product changes are rare, and three are enough to show SCD Type 2."]],
            [2.6, 2.8, 3.0, 3.0, 5.6]),
      Spacer(1, 3),
      P("These are the actual counts from our two refresh runs (logged in ops_pipeline_runs). Together the two refreshes add about 11% to the sales history and about 6% to the hospital history, "
        "which is enough to move the monthly numbers on a dashboard but still loads in under a minute.")]

# ------------------------------------------------------------------ 5
S += [P("5. Ingestion", H1),
      P("New files are dropped into " + mono("data/incoming") + " with the name " + mono("&lt;source&gt;__&lt;batch&gt;.csv") +
        ", where the batch is INIT, R01 or R02. Our file watcher is an Airflow PythonSensor. It only picks up a file when the name matches one of our sources and the file has not changed "
        "for two seconds, so we never read a half-written file. We also wrote a stand-alone watcher (" + mono("scripts/run_watcher.py") +
        ") and a small FastAPI endpoint (" + mono("api/ingest_api.py") + ") that do the same thing outside Airflow."),
      P("The loader reads each file with pandas, keeps every column as text, adds batch_id, source_file and loaded_at, and copies it into Postgres with COPY because that is much faster than inserts. "
        "After a successful load the file is moved to " + mono("data/archive") + "."),
      *bullets(["For every file we log the load time in seconds, the number of rows and whether it worked, in " + mono("ops_batch_load_log") +
                ". The success rate is successful loads / all loads x 100 (view v_batch_success_rate).",
                "If a file was already loaded we skip it, so running the DAG again never loads the same data twice.",
                "If a new column shows up in a source file we add it to the staging table instead of crashing.",
                "If one file fails the others still load. The failure is logged and the task fails so Airflow retries it (2 retries, 30 seconds apart)."])]

# ------------------------------------------------------------------ 6
S += [P("6. Staging and data validation", H1),
      P("The staging tables (stg_master_data, stg_pharmacy_sales, stg_hospital_demand) keep every batch. Before anything goes into the warehouse it has to pass our validation rules. "
        "Rows that fail are written to " + mono("stg_rejects") + " together with the rule they broke. We never just drop them, and they are not loaded into the warehouse."),
      table([["Source", "Rules"],
             ["Sales", "Medicine ID is not empty, pharmacy ID is not empty, sales date is a real date, quantity &gt; 0, net sales amount &gt; 0 (this is the \"price &gt; 0\" rule from the brief), no duplicate transaction ID in the batch"],
             ["Hospital demand", "Medicine ID and hospital ID are not empty, demand month is a real date, requested quantity &gt;= 0, no duplicate record ID in the batch"],
             ["Master data", "Medicine ID is not empty, pack size &gt; 0, no duplicate medicine ID in the batch"],
             ["Warehouse load", "If a row's medicine, pharmacy or hospital cannot be found it is rejected as orphan_dimension_key. Rows already in the fact table are skipped."]],
            [3.2, 13.8]),
      P("The original 500,000 sales rows passed every rule, so in our runs only the rows we broke on purpose were rejected. "
        "After every run we also save storage numbers (row counts, size of the Postgres database and DuckDB file, first and last date in the facts, size of the Parquet files) in " + mono("ops_storage_metrics") + ".")]

# ------------------------------------------------------------------ 7
S += [P("7. The dimensional model", H1),
      P("We followed the design in our workbook. There are two fact tables that share the same dimensions, so in Phases 2 and 3 we can attach new facts to the same DimMedicine and DimDate and end up with a fact constellation."),
      Image("star_schema.png", width=11.3 * cm, height=11.3 * cm * 1529 / 1749),
      table([["Part of the design", "What we did"],
             ["Fact tables", "FactPharmacySales is a <b>transactional</b> fact with one row per sale (product, store, day). FactHospitalDemand is a <b>periodic snapshot</b> with one row per hospital, product and month. "
              "ClosingStockPacks is <b>semi-additive</b>: you can add it across hospitals and products but not across months."],
             ["Measures", "Sales: packs, net sales, discount, cost of goods and returned packs, all fully additive. Gross sales, margin, unit price and service level are calculated in the queries instead of being stored."],
             ["Slowly changing dimensions", "DimMedicine, DimPharmacy and DimHospital have EffectiveFromDate, EffectiveToDate (9999-12-31 means still open) and IsCurrent. "
              "When a Type 2 column changes (for example pack size, prescription class, pharmacy type or location) we close the old row and add a new row with a new key. "
              "Type 1 columns (names, GTIN, bed counts) are just overwritten. Type 0 keys never change."],
             ["Junk dimensions", "DimSalesJunk holds the small flags from the sales file (channel, customer segment, payer, payment method, promotion, prescription flag, return flag, sale status, online delivery status and expiry band). "
              "DimDemandJunk holds the two hospital status columns. This keeps those flags off the fact tables."],
             ["Role playing and outrigger", "DimDate is used three times: sales date, delivery date and demand month. DimLocation is shared by DimPharmacy and DimHospital (Country, Region, State, City)."],
             ["Degenerate dimensions", "Transaction, order, delivery, prescription, lot and production batch IDs stay on the sales fact so we can trace a sale back. We will need these again in Phase 3."],
             ["Key lookup", "When we load a fact row we look up the dimension version that was valid <b>on the date of the sale</b>, not just the current one. That way an old sale stays with the old version of the product."]],
            [3.4, 13.6]),
      P("<b>Small changes compared to the first version of the workbook:</b> the Transform.OLTP sheet first said \"look up the current row\". With Type 2 history that would move old sales to the new version, "
        "so we changed it to the as-of lookup above. We also made DimDate run until 31 December 2026 because our two refresh months are in 2026. Both changes are now in the workbook as well.")]

# ------------------------------------------------------------------ 8
S += [P("8. Query layer and optimisation", H1),
      P("All stakeholder queries are plain SQL in " + mono("include/sdi/sql/queries.sql") + ". We wrote each query twice: a <b>base</b> version that joins the big fact tables directly, "
        "and an <b>opt</b> version that uses our summary tables. On every run the pipeline checks that both versions give exactly the same result."),
      table([["Technique", "What we did"],
             ["Indexes", "Indexes on the fact foreign keys and date keys, a combined index on (MonthDateKey, HospitalKey, MedicineKey), and indexes on the summary tables. "
              "We drop them before loading and build them again afterwards, which is faster than updating them row by row."],
             ["Summary tables", "AggSalesMonthly (month, location, medicine, channel) and AggDemandMonthly (month, hospital, medicine). All six queries can be answered from them. "
              "DuckDB has no materialised views, so we rebuild these tables after every load instead."],
             ["Partitioning", "DuckDB does not support table partitions, so we also export the facts as Parquet files split by year and month (year=/month= folders). A query that only needs one month then only has to read that folder."],
             ["Timing queries", "Every query is wrapped in a timer and logged in ops_query_log with the time in milliseconds, number of rows and any error. "
              "From this we get the time per query, the number of queries per day and the error rate (failed / total x 100)."]],
            [3.2, 13.8])]

# ------------------------------------------------------------------ 9
S += [P("9. How the Airflow DAG is set up", H1),
      P(mono("init_infrastructure &gt; choose_path &gt; [seed_historical or oversampling (3 tasks)] &gt; wait_for_files &gt; ingestion (3 tasks) &gt; validate_data &gt; transform_load &gt; query_layer (optimise &gt; benchmark) &gt; storage_metrics &gt; end"),
        ParagraphStyle("c", parent=CODE, fontSize=8.2)),
      *bullets(["<b>Parameter:</b> " + mono("refresh_no") + " = 0 means first load of the history, 1 and 2 are the refreshes. "
                "The DAG file only connects the tasks. All the real work is in our " + mono("sdi") + " Python package (generator, ingestion, validation, transform, query_layer), "
                "which keeps the DAG short and lets us test the logic without Airflow.",
                "<b>Branching:</b> for the first load the generator tasks are skipped. The tasks after the branch use the trigger rule none_failed_min_one_success so the skipped branch does not block them.",
                "<b>Safe to re-run:</b> files that were already loaded are skipped, batches that were already transformed are skipped (EtlBatchLog), and rows already in a fact table are not inserted again.",
                "<b>Reliability:</b> 2 retries with a 30 second wait, only one run at a time, and the sensor uses reschedule mode so it does not block a worker while it waits."]),
      P("<b>How to run it:</b> run " + mono("bash scripts/setup_local.sh") + " once (installs Postgres 16 with Homebrew and a Python 3.11 environment with Airflow), then " +
        mono("bash scripts/start_airflow.sh") + " to start Airflow on port 8080. Trigger the DAG with {\"refresh_no\": 0} for the first load, then {\"refresh_no\": 1} and {\"refresh_no\": 2} "
        "for the refreshes, or use " + mono("bash scripts/run_refresh.sh N") + ". " + mono("bash scripts/reset_pipeline.sh") + " clears everything so the demo can start again. More details are in README.md."),
      P("<b>Problems we had on macOS:</b> getting Airflow to run natively on a Mac took some work. Its worker processes kept crashing or hanging. "
        "The causes were the setproctitle library crashing after a fork, Python using \"spawn\" instead of \"fork\" on macOS, and pandas/numpy being imported after a fork. "
        "We fixed this with settings in " + mono("scripts/airflow_env.sh") + ", a small replacement for setproctitle, and by only importing our heavy libraries when a task actually runs. "
        "The setup script does all of this automatically.")]

# ------------------------------------------------------------------ 10
S += [P("10. Assumptions", H1),
      *bullets([
          "The dataset came as CSV files, so we load CSV. We read \"Excel files\" in the brief as \"table files\". Dates in the CSVs are YYYY-MM-DD, but our parser also accepts M/D/YYYY.",
          "Phase 1 only uses files 01, 05 and 06. Files 02, 03, 04 and 07 are for Phases 2 and 3. Adding them later just means adding an entry to config.SOURCES and to the generator.",
          "When we first profiled the data in Excel the GLN location codes showed up as 9.506E+11, so the workbook said to keep them empty. The actual CSV files have the full 13 digit codes, "
          "so we load PharmacyGLN and HospitalGLN as text with the leading zero. Anything that is not 12 or 13 digits becomes NULL. GTIN14 comes from the master file as text.",
          "Channel names: \"Physical Pharmacy\" becomes In store and \"Ecommerce\" becomes Online. Any other value is kept as it is.",
          "Each refresh is exactly one calendar month after the history, so we do not handle late or corrected sales. If a transaction ID comes again it is ignored, not updated.",
          "Master data changes come in as full rows with a new EffectiveFromDate. For pharmacies and hospitals a Type 2 change starts on the first date of the batch.",
          "Rows that fail validation are stored in stg_rejects and not fixed. We chose a 0.5% error rate because it is easy to see but does not take over the data.",
          "TraumaLevel \"None\" and an empty value both mean the hospital has no trauma rating, so both become \"Not rated\".",
          "Passwords (sdi/sdi, airflow/airflow and the Airflow login admin/admin) and ports are only for running locally.",
      ])]

# ------------------------------------------------------------------ 11
S += [P("11. Testing and results", H1),
      P("We have an automated test (" + mono("tests/test_pipeline.py") + ") that runs the first load and both refreshes on a small fake dataset with the same columns as the real files, "
        "using SQLite instead of Postgres and DuckDB. It checks that loaded + rejected = generated, that history is kept after each refresh, that there are no duplicate keys or orphan foreign keys, "
        "that SCD Type 2 creates new versions while old sales keep the old key, that a repeated batch is skipped, and that base and opt queries give the same result."),
      P("After that we ran the real pipeline in Airflow (2.10.5, LocalExecutor, on a MacBook Air) on the full dataset. All three runs finished with every task green. "
        "The first load took about 1.5 minutes and each refresh took less than a minute. The real run also found one bug the SQLite test could not: "
        "in DuckDB the year column is a SMALLINT, so Year x 100 overflowed while building the summary table. We fixed it with a cast."),
      table([["What we measured", "First load (INIT)", "Refresh 1 (Jan 2026)", "Refresh 2 (Feb 2026)"],
             ["Sales rows in batch / loaded / rejected", "500,000 / 500,000 / 0", "48,737 / 48,494 / 243", "7,144 / 7,109 / 35"],
             ["Hospital rows in batch / loaded", "27,216 / 27,216", "756 / 756", "756 / 756"],
             ["Master data rows / new DimMedicine versions", "63 / 63", "0 / 0", "3 / 3 (SCD Type 2)"],
             ["FactPharmacySales rows after the run", "500,000", "548,494", "555,603"],
             ["FactHospitalDemand rows after the run", "27,216", "27,972", "28,728"],
             ["Sales dates covered", "2023-01-30 to 2025-12-31", "up to 2026-01-31", "up to 2026-02-28"],
             ["Slowest file load (sales file)", "11.49 s", "0.86 s", "0.11 s"],
             ["Orphan rows", "0", "0", "0"]],
            [5.6, 3.8, 3.8, 3.8]),
      Spacer(1, 4),
      P("All 9 file loads worked, so the batch success rate is 100% for all three sources. The rejected rows are exactly the ones we broke on purpose (about a third each for negative quantity, missing medicine ID and bad date), "
        "and they are all in stg_rejects. After refresh 2 the three changed medicines (MED014, MED023 and MED058) each have two versions. The old one ends on 2026-01-31 and the new one starts on 2026-02-01, "
        "and sales from before February still point to the old key. After both refreshes the Postgres staging database is 325 MB, the DuckDB file is 82 MB and the Parquet copy of the facts is 24 MB in 42 files (year 2023 to 2026)."),
      table([["Query (average of 3 runs, in ms)", "base", "opt", "Change"],
             ["Q1 region x month x channel (2025)", "4.93", "3.28", "33% faster"],
             ["Q2 forecast vs actual, category x quarter", "2.35", "4.35", "85% slower"],
             ["Q3 unfulfilled demand vs store sales, city x product", "7.20", "4.57", "37% faster"],
             ["K4 channel revenue and margin", "3.75", "2.85", "24% faster"],
             ["K5 top 10 movers by class", "7.15", "3.14", "56% faster"],
             ["K6 hospital service level", "1.32", "2.79", "111% slower"]],
            [8.2, 2.6, 2.6, 3.6]),
      Spacer(1, 3),
      P("These times are from the refresh 2 run. Across the three runs there were 108 query executions, none failed, and base and opt always gave the same answer. "
        "The summary table helps every query on the sales fact (24% to 56% faster), because AggSalesMonthly has about 31,000 rows compared to 555,603 in the fact table. "
        "AggDemandMonthly turned out to have the same grain as FactHospitalDemand (hospital x product x month), so it does not make the data any smaller, and for Q2 and K6 the extra join makes the opt version slower. "
        "Every query still runs in a few milliseconds in DuckDB, so this is not a real problem, but it was a useful thing to learn. "
        "In Milestone 2 we plan to make a smaller demand summary (for example category x quarter) once we know exactly what the dashboard widgets need."),
      P("<b>Next, Milestone 2:</b> the BI dashboards (hospital forecast vs actual and unfulfilled demand, channel revenue and margin, fast vs slow movers), "
        "the four monitoring dashboards in Grafana, and a live demo showing the dashboards change after refresh 1 and refresh 2.")]

doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("built")
