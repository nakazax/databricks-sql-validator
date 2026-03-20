# CLAUDE.md

## Overview

See [README.md](README.md) for architecture, parameters, and output schema.

## Development Workflow

Before committing and pushing, always:

1. **Run tests**: `uv run pytest tests/ -v`
2. **Deploy to dev**: `databricks bundle deploy -t dev`  (with appropriate profile and variables)

## Key Design Decisions

- `EXPLAIN` runs on the Spark driver only, so parallelism comes from For Each task (max concurrency: 100), not executor scaling.
- The CLI (`cli/run_validation.py`) is the primary interface. Job parameters are passed through the CLI; users should not need to call `databricks bundle run` directly.
- `exclude_extensions` filters non-SQL files (e.g., `.xlsx`, `.DS_Store`) before upload processing.

## Notebooks

Databricks notebook format: `# COMMAND ----------` separators, `# MAGIC %md` for markdown cells. Notebooks use `dbutils` and `spark` (provided by Databricks runtime, not imported).
