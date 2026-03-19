# databricks-sql-validator

Validate SQL file syntax on Databricks using Spark SQL `EXPLAIN` with batch parallel execution.

## Overview

This tool scans SQL files across specified folders, extracts individual SQL statements, and validates their syntax using Spark SQL's `EXPLAIN` command. It leverages Databricks Jobs' **For Each** task for massively parallel validation.

## Features

- Recursive file discovery across multiple source folders
- Multi-encoding support (UTF-8, Shift-JIS, CP932, EUC-JP)
- Proper SQL comment handling (block comments, line comments, string literals)
- Statement splitting by semicolon with comment-awareness
- Template variable detection (`@VAR@` patterns)
- Parallel batch validation via Databricks For Each tasks
- CSV export with per-file summary reports
- **CLI wrapper** for local-to-Databricks workflow (upload, run, download)

## Architecture

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
- SQL files accessible via Unity Catalog Volumes (or local files via CLI wrapper)

## Quick Start

### 1. Deploy

```bash
databricks bundle deploy -t dev \
  --profile your-profile \
  --var="catalog=your_catalog" \
  --var="schema=your_schema"
```

### 2a. Run (from Volume)

```bash
databricks bundle run sql_validation -t dev \
  --profile your-profile \
  --var="catalog=your_catalog" \
  --var="schema=your_schema" \
  --param source_folders="/Volumes/your_catalog/your_schema/volume/folder1"
```

### 2b. Run (from local files via CLI)

The CLI wrapper uploads local SQL files to a Volume, runs the job, and downloads results:

```bash
pip install -e ".[cli]"

python cli/run_validation.py \
  --source-dir ./sql_files \
  --catalog my_catalog \
  --schema my_schema \
  --volume my_volume \
  --output-dir ./results
```

This creates a run directory on the Volume:

```
/Volumes/{catalog}/{schema}/{volume}/{run_id}/
├── input/           ← uploaded SQL files
└── output/          ← result CSVs (downloaded to --output-dir)
```

See `python cli/run_validation.py --help` for all options.

## Parameters

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

### Using uv

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

### Using pip

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Import Check

```bash
python -c "import sys; sys.path.insert(0, 'src/notebooks/pyscripts'); from sql_utils import remove_sql_comments; print('OK')"
```

## Merge Utility

The `merge_validation_results.py` script merges a `file_list.csv` with the validation file summary CSV.

### Expected `file_list.csv` Columns

| Column | Description |
|---|---|
| `folder` | Folder name (matches validation output `folder`) |
| `subfolder` | Subfolder path (optional, used to build `relative_path`) |
| `filename` | File name |

### Usage

```bash
pip install -e ".[merge]"
python src/notebooks/pyscripts/merge_validation_results.py file_list.csv validation_results_file_summary.csv
python src/notebooks/pyscripts/merge_validation_results.py file_list.csv summary.csv --output merged.csv
```

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
