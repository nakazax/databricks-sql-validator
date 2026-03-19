"""
Merge file_list.csv with validation_results_file_summary.csv.
"""

import argparse
import pandas as pd
from pathlib import Path


def merge_validation_results(file_list_path: str, summary_path: str, output_path: str = None):
    """
    Merge validation_results_file_summary.csv into file_list.csv.

    Args:
        file_list_path: Path to file_list.csv.
        summary_path: Path to validation_results_file_summary.csv.
        output_path: Output path (defaults to file_list_merged.csv in the same directory).
    """
    # Read files
    file_list = pd.read_csv(file_list_path)
    summary = pd.read_csv(summary_path)

    print(f"file_list: {len(file_list)} rows")
    print(f"summary: {len(summary)} rows")

    # Build join key for file_list
    # subfolder + filename -> folder + relative_path
    def build_relative_path(row):
        if pd.isna(row["subfolder"]) or row["subfolder"] == "":
            return row["filename"]
        else:
            return f"{row['subfolder']}/{row['filename']}"

    file_list["_relative_path"] = file_list.apply(build_relative_path, axis=1)
    file_list["_key"] = file_list["folder"] + "/" + file_list["_relative_path"]

    # Build join key for summary
    summary["_key"] = summary["folder"] + "/" + summary["relative_path"]

    # Merge (left outer join: file_list as base)
    merged = file_list.merge(
        summary[["_key", "sql_count", "ok_count", "ng_count", "ok_pct", "status"]],
        on="_key",
        how="left"
    )

    # Drop temporary columns
    merged = merged.drop(columns=["_relative_path", "_key"])

    # Determine output path
    if output_path is None:
        output_path = str(Path(file_list_path).parent / "file_list_merged.csv")

    # Write output
    merged.to_csv(output_path, index=False)

    # Display statistics
    matched = merged["status"].notna().sum()
    unmatched = merged["status"].isna().sum()
    print(f"\nMatched: {matched} rows")
    print(f"Unmatched: {unmatched} rows")
    print(f"\nOutput: {output_path}")

    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge file_list.csv with validation results summary.")
    parser.add_argument("file_list", help="Path to file_list.csv")
    parser.add_argument("summary", help="Path to validation_results_file_summary.csv")
    parser.add_argument("--output", help="Output path (default: file_list_merged.csv in file_list directory)")

    args = parser.parse_args()
    merge_validation_results(args.file_list, args.summary, args.output)
