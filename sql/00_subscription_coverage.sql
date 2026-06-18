-- Phase 5 — reusable building block.
-- Turns each customer's transactions into a NON-OVERLAPPING active timeline: a
-- subscription is "active" from its transaction_date until the earlier of its own
-- expiry or the customer's NEXT transaction (early renewals supersede the old plan).
-- Uses the LEAD window function. Built on v_subscription_value (created by metrics.py).

CREATE OR REPLACE VIEW v_subscription_coverage AS
WITH seq AS (
    SELECT
        msno,
        transaction_date,
        membership_expire_date,
        monthly_value,
        LEAD(transaction_date) OVER (PARTITION BY msno ORDER BY transaction_date) AS next_txn
    FROM v_subscription_value
)
SELECT
    msno,
    monthly_value,
    transaction_date AS start_d,
    -- active until the earlier of own expiry or next transaction, never before start
    GREATEST(
        transaction_date + 1,
        LEAST(membership_expire_date, COALESCE(next_txn, membership_expire_date))
    ) AS end_d
FROM seq;
