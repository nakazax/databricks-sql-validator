# Databricks notebook source
# MAGIC %md
# MAGIC # SQL Extraction
# MAGIC
# MAGIC Extract SQL statements from files in specified folders and write them to a Delta table.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

from datetime import datetime
from collections import Counter
import os

from pyscripts.sql_utils import remove_sql_comments, split_sql_statements

dbutils.widgets.text("source_folders", "", "Source Folders")
dbutils.widgets.text("exclude_extensions", ".xlsx,.xlsm,.dsx,.isx,.DS_Store", "Exclude Extensions")
dbutils.widgets.text("output_table_prefix", "", "Output Table Prefix")
dbutils.widgets.text("output_csv_prefix", "", "Output CSV Prefix")
dbutils.widgets.text("max_batches", "1000", "Max Batches")
dbutils.widgets.text("run_id", "", "Run ID")

SOURCE_FOLDERS = [f.strip() for f in dbutils.widgets.get("source_folders").split(",") if f.strip()]
EXCLUDE_EXTENSIONS = [e.strip().lower() for e in dbutils.widgets.get("exclude_extensions").split(",") if e.strip()]
OUTPUT_TABLE_PREFIX = dbutils.widgets.get("output_table_prefix")
OUTPUT_CSV_PREFIX = dbutils.widgets.get("output_csv_prefix")
MAX_BATCHES = int(dbutils.widgets.get("max_batches"))

# Use run_id if provided, otherwise generate timestamp
RUN_ID = dbutils.widgets.get("run_id").strip() or datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_TABLE = f"{OUTPUT_TABLE_PREFIX}_{RUN_ID}"
OUTPUT_CSV_PATH = f"{OUTPUT_CSV_PREFIX}_{RUN_ID}.csv"

print(f"Source Folders: {SOURCE_FOLDERS}")
print(f"Output Table: {OUTPUT_TABLE}")
print(f"Output CSV: {OUTPUT_CSV_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## File Discovery

# COMMAND ----------

def find_files(folders, exclude_extensions):
    """Recursively find files in specified folders."""
    files = []
    for folder in folders:
        if not os.path.exists(folder):
            print(f"Warning: Folder does not exist: {folder}")
            continue
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() not in exclude_extensions:
                    file_path = os.path.join(root, filename)
                    files.append({
                        "full_path": file_path,
                        "folder": os.path.basename(folder),
                        "relative_path": os.path.relpath(file_path, folder),
                        "file_name": filename
                    })
    return files

target_files = find_files(SOURCE_FOLDERS, EXCLUDE_EXTENSIONS)
print(f"Target files: {len(target_files)}")

ext_counts = Counter(os.path.splitext(f["file_name"])[1].lower() for f in target_files)
print("\nFiles by extension:")
for ext, count in ext_counts.most_common():
    print(f"  {ext}: {count}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Helper Functions

# COMMAND ----------

def read_file_with_encoding(file_path):
    """Read a file trying multiple encodings."""
    for encoding in ['utf-8', 'shift-jis', 'cp932', 'euc-jp']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(file_path, 'rb') as f:
        return f.read().decode('utf-8', errors='replace')


def create_result(file_info, stmt_idx, sql_text, status, error=None):
    """Create a result record."""
    return {
        "folder": file_info["folder"],
        "relative_path": file_info["relative_path"],
        "file_name": file_info["file_name"],
        "statement_index": stmt_idx,
        "sql_text": sql_text,
        "read_status": status,
        "read_error": error,
        "syntax_valid": None,
        "syntax_error": None,
    }

# COMMAND ----------

# MAGIC %md
# MAGIC ## SQL Extraction (Distributed Processing)

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, IntegerType, BooleanType
import pandas as pd

print(f"Started: {datetime.now()}")

output_schema = StructType([
    StructField("folder", StringType()),
    StructField("relative_path", StringType()),
    StructField("file_name", StringType()),
    StructField("statement_index", IntegerType()),
    StructField("sql_text", StringType()),
    StructField("read_status", StringType()),
    StructField("read_error", StringType()),
    StructField("syntax_valid", BooleanType()),
    StructField("syntax_error", StringType()),
])

def process_partition(pdf_iter):
    """Process files in each partition."""
    for pdf in pdf_iter:
        results = []
        for _, row in pdf.iterrows():
            file_info = row.to_dict()
            try:
                content = read_file_with_encoding(file_info["full_path"])
                statements = split_sql_statements(content)
                if not statements:
                    results.append(create_result(file_info, 0, None, "EMPTY", "No SQL statement found"))
                else:
                    for idx, stmt in enumerate(statements):
                        results.append(create_result(file_info, idx, stmt, "OK"))
            except Exception as e:
                results.append(create_result(file_info, 0, None, "READ_ERROR", str(e)))
        yield pd.DataFrame(results)

# Determine number of partitions
num_partitions = min(max(8, len(target_files) // 50), 200)
print(f"Partitions: {num_partitions}")

files_df = spark.createDataFrame(target_files).repartition(num_partitions)
results_df = files_df.mapInPandas(process_partition, schema=output_schema)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Delta Table

# COMMAND ----------

# Create schema if needed
table_parts = OUTPUT_TABLE.split(".")
if len(table_parts) == 3:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {table_parts[0]}.{table_parts[1]}")

results_df.write.mode("overwrite").saveAsTable(OUTPUT_TABLE)

count = spark.sql(f"SELECT COUNT(*) as cnt FROM {OUTPUT_TABLE}").collect()[0]["cnt"]
print(f"Done: {OUTPUT_TABLE} ({count:,} rows)")

# Cap batch count to actual statement count to avoid empty batches
actual_batches = min(MAX_BATCHES, max(1, count))
if actual_batches < MAX_BATCHES:
    print(f"Adjusted batches: {MAX_BATCHES} -> {actual_batches} (based on statement count)")

# Pass values to downstream tasks
dbutils.jobs.taskValues.set(key="output_table", value=OUTPUT_TABLE)
dbutils.jobs.taskValues.set(key="output_csv_path", value=OUTPUT_CSV_PATH)
dbutils.jobs.taskValues.set(key="batch_count", value=str(actual_batches))
dbutils.jobs.taskValues.set(key="batch_ids", value=str(list(range(actual_batches))))
dbutils.jobs.taskValues.set(key="run_id", value=RUN_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Result Preview

# COMMAND ----------

display(spark.sql(f"SELECT folder, read_status, COUNT(*) as count FROM {OUTPUT_TABLE} GROUP BY folder, read_status ORDER BY folder"))
