-- Phase 5 — cohort retention triangle.
-- Cohort = customer's first-transaction month. Retention(cohort, k) = % of the cohort
-- still active k months later. Active months derived by expanding the non-overlapping
-- coverage intervals. Materialized (heavy expand), then a view adds the retention %.

DROP MATERIALIZED VIEW IF EXISTS mv_cohort_retention CASCADE;

CREATE MATERIALIZED VIEW mv_cohort_retention AS
WITH cohort AS (
    SELECT msno, date_trunc('month', MIN(transaction_date))::date AS cohort_month
    FROM transactions
    GROUP BY msno
),
active_months AS (
    SELECT DISTINCT
        c.msno,
        date_trunc('month', gs)::date AS active_month
    FROM v_subscription_coverage c
    CROSS JOIN LATERAL generate_series(c.start_d, c.end_d - 1, INTERVAL '1 month') AS gs
),
joined AS (
    SELECT
        co.cohort_month,
        ((EXTRACT(YEAR  FROM age(a.active_month, co.cohort_month)) * 12)
       +  EXTRACT(MONTH FROM age(a.active_month, co.cohort_month)))::int AS month_offset,
        a.msno
    FROM active_months a
    JOIN cohort co USING (msno)
)
SELECT cohort_month, month_offset, COUNT(DISTINCT msno) AS active_customers
FROM joined
WHERE month_offset BETWEEN 0 AND 18
GROUP BY cohort_month, month_offset;

CREATE OR REPLACE VIEW v_cohort_retention AS
WITH sizes AS (
    SELECT cohort_month, active_customers AS cohort_size
    FROM mv_cohort_retention
    WHERE month_offset = 0
)
SELECT
    r.cohort_month,
    r.month_offset,
    r.active_customers,
    s.cohort_size,
    ROUND(100.0 * r.active_customers / NULLIF(s.cohort_size, 0), 1) AS retention_pct
FROM mv_cohort_retention r
JOIN sizes s USING (cohort_month)
ORDER BY r.cohort_month, r.month_offset;
