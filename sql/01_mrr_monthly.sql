-- Phase 5 — monthly MRR time series (rolling MRR) with month-over-month growth.
-- Built on the non-overlapping v_subscription_coverage. Materialized because it scans
-- the full transaction history; the wrapper view adds LAG-based growth (window function).

DROP MATERIALIZED VIEW IF EXISTS mv_mrr_monthly CASCADE;

CREATE MATERIALIZED VIEW mv_mrr_monthly AS
WITH months AS (
    SELECT generate_series(DATE '2015-01-01', DATE '2017-03-01', INTERVAL '1 month')::date AS month
)
SELECT
    m.month,
    COUNT(DISTINCT c.msno)                                            AS active_customers,
    ROUND(SUM(c.monthly_value))                                       AS mrr,
    ROUND(SUM(c.monthly_value) / NULLIF(COUNT(DISTINCT c.msno), 0), 2) AS arpu
FROM months m
JOIN v_subscription_coverage c
  ON c.start_d < (m.month + INTERVAL '1 month')
 AND c.end_d   > m.month
GROUP BY m.month;

CREATE OR REPLACE VIEW v_mrr_monthly AS
SELECT
    month,
    active_customers,
    mrr,
    arpu,
    mrr - LAG(mrr) OVER (ORDER BY month)                                              AS mrr_mom_change,
    ROUND(100.0 * (mrr - LAG(mrr) OVER (ORDER BY month))
          / NULLIF(LAG(mrr) OVER (ORDER BY month), 0), 2)                             AS mrr_mom_pct
FROM mv_mrr_monthly
ORDER BY month;
