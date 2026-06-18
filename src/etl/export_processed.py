"""Phase 2 — persist a portable snapshot of the clean data to data/processed/.

Exports the small ``customers`` table to Parquet for fast pandas/EDA use in Phase 3.
The 23M-row ``transactions`` table is deliberately NOT exported here: it lives in
PostgreSQL (indexed), which is the correct access path for downstream metrics/ML — a
columnar copy would only duplicate disk for no benefit.

Usage:
    python -m src.etl.export_processed
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import DATA_PROCESSED, get_engine  # noqa: E402


def main() -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    engine = get_engine()

    out = DATA_PROCESSED / "customers.parquet"
    df = pd.read_sql("SELECT * FROM customers", engine)
    df.to_parquet(out, index=False)
    print(f"[export] customers -> {out}  ({len(df):,} rows, {df.shape[1]} cols)")
    print("[export] transactions: kept in PostgreSQL (indexed) — not exported by design.")


if __name__ == "__main__":
    main()
