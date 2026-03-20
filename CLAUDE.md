# CLAUDE.md

## Overview

See [README.md](README.md) for architecture, parameters, and output schema.

## Development Workflow

Before committing and pushing, always:

1. **Run tests**: `uv run pytest tests/ -v`
2. **Deploy to dev**: `databricks bundle deploy -t dev --profile e2-demo-tokyo --var="catalog=hinak_catalog_aws_apne1" --var="schema=sql_validation"`

## Key Commands

```bash
# Test
uv run pytest tests/ -v

# Deploy
databricks bundle deploy -t dev --profile e2-demo-tokyo \
  --var="catalog=hinak_catalog_aws_apne1" --var="schema=sql_validation"

# Run validation (CLI)
python cli/run_validation.py \
  --source-dir /tmp/sql_test_files \
  --catalog hinak_catalog_aws_apne1 \
  --schema sql_validation \
  --volume runs \
  --output-dir /tmp/sql_test_staging \
  --profile e2-demo-tokyo \
  --poll-interval 10
```

## Notebooks

Databricks notebook format: `# COMMAND ----------` separators, `# MAGIC %md` for markdown cells. Notebooks use `dbutils` and `spark` (provided by Databricks runtime, not imported).
