Deploy to the specified target environment (default: dev).

1. Run tests: `uv run pytest tests/ -v`
2. Deploy: `databricks bundle deploy -t $ARGUMENTS`
3. Verify the deployment output shows success.

If no argument is given, deploy to `dev`.
