"""Service layer — the only place that touches the database. Returns plain dicts the
API maps to DTOs, so the raw schema is never exposed and queries stay parameterized."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def ping(engine: Engine) -> bool:
    with engine.connect() as c:
        return c.execute(text("SELECT 1")).scalar_one() == 1


def get_metrics(engine: Engine) -> dict[str, Any] | None:
    sql = text("""
        SELECT as_of_date, active_customers, mrr, arpu, monthly_churn_rate,
               avg_lifetime_months, ltv, arr
        FROM business_metrics ORDER BY as_of_date DESC LIMIT 1
    """)
    with engine.connect() as c:
        row = c.execute(sql).mappings().first()
    return dict(row) if row else None


def get_high_risk(engine: Engine, min_score: int, limit: int, offset: int) -> list[dict[str, Any]]:
    sql = text("""
        SELECT r.msno, r.risk_score, r.churn_prob,
               f.gender, f.city, f.days_to_expiry, f.auto_renew_share,
               f.is_churn AS actual_is_churn
        FROM customer_risk_scores r
        JOIN customer_features f USING (msno)
        WHERE r.risk_score >= :min_score
        ORDER BY r.risk_score DESC, r.churn_prob DESC
        LIMIT :limit OFFSET :offset
    """)
    with engine.connect() as c:
        rows = c.execute(sql, {"min_score": min_score, "limit": limit, "offset": offset}).mappings().all()
    return [dict(r) for r in rows]


def get_customer(engine: Engine, msno: str) -> dict[str, Any] | None:
    sql = text("""
        SELECT f.msno,
               r.risk_score, r.churn_prob, r.scored_at,
               f.is_churn AS actual_is_churn,
               f.gender, f.bd_clean, f.city, f.registered_via, f.account_age_days,
               f.n_tx, f.tenure_days, f.recency_days, f.auto_renew_share,
               f.n_cancels, f.total_paid, f.avg_monthly_value, f.days_to_expiry
        FROM customer_features f
        LEFT JOIN customer_risk_scores r USING (msno)
        WHERE f.msno = :msno
    """)
    with engine.connect() as c:
        row = c.execute(sql, {"msno": msno}).mappings().first()
    return dict(row) if row else None
