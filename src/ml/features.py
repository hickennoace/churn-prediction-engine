"""Phase 3 — feature engineering (leak-free, as of 2017-02-28).

Builds the `customer_features` table: one row per customer, every feature derived ONLY
from transactions with transaction_date <= the cutoff (plus static member profile). This
guarantees no label leakage (the March-2017 renewal decision is excluded).

Usage:
    python -m src.ml.features
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import get_engine  # noqa: E402

CUTOFF = "2017-02-28"

FEATURES_SQL = f"""
DROP TABLE IF EXISTS customer_features;

CREATE TABLE customer_features AS
WITH tx AS (
    SELECT * FROM transactions WHERE transaction_date <= DATE '{CUTOFF}'
),
agg AS (
    SELECT
        msno,
        COUNT(*)                                            AS n_tx,
        (DATE '{CUTOFF}' - MIN(transaction_date))           AS tenure_days,
        (DATE '{CUTOFF}' - MAX(transaction_date))           AS recency_days,
        AVG(payment_plan_days)                              AS avg_plan_days,
        AVG(actual_amount_paid)                             AS avg_paid,
        AVG(plan_list_price - actual_amount_paid)           AS avg_discount,
        COUNT(DISTINCT payment_plan_days)                   AS n_distinct_plans,
        COUNT(DISTINCT payment_method_id)                   AS n_payment_methods,
        AVG(CASE WHEN is_auto_renew THEN 1.0 ELSE 0 END)    AS auto_renew_share,
        SUM(CASE WHEN is_cancel THEN 1 ELSE 0 END)          AS n_cancels,
        MAX(CASE WHEN is_cancel THEN 1 ELSE 0 END)          AS ever_cancelled,
        SUM(actual_amount_paid)                             AS total_paid,
        SUM(CASE WHEN actual_amount_paid = 0 THEN 1 ELSE 0 END) AS n_promo_tx,
        AVG(CASE WHEN payment_plan_days > 0
                 THEN actual_amount_paid::numeric / payment_plan_days * 30 END) AS avg_monthly_value
    FROM tx GROUP BY msno
),
last_tx AS (
    SELECT DISTINCT ON (msno)
        msno,
        payment_plan_days                       AS last_plan_days,
        actual_amount_paid                      AS last_paid,
        (is_auto_renew)::int                    AS last_auto_renew,
        (is_cancel)::int                        AS last_is_cancel,
        payment_method_id                       AS last_payment_method,
        (membership_expire_date - DATE '{CUTOFF}') AS days_to_expiry
    FROM tx
    ORDER BY msno, transaction_date DESC
)
SELECT
    c.msno,
    c.is_churn,
    -- static profile
    c.bd_clean,
    c.gender,
    c.city,
    c.registered_via,
    (DATE '{CUTOFF}' - c.registration_date)     AS account_age_days,
    -- aggregate behavior
    a.n_tx, a.tenure_days, a.recency_days, a.avg_plan_days, a.avg_paid, a.avg_discount,
    a.n_distinct_plans, a.n_payment_methods, a.auto_renew_share, a.n_cancels,
    a.ever_cancelled, a.total_paid, a.n_promo_tx, a.avg_monthly_value,
    -- most-recent snapshot
    l.last_plan_days, l.last_paid, l.last_auto_renew, l.last_is_cancel,
    l.last_payment_method, l.days_to_expiry
FROM customers c
JOIN agg a      USING (msno)
LEFT JOIN last_tx l USING (msno);

ALTER TABLE customer_features ADD PRIMARY KEY (msno);
"""


def main() -> None:
    engine = get_engine()
    print(f"[features] building customer_features (cutoff {CUTOFF}) ...", flush=True)
    with engine.begin() as conn:
        for stmt in (s.strip() for s in FEATURES_SQL.split(";")):
            if stmt:
                conn.execute(text(stmt))

    with engine.connect() as c:
        total = c.execute(text("SELECT COUNT(*) FROM customer_features")).scalar_one()
        labeled = c.execute(text("SELECT COUNT(*) FROM customer_features WHERE is_churn IS NOT NULL")).scalar_one()
        ncols = c.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='customer_features'")).scalar_one()
    print(f"[features] done: {total:,} customers, {labeled:,} labeled, {ncols} columns.")


if __name__ == "__main__":
    main()
