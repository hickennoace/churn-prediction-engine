"""Phase 3 — economic metrics (MRR / ARPU / LTV) as of the leak-free cutoff.

Computes the as-of-2017-02-28 snapshot. Monthly-equivalent value normalizes every plan
to 30 days: actual_amount_paid / payment_plan_days * 30 (validated stable across plan
lengths in docs/phase3-metrics-and-model.md). The monthly MRR *time series* / cohort
retention are deferred to Phase 5 (window-function SQL).

Currency: New Taiwan Dollar (NT$), KKBox's market.

Usage:
    python -m src.analytics.metrics
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import get_engine  # noqa: E402

CUTOFF = "2017-02-28"  # leak-free as-of date (predict the March-2017 expiry cohort)

# Reusable view: per-subscription monthly-equivalent value (valid plans only).
# Phase 5 BI queries can build the rolling-MRR time series on top of this.
VIEW_SQL = """
CREATE OR REPLACE VIEW v_subscription_value AS
SELECT
    msno,
    transaction_date,
    membership_expire_date,
    ROUND(actual_amount_paid::numeric / payment_plan_days * 30, 4) AS monthly_value
FROM transactions
WHERE plan_days_valid AND expire_date_valid;
"""

SNAPSHOT_SQL = f"""
WITH active AS (
    SELECT DISTINCT ON (msno) msno, monthly_value
    FROM v_subscription_value
    WHERE transaction_date <= DATE '{CUTOFF}'
      AND membership_expire_date > DATE '{CUTOFF}'
    ORDER BY msno, transaction_date DESC
)
SELECT COUNT(*)            AS active_customers,
       ROUND(SUM(monthly_value))      AS mrr,
       ROUND(AVG(monthly_value), 2)   AS arpu
FROM active;
"""


def main() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(VIEW_SQL))

    with engine.connect() as c:
        active_customers, mrr, arpu = c.execute(text(SNAPSHOT_SQL)).one()
        churn_rate = float(c.execute(text(
            "SELECT AVG(CASE WHEN is_churn THEN 1.0 ELSE 0 END) FROM customers WHERE is_churn IS NOT NULL"
        )).scalar_one())

    arpu = float(arpu)
    mrr = float(mrr)
    avg_lifetime = 1.0 / churn_rate
    ltv = arpu * avg_lifetime

    # Persist a single-row snapshot so the API can serve /metrics instantly
    # (the live snapshot query scans millions of rows — too slow per request).
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS business_metrics (
                as_of_date DATE PRIMARY KEY,
                active_customers INT, mrr NUMERIC, arpu NUMERIC,
                monthly_churn_rate NUMERIC, avg_lifetime_months NUMERIC,
                ltv NUMERIC, arr NUMERIC, computed_at TIMESTAMP DEFAULT now())
        """))
        conn.execute(text("DELETE FROM business_metrics WHERE as_of_date = :d"), {"d": CUTOFF})
        conn.execute(text("""
            INSERT INTO business_metrics
                (as_of_date, active_customers, mrr, arpu, monthly_churn_rate,
                 avg_lifetime_months, ltv, arr)
            VALUES (:d, :ac, :mrr, :arpu, :cr, :life, :ltv, :arr)
        """), {"d": CUTOFF, "ac": active_customers, "mrr": mrr, "arpu": arpu,
               "cr": churn_rate, "life": avg_lifetime, "ltv": ltv, "arr": mrr * 12})

    print(f"[metrics] As-of date            : {CUTOFF} (leak-free cutoff)")
    print(f"[metrics] Active customers       : {active_customers:,}")
    print(f"[metrics] MRR                     : NT$ {mrr:,.0f} / month")
    print(f"[metrics] ARPU                    : NT$ {arpu:,.2f} / customer / month")
    print(f"[metrics] Monthly churn rate      : {churn_rate*100:.2f}%")
    print(f"[metrics] Avg customer lifetime   : {avg_lifetime:.1f} months")
    print(f"[metrics] LTV (ARPU / churn)      : NT$ {ltv:,.0f} / customer")
    print(f"[metrics] Annualized recurring rev : NT$ {mrr*12:,.0f} (MRR x 12)")


if __name__ == "__main__":
    main()
