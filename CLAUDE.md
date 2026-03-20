# CLAUDE.md

## Overview

See [README.md](README.md) for architecture, parameters, and output schema.

## Development Workflow

Before committing and pushing, always:

1. **Run tests**: `uv run pytest tests/ -v`
2. **Deploy to dev**: `databricks bundle deploy -t dev`  (with appropriate profile and variables)

## Notebooks

Databricks notebook format: `# COMMAND ----------` separators, `# MAGIC %md` for markdown cells. Notebooks use `dbutils` and `spark` (provided by Databricks runtime, not imported).
