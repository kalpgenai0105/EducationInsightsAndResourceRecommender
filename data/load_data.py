"""
BigQuery dataset creation and data loading script.

Run this once (or re-run with --replace to refresh) before starting the agents.

Usage:
    python -m data.load_data
    python -m data.load_data --replace        # drop and recreate all tables
    python -m data.load_data --table staffing # load a single table
    python -m data.load_data --dry-run        # validate CSVs without uploading
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib
import sys
from typing import Any

from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud.exceptions import Conflict, NotFound
from rich.console import Console
from rich.table import Table

from data.schema import TABLE_CONFIG

load_dotenv()
console = Console()

# ---------------------------------------------------------------------------
# Config (from environment / defaults)
# ---------------------------------------------------------------------------
PROJECT   = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DATASET   = os.environ.get("BIGQUERY_DATASET", "education_insights")
LOCATION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "US")
DATA_DIR  = pathlib.Path(__file__).parent.parent / "sample_data"


# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------

def get_or_create_dataset(client: bigquery.Client) -> bigquery.Dataset:
    """Create the BigQuery dataset if it does not already exist."""
    dataset_ref = bigquery.Dataset(f"{PROJECT}.{DATASET}")
    dataset_ref.location = LOCATION
    dataset_ref.description = (
        "Education Insights: school performance, funding, staffing, and programs "
        "for 30 schools across Millbrook, Jefferson, and Oakdale counties, CA."
    )

    try:
        dataset = client.create_dataset(dataset_ref, timeout=30)
        console.print(f"[green]Created dataset[/green] {PROJECT}.{DATASET}")
    except Conflict:
        dataset = client.get_dataset(dataset_ref)
        console.print(f"[yellow]Dataset exists[/yellow] {PROJECT}.{DATASET}")

    return dataset


# ---------------------------------------------------------------------------
# Table loading
# ---------------------------------------------------------------------------

def _bool_to_yes_no(value: str) -> str:
    """Normalise TRUE/FALSE strings to Yes/No for STRING BQ columns."""
    if value.strip().upper() == "TRUE":
        return "Yes"
    if value.strip().upper() == "FALSE":
        return "No"
    return value


def load_table(
    client: bigquery.Client,
    table_name: str,
    replace: bool = False,
) -> int:
    """
    Load a single CSV file into the corresponding BigQuery table.

    Returns the number of rows loaded.
    Strategy: load via LoadJobConfig so the schema is enforced at write time.
    All loads are WRITE_TRUNCATE so repeated runs are idempotent.
    """
    config = TABLE_CONFIG[table_name]
    csv_path = DATA_DIR / config["csv_file"]

    if not csv_path.exists():
        console.print(f"[red]CSV not found:[/red] {csv_path}")
        return 0

    table_ref = f"{PROJECT}.{DATASET}.{table_name}"

    if replace:
        try:
            client.delete_table(table_ref)
            console.print(f"[yellow]Dropped[/yellow] {table_ref}")
        except NotFound:
            pass

    job_config = bigquery.LoadJobConfig(
        schema=config["schema"],
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,          # skip header row
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        null_marker="",               # empty string → NULL
        autodetect=False,             # use explicit schema
    )

    with open(csv_path, "rb") as fh:
        job = client.load_table_from_file(fh, table_ref, job_config=job_config)

    job.result()  # block until complete

    if job.errors:
        for err in job.errors:
            console.print(f"[red]Load error:[/red] {err}")
        raise RuntimeError(f"Load job failed for table {table_name}")

    table = client.get_table(table_ref)
    console.print(
        f"[green]Loaded[/green] {table.num_rows:,} rows → {table_ref}"
    )
    return table.num_rows


def validate_csv(table_name: str) -> list[str]:
    """
    Basic validation: check CSV exists and headers match the expected schema.
    Returns a list of warning strings (empty = all good).
    """
    config = TABLE_CONFIG[table_name]
    csv_path = DATA_DIR / config["csv_file"]
    warnings: list[str] = []

    if not csv_path.exists():
        return [f"File not found: {csv_path}"]

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        csv_headers = set(reader.fieldnames or [])

    expected = {field.name for field in config["schema"]}
    missing  = expected - csv_headers
    extra    = csv_headers - expected

    if missing:
        warnings.append(f"Missing columns: {sorted(missing)}")
    if extra:
        warnings.append(f"Extra columns (will be ignored): {sorted(extra)}")

    return warnings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load education sample data into BigQuery"
    )
    parser.add_argument("--replace",  action="store_true", help="Drop and recreate tables")
    parser.add_argument("--dry-run",  action="store_true", help="Validate only, no upload")
    parser.add_argument("--table",    default=None,        help="Load a single table by name")
    args = parser.parse_args(argv)

    if not PROJECT:
        console.print("[red]Error:[/red] GOOGLE_CLOUD_PROJECT env var is not set.")
        return 1

    tables_to_load = [args.table] if args.table else list(TABLE_CONFIG.keys())

    # --- Validation pass ---
    console.rule("Validating CSVs")
    validation_table = Table("Table", "Status", "Warnings")
    all_ok = True
    for tname in tables_to_load:
        issues = validate_csv(tname)
        status = "[green]OK[/green]" if not issues else "[yellow]WARN[/yellow]"
        validation_table.add_row(tname, status, "; ".join(issues) or "—")
        if issues:
            all_ok = False
    console.print(validation_table)

    if args.dry_run:
        console.print("[cyan]Dry-run complete — no data uploaded.[/cyan]")
        return 0 if all_ok else 2

    # --- Upload pass ---
    console.rule("Uploading to BigQuery")
    client = bigquery.Client(project=PROJECT)
    get_or_create_dataset(client)

    total_rows = 0
    for tname in tables_to_load:
        try:
            rows = load_table(client, tname, replace=args.replace)
            total_rows += rows
        except Exception as exc:
            console.print(f"[red]Failed to load {tname}:[/red] {exc}")
            return 1

    console.print(f"\n[bold green]Done.[/bold green] {total_rows:,} total rows loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
