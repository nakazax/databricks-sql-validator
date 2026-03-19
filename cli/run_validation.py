"""
CLI wrapper to run SQL validation from local files.

Uploads local SQL files to a Databricks Volume, triggers the validation job,
waits for completion, and downloads the result CSVs.
"""

import argparse
import os
import time
from datetime import datetime
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import RunLifeCycleState, RunResultState


def upload_directory(ws: WorkspaceClient, local_dir: Path, volume_path: str) -> int:
    """Upload a local directory to a Volume path recursively.

    Returns the number of files uploaded.
    """
    count = 0
    for root, _, files in os.walk(local_dir):
        for filename in files:
            if filename.startswith("."):
                continue
            local_file = Path(root) / filename
            relative = local_file.relative_to(local_dir)
            remote_path = f"{volume_path}/{relative}"
            with open(local_file, "rb") as f:
                ws.files.upload(remote_path, f, overwrite=True)
            count += 1
    return count


def find_job_by_name(ws: WorkspaceClient, job_name: str) -> int:
    """Find a job by name and return its job_id.

    Supports both exact match and suffix match to handle DABs dev mode
    prefix (e.g., '[dev user] Job Name').
    """
    # Try exact match first
    for job in ws.jobs.list(name=job_name):
        return job.job_id
    # Fall back to suffix match (for DABs dev mode prefix)
    for job in ws.jobs.list():
        if job.settings and job.settings.name and job.settings.name.endswith(job_name):
            print(f"Found job: {job.settings.name}")
            return job.job_id
    raise SystemExit(f"Error: Job '{job_name}' not found. Deploy with 'databricks bundle deploy' first.")


def wait_for_run(ws: WorkspaceClient, run_id: int, poll_interval: int = 30) -> RunResultState:
    """Wait for a job run to complete and return the result state."""
    while True:
        run = ws.jobs.get_run(run_id)
        state = run.state
        if state.life_cycle_state in (
            RunLifeCycleState.TERMINATED,
            RunLifeCycleState.SKIPPED,
            RunLifeCycleState.INTERNAL_ERROR,
        ):
            print(f"\nRun finished: {state.life_cycle_state.value}, result: {state.result_state.value}")
            return state.result_state
        print(f"  Status: {state.life_cycle_state.value}...", end="\r")
        time.sleep(poll_interval)


def download_results(ws: WorkspaceClient, volume_path: str, output_dir: Path) -> list[str]:
    """Download all files from a Volume directory to a local directory.

    Returns the list of downloaded file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    try:
        entries = ws.files.list_directory_contents(volume_path)
    except Exception:
        print(f"Warning: No files found at {volume_path}")
        return downloaded
    for entry in entries:
        if entry.is_directory:
            continue
        name = entry.name
        resp = ws.files.download(f"{volume_path}/{name}")
        local_path = output_dir / name
        with open(local_path, "wb") as f:
            f.write(resp.contents.read())
        downloaded.append(str(local_path))
    return downloaded


def main():
    parser = argparse.ArgumentParser(
        description="Run SQL validation on Databricks from local files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --source-dir ./sql_files --catalog my_catalog --schema my_schema --volume my_volume
  %(prog)s --source-dir ./sql_files --catalog my_catalog --schema my_schema --volume my_volume --output-dir ./results
  %(prog)s --source-dir ./sql_files --catalog my_catalog --schema my_schema --volume my_volume --profile STAGING
        """,
    )
    parser.add_argument("--source-dir", required=True, type=Path, help="Local directory containing SQL files")
    parser.add_argument("--catalog", required=True, help="Unity Catalog name")
    parser.add_argument("--schema", required=True, help="Schema name")
    parser.add_argument("--volume", required=True, help="Volume name for staging files")
    parser.add_argument("--output-dir", type=Path, default=Path("./results"), help="Local directory for result CSVs (default: ./results)")
    parser.add_argument("--job-name", default="SQL Validation - Syntax Check", help="Databricks job name")
    parser.add_argument("--max-batches", type=int, default=1000, help="Max number of parallel validation batches (default: 1000)")
    parser.add_argument("--profile", default=None, help="Databricks CLI profile name")
    parser.add_argument("--poll-interval", type=int, default=30, help="Polling interval in seconds (default: 30)")

    args = parser.parse_args()

    if not args.source_dir.is_dir():
        raise SystemExit(f"Error: {args.source_dir} is not a directory")

    # Initialize client
    ws = WorkspaceClient(profile=args.profile)

    # Generate run_id
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_base = f"/Volumes/{args.catalog}/{args.schema}/{args.volume}/{run_id}"
    input_path = f"{volume_base}/input"
    output_path = f"{volume_base}/output"

    print(f"Run ID: {run_id}")
    print(f"Volume base: {volume_base}")

    # Step 1: Upload
    print(f"\n=== Uploading files from {args.source_dir} ===")
    count = upload_directory(ws, args.source_dir, input_path)
    print(f"Uploaded {count} files to {input_path}")

    # Step 2: Run job
    print(f"\n=== Starting job: {args.job_name} ===")
    job_id = find_job_by_name(ws, args.job_name)

    run_response = ws.jobs.run_now(
        job_id=job_id,
        job_parameters={
            "source_folders": input_path,
            "output_table_prefix": f"{args.catalog}.{args.schema}.sql_validation_results",
            "output_csv_prefix": f"{output_path}/validation_results",
            "max_batches": str(args.max_batches),
            "run_id": run_id,
        },
    )
    print(f"Run started: run_id={run_response.run_id}")
    print("Waiting for completion...")

    result_state = wait_for_run(ws, run_response.run_id, args.poll_interval)
    if result_state != RunResultState.SUCCESS:
        raise SystemExit(f"Error: Job run failed with state: {result_state.value}")

    # Step 3: Download results
    print(f"\n=== Downloading results to {args.output_dir} ===")
    downloaded = download_results(ws, output_path, args.output_dir)
    if downloaded:
        print(f"Downloaded {len(downloaded)} files:")
        for path in downloaded:
            print(f"  {path}")
    else:
        print("No result files found.")

    print(f"\n=== Done ===")
    print(f"Delta table: {args.catalog}.{args.schema}.sql_validation_results_{run_id}")
    print(f"Results: {args.output_dir}")


if __name__ == "__main__":
    main()
