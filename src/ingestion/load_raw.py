"""Phase 1 — Raw ingestion (KKBox Churn Prediction dataset).

Loads the user-provided KKBox CSVs from ``data/raw/`` *verbatim* into PostgreSQL
staging tables. Every column is loaded as ``TEXT`` — no cleaning, parsing, or type
coercion happens here. The goal is a faithful, auditable copy of the source; proper
typing and a clean relational schema are Phase 2's job.

Loading uses PostgreSQL's native ``COPY`` (via psycopg2) rather than ``pandas.to_sql``
because ``transactions`` alone is ~23M rows / 1.7GB — COPY streams the file with flat
memory and finishes in a minute or two.

A provenance column ``_source_file`` is appended to each table so that rows unioned
from multiple files (e.g. the original vs. the ``_v2`` competition refresh) remain
distinguishable downstream — the same ``msno`` can legitimately appear in both
``train.csv`` and ``train_v2.csv`` for different churn windows.

Staging tables:
    raw_members        <- members_v3.csv
    raw_transactions   <- transactions.csv + transactions_v2.csv
    raw_train          <- train.csv + train_v2.csv

Usage:
    python -m src.ingestion.load_raw                 # load all three tables
    python -m src.ingestion.load_raw --only raw_train
    python -m src.ingestion.load_raw --only raw_members raw_train
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy import text

# Support both "python -m src.ingestion.load_raw" and direct execution.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import DATA_RAW, get_engine  # noqa: E402

# Staging table -> source CSV file(s), loaded verbatim and unioned in file order.
STAGING: dict[str, list[str]] = {
    "raw_members": ["members_v3.csv"],
    "raw_transactions": ["transactions.csv", "transactions_v2.csv"],
    "raw_train": ["train.csv", "train_v2.csv"],
}

PROVENANCE_COL = "_source_file"


def _quote_ident(name: str) -> str:
    """Safely double-quote a SQL identifier (column/table name)."""
    return '"' + name.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    """Safely single-quote a SQL string literal (for DDL defaults)."""
    return "'" + value.replace("'", "''") + "'"


def read_header(path: Path) -> list[str]:
    """Return the CSV column names from the first line of a file."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def resolve_files(table: str) -> list[Path]:
    """Resolve and validate the source files for a staging table."""
    paths = []
    for fname in STAGING[table]:
        path = DATA_RAW / fname
        if not path.exists():
            raise FileNotFoundError(
                f"Expected source file for {table} not found: {path}. "
                f"Place the extracted KKBox CSVs in {DATA_RAW}."
            )
        paths.append(path)
    return paths


def load_table(table: str) -> int:
    """Create the staging table and COPY all its source files in. Returns row count."""
    paths = resolve_files(table)

    # Header comes from the first file; assert the rest match so we never silently
    # union files with mismatched schemas.
    columns = read_header(paths[0])
    for path in paths[1:]:
        other = read_header(path)
        if other != columns:
            raise RuntimeError(
                f"Header mismatch for {table}: {paths[0].name}={columns} "
                f"vs {path.name}={other}. Refusing to union mismatched files."
            )

    col_defs = ", ".join(f"{_quote_ident(c)} TEXT" for c in columns)
    col_list = ", ".join(_quote_ident(c) for c in columns)
    qtable = _quote_ident(table)

    engine = get_engine()

    # DDL via SQLAlchemy (autocommits in a transaction block).
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {qtable}"))
        conn.execute(
            text(
                f"CREATE TABLE {qtable} ({col_defs}, "
                f"{_quote_ident(PROVENANCE_COL)} TEXT)"
            )
        )

    # Bulk load via raw psycopg2 COPY — one stream per source file.
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        for path in paths:
            # Stamp provenance cheaply via a column DEFAULT (no per-row UPDATE).
            cur.execute(
                f"ALTER TABLE {qtable} ALTER COLUMN "
                f"{_quote_ident(PROVENANCE_COL)} SET DEFAULT {_quote_literal(path.name)}"
            )
            print(f"  [COPY] {path.name} -> {table} ...", flush=True)
            with path.open("r", encoding="utf-8", newline="") as fh:
                cur.copy_expert(
                    f"COPY {qtable} ({col_list}) FROM STDIN WITH (FORMAT csv, HEADER true)",
                    fh,
                )
        raw.commit()
    finally:
        raw.close()

    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {qtable}")).scalar_one())


def expected_rows(table: str) -> int:
    """Sum of data rows across a table's source files (line count minus header)."""
    total = 0
    for path in resolve_files(table):
        with path.open("r", encoding="utf-8", newline="") as fh:
            total += sum(1 for _ in fh) - 1
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Load raw KKBox CSVs into Postgres staging tables.")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=list(STAGING),
        help="Load only the named table(s) (default: all).",
    )
    args = parser.parse_args()

    tables = args.only or list(STAGING)
    print(f"[load_raw] Source dir : {DATA_RAW}")
    print(f"[load_raw] Tables     : {', '.join(tables)}\n")

    failures = []
    for table in tables:
        print(f"[load_raw] === {table} ({' + '.join(STAGING[table])}) ===")
        expected = expected_rows(table)
        loaded = load_table(table)
        status = "OK" if loaded == expected else "ROW COUNT MISMATCH"
        print(f"  expected={expected:,}  loaded={loaded:,}  -> {status}\n")
        if loaded != expected:
            failures.append((table, expected, loaded))

    if failures:
        for table, exp, got in failures:
            print(f"[load_raw] FAIL {table}: expected {exp:,}, loaded {got:,}", file=sys.stderr)
        raise SystemExit("[load_raw] One or more tables failed the row-count check.")

    print("[load_raw] OK — all tables loaded and row counts match.")


if __name__ == "__main__":
    main()
