-- Phase 5 — risk-score distribution and expected revenue at risk.
-- v_risk_distribution: customers per 10-point risk band (+ % of base via window function).
-- v_revenue_at_risk: each band's current MRR and expected monthly revenue lost to churn
--   (MRR x churn probability) — the headline executive number.

CREATE OR REPLACE VIEW v_risk_distribution AS
SELECT
    width_bucket(risk_score, 1, 101, 10)            AS band,
    (width_bucket(risk_score, 1, 101, 10) - 1) * 10 + 1 AS score_lo,
    width_bucket(risk_score, 1, 101, 10) * 10       AS score_hi,
    COUNT(*)                                        AS customers,
    ROUND(AVG(churn_prob)::numeric, 4)              AS avg_churn_prob,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_base
FROM customer_risk_scores
GROUP BY band
ORDER BY band;

CREATE OR REPLACE VIEW v_revenue_at_risk AS
WITH current_sub AS (
    SELECT DISTINCT ON (msno) msno, monthly_value
    FROM v_subscription_value
    WHERE transaction_date <= DATE '2017-02-28'
      AND membership_expire_date > DATE '2017-02-28'
    ORDER BY msno, transaction_date DESC
)
SELECT
    width_bucket(r.risk_score, 1, 101, 10)                       AS band,
    (width_bucket(r.risk_score, 1, 101, 10) - 1) * 10 + 1        AS score_lo,
    COUNT(*)                                                     AS active_customers,
    ROUND(SUM(cs.monthly_value))                                AS mrr_in_band,
    ROUND(SUM(cs.monthly_value * r.churn_prob)::numeric)        AS expected_monthly_revenue_at_risk
FROM customer_risk_scores r
JOIN current_sub cs USING (msno)
GROUP BY band
ORDER BY band;
