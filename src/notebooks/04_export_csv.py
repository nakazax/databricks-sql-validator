# Databricks notebook source
# MAGIC %md
# MAGIC # CSV Export & Report
# MAGIC
# MAGIC Export validation results to CSV and display a summary.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

from datetime import datetime

dbutils.widgets.text("table_name", "", "Table Name")
dbutils.widgets.text("output_csv_path", "", "Output CSV Path")

TABLE_NAME = dbutils.widgets.get("table_name")
OUTPUT_CSV_PATH = dbutils.widgets.get("output_csv_path")

print(f"Table: {TABLE_NAME}")
print(f"Output CSV: {OUTPUT_CSV_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Detail CSV Export

# COMMAND ----------

def export_csv(df, output_path):
    """Export a DataFrame to a single CSV file."""
    temp_dir = output_path.replace(".csv", "_temp")
    df.coalesce(1).write.mode("overwrite") \
        .option("header", "true") \
        .option("escape", '"') \
        .csv(temp_dir)
    csv_files = [f.path for f in dbutils.fs.ls(temp_dir) if f.path.endswith(".csv")]
    if csv_files:
        dbutils.fs.cp(csv_files[0], output_path)
        dbutils.fs.rm(temp_dir, recurse=True)
    return df.count()

if TABLE_NAME and OUTPUT_CSV_PATH:
    detail_df = spark.read.table(TABLE_NAME)
    count = export_csv(detail_df, OUTPUT_CSV_PATH)
    print(f"Detail CSV exported: {OUTPUT_CSV_PATH} ({count:,} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## File Summary CSV Export

# COMMAND ----------

if TABLE_NAME and OUTPUT_CSV_PATH:
    # Aggregate by file
    file_summary_df = spark.sql(f"""
    SELECT
        folder,
        relative_path,
        file_name,
        COUNT(*) as sql_count,
        SUM(CASE WHEN syntax_valid = true THEN 1 ELSE 0 END) as ok_count,
        SUM(CASE WHEN syntax_valid = false THEN 1 ELSE 0 END) as ng_count,
        SUM(CASE WHEN syntax_valid = false AND syntax_flags IS NOT NULL THEN 1 ELSE 0 END) as ng_count_flagged,
        SUM(CASE WHEN syntax_valid = true OR syntax_flags IS NOT NULL THEN 1 ELSE 0 END) as ok_count_lenient,
        ROUND(SUM(CASE WHEN syntax_valid = true THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as ok_pct,
        CASE
            WHEN SUM(CASE WHEN syntax_valid = false THEN 1 ELSE 0 END) > 0 THEN 'NG'
            WHEN SUM(CASE WHEN syntax_valid IS NULL THEN 1 ELSE 0 END) > 0 THEN 'PENDING'
            ELSE 'OK'
        END as status
    FROM {TABLE_NAME}
    WHERE read_status = 'OK'
    GROUP BY folder, relative_path, file_name
    ORDER BY folder, relative_path, file_name
    """)

    summary_path = OUTPUT_CSV_PATH.replace(".csv", "_file_summary.csv")
    count = export_csv(file_summary_df, summary_path)
    print(f"File summary CSV exported: {summary_path} ({count:,} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary Display

# COMMAND ----------

if TABLE_NAME:
    total = spark.sql(f"SELECT COUNT(*) FROM {TABLE_NAME}").collect()[0][0]
    print(f"Total SQL statements: {total:,}")

# COMMAND ----------

# Validation results
summary = spark.sql(f"""
SELECT
    SUM(CASE WHEN syntax_valid = true THEN 1 ELSE 0 END) as ok,
    SUM(CASE WHEN syntax_valid = false THEN 1 ELSE 0 END) as ng,
    SUM(CASE WHEN syntax_valid IS NULL AND read_status = 'OK' THEN 1 ELSE 0 END) as pending,
    SUM(CASE WHEN syntax_valid = false AND syntax_flags IS NOT NULL THEN 1 ELSE 0 END) as ng_with_flags,
    SUM(CASE WHEN syntax_valid = false AND syntax_flags IS NULL THEN 1 ELSE 0 END) as ng_real
FROM {TABLE_NAME}
""").collect()[0]
print("=== Validation Results ===")
print(f"Total: {total:,}, OK: {summary['ok']:,}, NG: {summary['ng']:,}, Pending: {summary['pending']:,}")
print(f"  NG (real syntax errors): {summary['ng_real']:,}")
print(f"  NG (with syntax_flags): {summary['ng_with_flags']:,}")

# COMMAND ----------

# By folder
print("=== By Folder ===")
display(spark.sql(f"""
SELECT folder,
    SUM(CASE WHEN syntax_valid = true THEN 1 ELSE 0 END) as ok,
    SUM(CASE WHEN syntax_valid = false THEN 1 ELSE 0 END) as ng,
    COUNT(*) as total
FROM {TABLE_NAME}
GROUP BY folder ORDER BY folder
"""))

# COMMAND ----------

# Error patterns
print("=== Error Patterns (Top 10) ===")
display(spark.sql(f"""
SELECT SUBSTRING(syntax_error, 1, 100) as error_pattern, COUNT(*) as count
FROM {TABLE_NAME}
WHERE syntax_valid = false AND syntax_error IS NOT NULL
GROUP BY SUBSTRING(syntax_error, 1, 100)
ORDER BY count DESC LIMIT 10
"""))

# COMMAND ----------

print(f"Done: {datetime.now()}")
