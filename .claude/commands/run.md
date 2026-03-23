Run the SQL validation CLI.

Execute:
```bash
python cli/run_validation.py $ARGUMENTS
```

If no arguments are given, show the help output (`--help`) so the user can see available options.

After completion, read the file summary CSV from the output directory and present a concise summary:
- Total files and SQL statements
- Pass/fail counts (OK / NG / NG with syntax_flags / OK lenient)
- Any files with errors (show filename + error pattern)

When `ng_count_flagged > 0`, note that these NG results have `syntax_flags` (template vars, params, placeholders) and may not be real syntax errors.

If the user wants details, read the full detail CSV.
