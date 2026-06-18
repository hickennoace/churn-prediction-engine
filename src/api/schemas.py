"""Pydantic response models (DTOs). The API returns only these curated shapes —
the raw database tables are never exposed directly."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class MetricsResponse(BaseModel):
    as_of_date: date
    currency: str = "NTD"
    active_customers: int
    mrr: float = Field(..., description="Monthly Recurring Revenue")
    arpu: float = Field(..., description="Average Revenue Per User / month")
    monthly_churn_rate: float
    avg_lifetime_months: float
    ltv: float = Field(..., description="Lifetime Value = ARPU / churn rate")
    arr: float = Field(..., description="Annualized Recurring Revenue (MRR x 12)")
    assumed_cac: float | None = Field(None, description="Assumed Customer Acquisition Cost (if supplied)")
    ltv_to_cac: float | None = Field(None, description="LTV : CAC ratio (only if assumed_cac supplied)")


class HighRiskCustomer(BaseModel):
    msno: str
    risk_score: int = Field(..., ge=1, le=100)
    churn_prob: float
    gender: str | None = None
    city: int | None = None
    days_to_expiry: int | None = None
    auto_renew_share: float | None = None
    actual_is_churn: bool | None = Field(None, description="Ground-truth label where known")


class HighRiskPage(BaseModel):
    min_score: int
    limit: int
    offset: int
    count: int
    items: list[HighRiskCustomer]


class CustomerDetail(BaseModel):
    msno: str
    # risk
    risk_score: int | None = None
    churn_prob: float | None = None
    scored_at: datetime | None = None
    actual_is_churn: bool | None = None
    # profile
    gender: str | None = None
    bd_clean: int | None = None
    city: int | None = None
    registered_via: int | None = None
    account_age_days: int | None = None
    # behavior summary
    n_tx: int | None = None
    tenure_days: int | None = None
    recency_days: int | None = None
    auto_renew_share: float | None = None
    n_cancels: int | None = None
    total_paid: float | None = None
    avg_monthly_value: float | None = None
    days_to_expiry: int | None = None
