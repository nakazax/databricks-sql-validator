Run the SQL validation CLI.

Execute:
```bash
python cli/run_validation.py $ARGUMENTS
```

If no arguments are given, show the help output (`--help`) so the user can see available options.

After completion, read the file summary CSV from the output directory and present a concise summary:
- Total files and SQL statements
- Pass/fail counts
- Any files with errors (show filename + error pattern)

If the user wants details, read the full detail CSV.
