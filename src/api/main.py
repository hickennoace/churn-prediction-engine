"""Phase 4 — FastAPI read-only API over the churn engine.

Exposes curated business metrics and customer risk scores. All access goes through the
service layer (src/api/service.py); the database is never exposed directly. Endpoints
return Pydantic DTOs and auto-generate OpenAPI/Swagger docs at /docs.

Run:
    uvicorn src.api.main:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.api import service  # noqa: E402
from src.api.schemas import CustomerDetail, HighRiskPage, MetricsResponse  # noqa: E402
from src.config import get_engine  # noqa: E402

app = FastAPI(
    title="Customer Churn Prediction & Business Performance Engine",
    version="1.0.0",
    description="Read-only API serving SaaS economics (MRR/ARPU/LTV) and 1-100 churn risk scores.",
)
engine = get_engine()


@app.get("/", tags=["meta"])
def root():
    return {"service": app.title, "version": app.version, "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health():
    try:
        ok = service.ping(engine)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    return {"status": "ok" if ok else "degraded"}


@app.get("/metrics", response_model=MetricsResponse, tags=["analytics"])
def metrics(
    cac: float | None = Query(None, gt=0, description="Optional assumed CAC (NT$); returns LTV:CAC when supplied."),
):
    """Business metrics snapshot. CAC is not in the source data, so LTV:CAC is only
    returned when you supply an explicit assumed `cac` (no value is fabricated)."""
    m = service.get_metrics(engine)
    if m is None:
        raise HTTPException(status_code=503, detail="metrics not computed yet (run src.analytics.metrics)")
    resp = MetricsResponse(**m)
    if cac is not None:
        resp.assumed_cac = cac
        resp.ltv_to_cac = round(resp.ltv / cac, 2)
    return resp


@app.get("/customers/high-risk", response_model=HighRiskPage, tags=["customers"])
def high_risk(
    min_score: int = Query(80, ge=1, le=100, description="Minimum 1-100 risk score."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Highest-risk customers, descending by risk score (paginated)."""
    items = service.get_high_risk(engine, min_score=min_score, limit=limit, offset=offset)
    return HighRiskPage(min_score=min_score, limit=limit, offset=offset, count=len(items), items=items)


@app.get("/customer", response_model=CustomerDetail, tags=["customers"])
def customer(msno: str = Query(..., description="Customer id (base64 hash). Query param avoids '/' path issues.")):
    """Full profile + risk score for one customer. 404 if unknown."""
    c = service.get_customer(engine, msno)
    if c is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return c
