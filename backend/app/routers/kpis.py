"""
Enterprise KPI Engine API.

Every value returned by GET here is computed live from real CRM data
(see app/kpi/engine.py) -- nothing is cached or fabricated, and every
computation is scoped to the caller's organization. The only thing
stored is the *target* for each KPI (KPITarget), which only an
admin may set (`kpis:update_target` -- admin-only, no member grant, no
ownership dimension since a KPI target is an org-wide setting, not a
per-record one).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_feature, enforce_permission, get_current_org, get_current_user
from app.kpi.engine import KPI_DEFINITIONS, KPIResult, compute_all_kpis, compute_kpi
from app.kpi.explain import explain_kpi
from app.models import AgentActionStatus, KPITarget, Organization, User
from app.schemas import KPIExplanation, KPIOut, KPIStatsOut, KPITargetUpdate

router = APIRouter(prefix="/api/kpis", tags=["kpis"])


def _to_out(result: KPIResult) -> KPIOut:
    return KPIOut(
        key=result.key,
        name=result.name,
        description=result.description,
        department=result.department,
        unit=result.unit,
        higher_is_better=result.higher_is_better,
        supports_trend=result.supports_trend,
        current_value=result.current_value,
        previous_value=result.previous_value,
        change_pct=result.change_pct,
        trend=result.trend,
        target=result.target,
        risk_level=result.risk_level,
        prediction_next=result.prediction_next,
        prediction_low=result.prediction_low,
        prediction_high=result.prediction_high,
        stats=KPIStatsOut(**vars(result.stats)) if result.stats else None,
        breakdown=result.breakdown,
    )


def _require_known_kpi(kpi_key: str) -> None:
    if kpi_key not in KPI_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Unknown KPI '{kpi_key}'")


@router.get("", response_model=list[KPIOut])
def list_kpis(
    months: int = Query(6, ge=3, le=24),
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "kpi.management")
    return [_to_out(r) for r in compute_all_kpis(db, org.id, language=lang, months=months)]


@router.get("/{kpi_key}", response_model=KPIOut)
def get_kpi(
    kpi_key: str,
    months: int = Query(6, ge=3, le=24),
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    _require_known_kpi(kpi_key)
    enforce_feature(db, org, "kpi.management")
    return _to_out(compute_kpi(db, org.id, kpi_key, language=lang, months=months))


@router.put("/{kpi_key}/target", response_model=KPIOut)
def set_target(
    kpi_key: str,
    payload: KPITargetUpdate,
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    _require_known_kpi(kpi_key)
    enforce_feature(db, org, "kpi.management")
    enforce_permission(db, current_user, "kpis:update_target")

    row = db.query(KPITarget).filter(KPITarget.organization_id == org.id, KPITarget.kpi_key == kpi_key).first()
    previous_value = float(row.target_value) if row else None
    if row is None:
        row = KPITarget(organization_id=org.id, kpi_key=kpi_key, target_value=payload.target_value, updated_by_id=current_user.id)
        db.add(row)
    else:
        row.target_value = payload.target_value
        row.updated_by_id = current_user.id
    db.commit()
    db.refresh(row)

    record_action(
        db,
        current_user,
        "kpis:update_target",
        source="api",
        status=AgentActionStatus.success,
        arguments={"kpi_key": kpi_key, "target_value": payload.target_value},
        previous_state={"target_value": previous_value} if previous_value is not None else None,
        entity_type="kpi_target",
        entity_id=row.id,
        organization_id=org.id,
    )
    return _to_out(compute_kpi(db, org.id, kpi_key, language=lang))


@router.post("/{kpi_key}/explain", response_model=KPIExplanation)
def explain(
    kpi_key: str,
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    _require_known_kpi(kpi_key)
    enforce_feature(db, org, "kpi.management")
    result = compute_kpi(db, org.id, kpi_key, language=lang)
    text, generated_by = explain_kpi(result, language=lang)
    return KPIExplanation(kpi_key=kpi_key, explanation=text, generated_by=generated_by)
