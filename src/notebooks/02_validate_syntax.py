# Databricks notebook source
# MAGIC %md
# MAGIC # SQL Syntax Validation (Batch Processing)
# MAGIC
# MAGIC Validate SQL statements in a Delta table using Spark SQL EXPLAIN and update the results.
# MAGIC Supports parallel execution via For Each tasks.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

from datetime import datetime
from pyspark.sql.types import StructType, StructField, StringType, BooleanType, IntegerType

dbutils.widgets.text("table_name", "", "Table Name")
dbutils.widgets.text("staging_table", "", "Staging Table")
dbutils.widgets.text("batch_id", "0", "Batch ID")
dbutils.widgets.text("batch_count", "1", "Batch Count")

TABLE_NAME = dbutils.widgets.get("table_name")
STAGING_TABLE = dbutils.widgets.get("staging_table")
BATCH_ID = int(dbutils.widgets.get("batch_id"))
BATCH_COUNT = int(dbutils.widgets.get("batch_count"))

print(f"Table: {TABLE_NAME}")
print(f"Staging Table: {STAGING_TABLE}")
print(f"Batch: {BATCH_ID + 1} / {BATCH_COUNT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Batch Target Records

# COMMAND ----------

print(f"Started: {datetime.now()}")

target_df = spark.sql(f"""
SELECT folder, relative_path, file_name, statement_index, sql_text
FROM {TABLE_NAME}
WHERE syntax_valid IS NULL AND read_status = 'OK'
  AND MOD(ABS(HASH(folder, relative_path, file_name, statement_index)), {BATCH_COUNT}) = {BATCH_ID}
""")

# Display target SQL statements
display(target_df)

rows = target_df.collect()
print(f"Target statements: {len(rows):,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## SQL Validation

# COMMAND ----------

import re

# Template variable pattern (e.g., @TBL@, @IDXSPC@, @TBLSPC@)
TEMPLATE_VAR_PATTERN = re.compile(r'@([A-Za-z0-9_]+)@')

def validate_sql(sql_text):
    """Validate SQL using EXPLAIN."""
    if not sql_text:
        return (None, "No SQL statement found")

    # Detect and temporarily replace template variables
    template_vars = TEMPLATE_VAR_PATTERN.findall(sql_text)
    check_sql = sql_text
    if template_vars:
        # Replace @VAR@ with _TEMPLATE_VAR_ for syntax checking
        check_sql = TEMPLATE_VAR_PATTERN.sub(r'_TEMPLATE_\1_', sql_text)

    try:
        spark.sql(f"EXPLAIN {check_sql}")
        if template_vars:
            vars_str = ", ".join(f"@{v}@" for v in sorted(set(template_vars)))
            return (True, f"INFO: Template variables detected ({vars_str})")
        return (True, None)
    except Exception as e:
        msg = str(e)
        if "JVM stacktrace:" in msg:
            msg = msg[:msg.index("JVM stacktrace:")].strip()
        return (False, msg[:500] if len(msg) > 500 else msg)

results = []
for i, row in enumerate(rows):
    valid, error = validate_sql(row.sql_text)
    results.append({
        "folder": row.folder,
        "relative_path": row.relative_path,
        "file_name": row.file_name,
        "statement_index": row.statement_index,
        "syntax_valid": valid,
        "syntax_error": error,
    })
    if (i + 1) % 1000 == 0:
        print(f"Progress: {i + 1}/{len(rows)} ({(i + 1) / len(rows) * 100:.1f}%)")

print(f"Validation done: {len(results):,} statements")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Update Delta Table

# COMMAND ----------

if results:
    schema = StructType([
        StructField("folder", StringType(), True),
        StructField("relative_path", StringType(), True),
        StructField("file_name", StringType(), True),
        StructField("statement_index", IntegerType(), True),
        StructField("syntax_valid", BooleanType(), True),
        StructField("syntax_error", StringType(), True),
    ])
    results_df = spark.createDataFrame(results, schema)
    results_df.write.mode("append").saveAsTable(STAGING_TABLE)
    print(f"Appended {len(results):,} rows to staging table: {STAGING_TABLE}")
else:
    print("No records to write")

print(f"Done: {datetime.now()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Result Summary

# COMMAND ----------

valid_count = sum(1 for r in results if r["syntax_valid"] is True)
invalid_count = sum(1 for r in results if r["syntax_valid"] is False)
print(f"This batch: OK={valid_count:,}, ERROR={invalid_count:,}")
