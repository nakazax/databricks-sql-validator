# databricks-sql-validator

Validate SQL file syntax on Databricks using Spark SQL `EXPLAIN` with batch parallel execution.

## Overview

This tool validates SQL file syntax on Databricks. Point it at a directory of SQL files and it produces per-statement validation results (Delta table + CSV).

- **Input**: Local directory containing SQL files (any encoding: UTF-8, Shift-JIS, CP932, EUC-JP)
- **Output**: Detail CSV (per-statement pass/fail) and file summary CSV (per-file aggregation)

The tool extracts individual SQL statements from each file, then validates syntax using Spark SQL's `EXPLAIN` command. Since `EXPLAIN` runs only on the Spark driver (not distributed across executors), simply adding nodes does not improve throughput. To work around this, the tool leverages Lakeflow Jobs' [For Each task](https://docs.databricks.com/aws/en/jobs/for-each) to run up to 100 concurrent validation tasks in parallel.

## Pipeline

The job consists of four sequential steps. The validate step runs as a For Each task, executing batches in parallel.

```
┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐
│ 01_extract   │──▶│ 02_validate      │──▶│ 03_merge_results │──▶│ 04_export    │
│              │   │ (For Each, auto) │   │                  │   │              │
│ Find files   │   │ EXPLAIN validate │   │ Staging → Main   │   │ Detail CSV   │
│ Split SQL    │   │ INSERT staging   │   │ DROP staging     │   │ Summary CSV  │
│ Write Delta  │   │ (no conflicts)   │   │ (single MERGE)   │   │ Report       │
└──────────────┘   └──────────────────┘   └──────────────────┘   └──────────────┘
```

## Prerequisites

- Databricks workspace with Unity Catalog enabled
- Databricks CLI (`databricks`) installed and configured
- A Unity Catalog catalog, schema, and volume created beforehand (the tool does not create these)
- SQL files with statements separated by semicolons
- Serverless compute enabled (optimized for serverless jobs; classic compute works but won't start as quickly)

## Quick Start

### 1. Deploy

```bash
databricks bundle deploy -t dev \
  --profile your-profile \
  --var="catalog=your_catalog" \
  --var="schema=your_schema"
```

### 2. Run (via CLI)

The CLI uploads local SQL files to a Volume, triggers the validation job, and downloads results:

```bash
pip install -e ".[cli]"

python cli/run_validation.py \
  --source-dir ./sql_files \
  --catalog my_catalog \
  --schema my_schema \
  --volume my_volume \
  --job-id 123456 \
  --output-dir ./results
```

This creates a run directory on the Volume:

```
/Volumes/{catalog}/{schema}/{volume}/{run_id}/
├── input/           ← uploaded SQL files
└── output/          ← result CSVs (downloaded to --output-dir)
```

See `python cli/run_validation.py --help` for all options.

> **Claude Code users**: `/deploy` and `/run` slash commands are available for streamlined workflow.

## Parameters

### CLI (`run_validation.py`)

| Option | Description | Default |
|---|---|---|
| `--source-dir` | Local directory containing SQL files | (required) |
| `--catalog` | Unity Catalog name | (required) |
| `--schema` | Schema name | (required) |
| `--volume` | Volume name for staging files | (required) |
| `--job-id` | Databricks job ID | (required) |
| `--output-dir` | Local directory for result CSVs | `./results` |
| `--exclude-extensions` | Comma-separated file extensions to exclude | `.xlsx,.xlsm,.dsx,.isx,.DS_Store` |
| `--max-batches` | Max number of parallel validation batches | `1000` |
| `--profile` | Databricks CLI profile name | (env default) |
| `--upload-workers` | Parallel upload threads | `10` |
| `--poll-interval` | Polling interval in seconds | `30` |

### Job Parameters

These are passed automatically by the CLI, or manually via `databricks bundle run --param`.

| Parameter | Description | Default |
|---|---|---|
| `source_folders` | Comma-separated Volume paths containing SQL files | (required) |
| `exclude_extensions` | File extensions to skip | `.xlsx,.xlsm,.dsx,.isx,.DS_Store` |
| `output_table_prefix` | Delta table name prefix for results | `${catalog}.${schema}.sql_validation_results` |
| `output_csv_prefix` | Volume path prefix for CSV output | `/Volumes/${catalog}/${schema}/raw/validation_results` |
| `max_batches` | Max number of parallel validation batches (auto-reduced to statement count) | `1000` |
| `run_id` | Run identifier for consistent naming (auto-generated if empty) | `""` |

## Output Schema

### Detail Table / CSV

| Column | Type | Description |
|---|---|---|
| `folder` | string | Source folder name |
| `relative_path` | string | File path relative to source folder |
| `file_name` | string | File name |
| `statement_index` | int | Statement position within the file |
| `sql_text` | string | Extracted SQL statement |
| `read_status` | string | `OK`, `EMPTY`, or `READ_ERROR` |
| `read_error` | string | Error message if read failed |
| `syntax_valid` | boolean | `true` if EXPLAIN succeeded |
| `syntax_error` | string | Error message if validation failed |

### File Summary CSV

| Column | Type | Description |
|---|---|---|
| `folder` | string | Source folder name |
| `relative_path` | string | File path relative to source folder |
| `file_name` | string | File name |
| `sql_count` | int | Total SQL statements in file |
| `ok_count` | int | Statements that passed validation |
| `ng_count` | int | Statements that failed validation |
| `ok_pct` | float | Pass rate (%) |
| `status` | string | `OK`, `NG`, or `PENDING` |

## Project Structure

```
databricks-sql-validator/
├── README.md
├── LICENSE
├── .gitignore
├── pyproject.toml
├── databricks.yml
├── cli/
│   └── run_validation.py              # CLI wrapper (upload → run → download)
├── src/
│   └── notebooks/
│       ├── 01_extract_sql.py          # File discovery + SQL extraction
│       ├── 02_validate_syntax.py      # EXPLAIN-based syntax validation
│       ├── 03_merge_results.py        # Merge staging results into main table
│       ├── 04_export_csv.py           # CSV export + summary report
│       └── pyscripts/
│           ├── sql_utils.py           # SQL comment/statement utilities
│           └── merge_validation_results.py  # Post-processing merge utility
├── tests/
│   └── test_sql_utils.py
└── resources/
    └── sql_validation_job.yml         # Databricks Asset Bundle job definition
```

## Local Development

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

## Limitations

- Expects serverless jobs (generic compute). Validation results may differ from SQL Warehouses, which sometimes support newer syntax earlier.
- SQL Scripting and Stored Procedures cannot be validated via `EXPLAIN`.

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
