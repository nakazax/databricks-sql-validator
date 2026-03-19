# Databricks notebook source
# MAGIC %md
# MAGIC # Merge Validation Results
# MAGIC
# MAGIC Merge results from the staging table into the main table and clean up.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

from datetime import datetime

dbutils.widgets.text("table_name", "", "Table Name")
dbutils.widgets.text("staging_table", "", "Staging Table")

TABLE_NAME = dbutils.widgets.get("table_name")
STAGING_TABLE = dbutils.widgets.get("staging_table")

print(f"Main Table: {TABLE_NAME}")
print(f"Staging Table: {STAGING_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Merge Staging into Main Table

# COMMAND ----------

print(f"Started: {datetime.now()}")

staging_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {STAGING_TABLE}").collect()[0]["cnt"]
print(f"Staging rows: {staging_count:,}")

if staging_count > 0:
    spark.sql(f"""
    MERGE INTO {TABLE_NAME} t
    USING {STAGING_TABLE} s
    ON t.folder = s.folder AND t.relative_path = s.relative_path
       AND t.file_name = s.file_name AND t.statement_index = s.statement_index
    WHEN MATCHED THEN UPDATE SET syntax_valid = s.syntax_valid, syntax_error = s.syntax_error
    """)
    print("Merge complete")
else:
    print("No staging rows to merge")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cleanup Staging Table

# COMMAND ----------

spark.sql(f"DROP TABLE IF EXISTS {STAGING_TABLE}")
print(f"Dropped staging table: {STAGING_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Result Summary

# COMMAND ----------

summary = spark.sql(f"""
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN syntax_valid = true THEN 1 ELSE 0 END) as ok,
    SUM(CASE WHEN syntax_valid = false THEN 1 ELSE 0 END) as ng,
    SUM(CASE WHEN syntax_valid IS NULL AND read_status = 'OK' THEN 1 ELSE 0 END) as pending
FROM {TABLE_NAME}
""").collect()[0]

print(f"Total: {summary['total']:,}, OK: {summary['ok']:,}, NG: {summary['ng']:,}, Pending: {summary['pending']:,}")
print(f"Done: {datetime.now()}")
