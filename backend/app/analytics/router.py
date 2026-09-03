"""
ACEWIN Analytics Engine router (Layer 3).

Exposes the AI modules in app/analytics/models.py as REST endpoints. All
modules are trained/evaluated against the real Olist dataset in
backend/data/olist/ -- if that data is missing, endpoints return a clear
503 rather than fabricating numbers.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics import models
from app.analytics.loader import DatasetNotFoundError, clear_cache
from app.database import get_db
from app.deps import get_current_org, get_current_user
from app.models import Deal, Organization, PipelineStage, User
from app.tenancy import scoped

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_lang(lang: str = Query("en", pattern="^(en|fa)$")) -> str:
    """Language for all human-readable analytics fields."""
    return lang


def _guarded(fn, *args, **kwargs) -> dict:
    try:
        return fn(*args, **kwargs)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/cache/clear", tags=["analytics"])
def reset_cache(current_user: User = Depends(get_current_user)):
    clear_cache()
    return {"status": "cache cleared"}


@router.get("/segmentation")
def segmentation(lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.customer_segmentation, lang=lang)


@router.get("/lead-scoring")
def lead_scoring(top_n: int = Query(20, ge=1, le=200), lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.lead_scoring, top_n=top_n, lang=lang)


@router.get("/clv")
def clv(top_n: int = Query(20, ge=1, le=200), lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.clv_prediction, top_n=top_n, lang=lang)


@router.get("/churn")
def churn(
    window_days: int = Query(180, ge=30, le=730),
    top_n: int = Query(20, ge=1, le=200),
    lang: str = Depends(get_lang),
    current_user: User = Depends(get_current_user),
):
    return _guarded(models.churn_prediction, churn_window_days=window_days, top_n=top_n, lang=lang)


@router.get("/deal-success")
def deal_success(
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    """Scores every open (not won/lost) CRM Core deal in the caller's organization."""
    open_deals = (
        scoped(db, Deal, org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(PipelineStage.is_won.is_(False), PipelineStage.is_lost.is_(False))
        .all()
    )
    stage_order = {s.id: s.order for s in scoped(db, PipelineStage, org).all()}
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    payload = []
    for d in open_deals:
        created = d.created_at if d.created_at and d.created_at.tzinfo else (
            d.created_at.replace(tzinfo=timezone.utc) if d.created_at else now
        )
        payload.append(
            {
                "deal_id": d.id,
                "title": d.title,
                "value": float(d.value),
                "stage_order": stage_order.get(d.stage_id, 0),
                "days_in_stage": max(0, (now - created).days),
                "contact_order_count": len(d.contact.activities) if d.contact and d.contact.activities else 0,
            }
        )
    return _guarded(models.deal_success_prediction, payload, lang=lang)


@router.get("/revenue-forecast")
def revenue_forecast(months_ahead: int = Query(3, ge=1, le=12), lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.revenue_forecast, months_ahead=months_ahead, lang=lang)


@router.get("/sales-trends")
def sales_trends(lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.sales_trend_analysis, lang=lang)


@router.get("/customer-behaviour")
def customer_behaviour(lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.customer_behaviour_analysis, lang=lang)


@router.get("/risk-detection")
def risk_detection(top_n: int = Query(20, ge=1, le=200), lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.risk_detection, top_n=top_n, lang=lang)


@router.get("/next-best-action")
def next_best_action(top_n: int = Query(20, ge=1, le=200), lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.next_best_action, top_n=top_n, lang=lang)


@router.get("/business-performance")
def business_performance(lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.business_performance_evaluation, lang=lang)


@router.get("/executive-insights")
def executive_insights(lang: str = Depends(get_lang), current_user: User = Depends(get_current_user)):
    return _guarded(models.executive_insights, lang=lang)
