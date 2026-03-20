Deploy the bundle to the specified target environment (default: dev).

1. Run tests: `uv run pytest tests/ -v`
2. Deploy: `databricks bundle deploy -t dev $ARGUMENTS`
3. Confirm the deployment output shows success.

Pass additional flags via $ARGUMENTS (e.g., `--profile my-profile --var="catalog=foo" --var="schema=bar"`).
