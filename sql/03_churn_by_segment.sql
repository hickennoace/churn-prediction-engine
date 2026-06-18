-- Phase 5 — churn rate by business segment (city, registration channel, gender,
-- auto-renew behavior, plan length). One tidy long-format view for easy BI slicing.

CREATE OR REPLACE VIEW v_churn_by_segment AS
SELECT 'city' AS segment_type, city::text AS segment,
       COUNT(*) AS labeled, SUM((is_churn)::int) AS churned,
       ROUND(AVG((is_churn)::int) * 100, 2) AS churn_pct
FROM customer_features WHERE is_churn IS NOT NULL GROUP BY city

UNION ALL
SELECT 'registered_via', registered_via::text,
       COUNT(*), SUM((is_churn)::int), ROUND(AVG((is_churn)::int) * 100, 2)
FROM customer_features WHERE is_churn IS NOT NULL GROUP BY registered_via

UNION ALL
SELECT 'gender', COALESCE(gender, 'unknown'),
       COUNT(*), SUM((is_churn)::int), ROUND(AVG((is_churn)::int) * 100, 2)
FROM customer_features WHERE is_churn IS NOT NULL GROUP BY gender

UNION ALL
SELECT 'auto_renew',
       CASE WHEN auto_renew_share >= 0.5 THEN 'mostly auto-renew' ELSE 'mostly manual' END,
       COUNT(*), SUM((is_churn)::int), ROUND(AVG((is_churn)::int) * 100, 2)
FROM customer_features WHERE is_churn IS NOT NULL GROUP BY 2

UNION ALL
SELECT 'plan_length',
       CASE WHEN avg_plan_days <= 31 THEN '1-monthly'
            WHEN avg_plan_days <= 100 THEN '2-quarterly'
            ELSE '3-long-term' END,
       COUNT(*), SUM((is_churn)::int), ROUND(AVG((is_churn)::int) * 100, 2)
FROM customer_features WHERE is_churn IS NOT NULL GROUP BY 2
ORDER BY 1, 2;
