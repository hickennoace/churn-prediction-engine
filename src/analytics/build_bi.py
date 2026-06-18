"""Phase 5 — build the BI reporting views and export them to CSV for Power BI.

Executes every sql/*.sql file (in name order) to (re)create the reporting views/matviews,
then exports each reporting mart to powerbi/ChurnEngine/data/*.csv so the .pbip project
can import them (self-contained — no DB driver needed to open the report).

Usage:
    python -m src.analytics.build_bi
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import PROJECT_ROOT, get_engine  # noqa: E402

SQL_DIR = PROJECT_ROOT / "sql"
OUT_DIR = PROJECT_ROOT / "powerbi" / "ChurnEngine" / "data"

# Reporting mart -> SQL that feeds the CSV the dashboard imports.
EXPORTS = {
    "metrics": "SELECT * FROM business_metrics",
    "mrr_monthly": "SELECT * FROM v_mrr_monthly",
    "cohort_retention": "SELECT * FROM v_cohort_retention",
    "churn_by_segment": "SELECT * FROM v_churn_by_segment",
    "risk_distribution": "SELECT * FROM v_risk_distribution",
    "revenue_at_risk": "SELECT * FROM v_revenue_at_risk",
    "high_risk_customers": """
        SELECT r.msno, r.risk_score, r.churn_prob,
               f.city, f.gender, f.days_to_expiry, f.tenure_days,
               f.auto_renew_share, f.total_paid
        FROM customer_risk_scores r
        JOIN customer_features f USING (msno)
        ORDER BY r.risk_score DESC, r.churn_prob DESC
        LIMIT 200
    """,
}


def run_sql_files(engine) -> None:
    for path in sorted(SQL_DIR.glob("*.sql")):
        print(f"[bi] executing {path.name} ...", flush=True)
        # Strip full-line `--` comments BEFORE splitting on ';' so a semicolon inside
        # a comment can't truncate a statement.
        cleaned = "\n".join(
            ln for ln in path.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("--")
        )
        with engine.begin() as conn:
            for stmt in cleaned.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))


def export_csvs(engine) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, sql in EXPORTS.items():
        df = pd.read_sql(text(sql), engine)
        out = OUT_DIR / f"{name}.csv"
        df.to_csv(out, index=False, encoding="utf-8")
        print(f"[bi] exported {name:<20} {len(df):>5,} rows -> {out}")


def main() -> None:
    engine = get_engine()
    run_sql_files(engine)
    export_csvs(engine)
    print("\n[bi] OK — reporting views built and CSVs exported for Power BI.")


if __name__ == "__main__":
    main()
