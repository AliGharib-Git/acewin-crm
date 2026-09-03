"""
Enterprise OKR Engine API.

    Objectives -> Key Results -> Progress -> Department Score -> Company Score

Scores, risk levels, and priority order are always computed live from
real data (see app/okr/engine.py) -- never stored. Only the Objectives,
Key Results, and progress check-ins themselves are persisted. Every
create/update/delete goes through the same RBAC + audit-log pipeline
as the rest of the CRM (app/ai/permissions.py, app/audit.py).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_feature, enforce_permission, get_current_org, get_current_user
from app.kpi.engine import KPI_DEFINITIONS
from app.models import (
    AgentActionStatus,
    KeyResult,
    KeyResultType,
    KeyResultUpdate,
    Objective,
    ObjectiveStatus,
    Organization,
    User,
)
from app.okr.engine import (
    ObjectiveScore,
    compute_company_score,
    compute_department_score,
    compute_objective_score,
    key_result_current_value,
    key_result_score,
    known_kpi_keys,
    parse_period,
    rank_by_priority,
)
from app.okr.explain import explain_objective
from app.tenancy import get_or_404, scoped
from app.schemas import (
    KeyResultCreate,
    KeyResultEdit,
    KeyResultOut,
    KeyResultUpdateIn,
    KeyResultUpdateOut,
    ObjectiveCreate,
    ObjectiveEdit,
    ObjectiveExplanation,
    ObjectiveOut,
    OKRScoreboard,
    UserBrief,
)

router = APIRouter(tags=["okrs"])


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _kr_update_out(update: KeyResultUpdate) -> KeyResultUpdateOut:
    return KeyResultUpdateOut(
        id=update.id,
        value=float(update.value),
        note=update.note,
        created_by_name=update.created_by.full_name if update.created_by else None,
        created_at=update.created_at,
    )


def _kr_out(db: Session, kr: KeyResult) -> KeyResultOut:
    return KeyResultOut(
        id=kr.id,
        objective_id=kr.objective_id,
        title=kr.title,
        measurement_type=kr.measurement_type.value,
        weight=float(kr.weight),
        unit=kr.unit,
        baseline_value=float(kr.baseline_value) if kr.baseline_value is not None else None,
        target_value=float(kr.target_value) if kr.target_value is not None else None,
        current_value=key_result_current_value(db, kr),
        is_done=kr.is_done,
        linked_kpi_key=kr.linked_kpi_key,
        owner=UserBrief.model_validate(kr.owner) if kr.owner else None,
        score_pct=round(key_result_score(db, kr) * 100, 1),
        updates=[_kr_update_out(u) for u in kr.updates],
    )


def _objective_out(db: Session, objective: Objective, score: ObjectiveScore | None = None) -> ObjectiveOut:
    score = score or compute_objective_score(db, objective)
    return ObjectiveOut(
        id=objective.id,
        title=objective.title,
        description=objective.description,
        department=objective.department,
        period_key=objective.period_key,
        start_date=objective.start_date,
        end_date=objective.end_date,
        status=objective.status.value,
        owner=UserBrief.model_validate(objective.owner) if objective.owner else None,
        created_by=UserBrief.model_validate(objective.created_by) if objective.created_by else None,
        key_results=[_kr_out(db, kr) for kr in objective.key_results],
        score_pct=score.score_pct,
        expected_pct=score.expected_pct,
        gap_pct=score.gap_pct,
        risk_level=score.risk_level,
        days_remaining=score.days_remaining,
        created_at=objective.created_at,
        updated_at=objective.updated_at,
    )


def _get_objective_or_404(db: Session, objective_id: int, org: Organization) -> Objective:
    return get_or_404(db, Objective, objective_id, org, detail="Objective not found")


def _get_kr_or_404(db: Session, objective_id: int, kr_id: int, org: Organization) -> KeyResult:
    # Reach the Key Result only through an objective already confirmed
    # to belong to this organization -- KeyResult itself has no
    # organization_id column, so this join is the only thing standing
    # between "my objective's key result" and "any tenant's key result
    # that happens to share this numeric id".
    kr = (
        db.query(KeyResult)
        .join(Objective, KeyResult.objective_id == Objective.id)
        .filter(KeyResult.id == kr_id, KeyResult.objective_id == objective_id, Objective.organization_id == org.id)
        .first()
    )
    if kr is None:
        raise HTTPException(status_code=404, detail="Key Result not found")
    return kr


# ---------------------------------------------------------------------------
# Objectives
# ---------------------------------------------------------------------------


@router.get("/api/objectives", response_model=list[ObjectiveOut])
def list_objectives(
    period_key: str | None = None,
    department: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    query = scoped(db, Objective, org)
    if period_key:
        query = query.filter(Objective.period_key == period_key)
    if department:
        query = query.filter(Objective.department == department)
    objectives = query.order_by(Objective.department, Objective.id).all()
    return [_objective_out(db, o) for o in objectives]


@router.post("/api/objectives", response_model=ObjectiveOut, status_code=201)
def create_objective(
    payload: ObjectiveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    enforce_permission(db, current_user, "objectives:create")
    try:
        start_date, end_date = parse_period(payload.period_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    objective = Objective(
        organization_id=org.id,
        title=payload.title,
        description=payload.description,
        department=payload.department,
        period_key=payload.period_key,
        start_date=start_date,
        end_date=end_date,
        status=ObjectiveStatus.active,
        owner_id=payload.owner_id or current_user.id,
        created_by_id=current_user.id,
    )
    db.add(objective)
    db.commit()
    db.refresh(objective)

    record_action(
        db, current_user, "objectives:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="objective", entity_id=objective.id,
    )
    return _objective_out(db, objective)


@router.get("/api/objectives/{objective_id}", response_model=ObjectiveOut)
def get_objective(
    objective_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    return _objective_out(db, _get_objective_or_404(db, objective_id, org))


@router.patch("/api/objectives/{objective_id}", response_model=ObjectiveOut)
def update_objective(
    objective_id: int,
    payload: ObjectiveEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    objective = _get_objective_or_404(db, objective_id, org)
    enforce_permission(db, current_user, "objectives:update", {"objective_id": objective_id})

    data = payload.model_dump(exclude_unset=True)
    previous_state = {k: (getattr(objective, k).value if hasattr(getattr(objective, k), "value") else getattr(objective, k)) for k in data}
    if "status" in data:
        data["status"] = ObjectiveStatus(data["status"])
    for field, value in data.items():
        setattr(objective, field, value)
    db.commit()
    db.refresh(objective)

    record_action(
        db, current_user, "objectives:update", source="api", status=AgentActionStatus.success,
        arguments={"objective_id": objective_id, **payload.model_dump(exclude_unset=True)},
        previous_state=previous_state, entity_type="objective", entity_id=objective.id,
    )
    return _objective_out(db, objective)


@router.delete("/api/objectives/{objective_id}", status_code=204)
def delete_objective(
    objective_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    objective = _get_objective_or_404(db, objective_id, org)
    enforce_permission(db, current_user, "objectives:delete")
    db.delete(objective)
    db.commit()
    record_action(
        db, current_user, "objectives:delete", source="api", status=AgentActionStatus.success,
        arguments={"objective_id": objective_id}, entity_type="objective", entity_id=objective_id,
    )
    return None


# ---------------------------------------------------------------------------
# Key Results
# ---------------------------------------------------------------------------


@router.post("/api/objectives/{objective_id}/key-results", response_model=KeyResultOut, status_code=201)
def create_key_result(
    objective_id: int,
    payload: KeyResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    _get_objective_or_404(db, objective_id, org)
    enforce_permission(db, current_user, "key_results:create", {"objective_id": objective_id})

    if payload.linked_kpi_key and payload.linked_kpi_key not in KPI_DEFINITIONS:
        raise HTTPException(status_code=400, detail=f"Unknown KPI '{payload.linked_kpi_key}'")
    measurement_type = KeyResultType(payload.measurement_type)
    if measurement_type == KeyResultType.metric and payload.target_value is None and not payload.linked_kpi_key:
        raise HTTPException(status_code=400, detail="A metric Key Result needs a target_value (or a linked_kpi_key)")

    kr = KeyResult(
        objective_id=objective_id,
        title=payload.title,
        measurement_type=measurement_type,
        weight=payload.weight,
        unit=payload.unit,
        baseline_value=payload.baseline_value,
        target_value=payload.target_value,
        current_value=payload.current_value if payload.current_value is not None else payload.baseline_value,
        linked_kpi_key=payload.linked_kpi_key,
        owner_id=payload.owner_id,
    )
    db.add(kr)
    db.commit()
    db.refresh(kr)

    record_action(
        db, current_user, "key_results:create", source="api", status=AgentActionStatus.success,
        arguments={"objective_id": objective_id, **payload.model_dump()}, entity_type="key_result", entity_id=kr.id,
    )
    return _kr_out(db, kr)


@router.patch("/api/objectives/{objective_id}/key-results/{kr_id}", response_model=KeyResultOut)
def update_key_result(
    objective_id: int,
    kr_id: int,
    payload: KeyResultEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    kr = _get_kr_or_404(db, objective_id, kr_id, org)
    enforce_permission(db, current_user, "key_results:update", {"key_result_id": kr_id})

    data = payload.model_dump(exclude_unset=True)
    previous_state = {k: getattr(kr, k) for k in data}
    for field, value in data.items():
        setattr(kr, field, value)
    db.commit()
    db.refresh(kr)

    record_action(
        db, current_user, "key_results:update", source="api", status=AgentActionStatus.success,
        arguments={"key_result_id": kr_id, **data}, previous_state=previous_state,
        entity_type="key_result", entity_id=kr.id,
    )
    return _kr_out(db, kr)


@router.delete("/api/objectives/{objective_id}/key-results/{kr_id}", status_code=204)
def delete_key_result(
    objective_id: int,
    kr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    kr = _get_kr_or_404(db, objective_id, kr_id, org)
    enforce_permission(db, current_user, "key_results:delete", {"key_result_id": kr_id})
    db.delete(kr)
    db.commit()
    record_action(
        db, current_user, "key_results:delete", source="api", status=AgentActionStatus.success,
        arguments={"key_result_id": kr_id}, entity_type="key_result", entity_id=kr_id,
    )
    return None


@router.post("/api/objectives/{objective_id}/key-results/{kr_id}/progress", response_model=KeyResultOut)
def record_progress(
    objective_id: int,
    kr_id: int,
    payload: KeyResultUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    kr = _get_kr_or_404(db, objective_id, kr_id, org)
    enforce_permission(db, current_user, "key_results:progress", {"key_result_id": kr_id})
    if kr.linked_kpi_key:
        raise HTTPException(
            status_code=400,
            detail="This Key Result is linked to a live KPI and updates automatically -- it can't be updated manually.",
        )
    if kr.measurement_type != KeyResultType.metric:
        raise HTTPException(status_code=400, detail="Only metric Key Results take progress check-ins; toggle is_done for a milestone.")

    update = KeyResultUpdate(key_result_id=kr.id, value=payload.value, note=payload.note, created_by_id=current_user.id)
    db.add(update)
    kr.current_value = payload.value
    db.commit()
    db.refresh(kr)

    record_action(
        db, current_user, "key_results:progress", source="api", status=AgentActionStatus.success,
        arguments={"key_result_id": kr_id, "value": payload.value, "note": payload.note},
        entity_type="key_result", entity_id=kr.id,
    )
    return _kr_out(db, kr)


# ---------------------------------------------------------------------------
# Scoreboard + AI explanation
# ---------------------------------------------------------------------------


@router.get("/api/okrs/scoreboard", response_model=OKRScoreboard)
def scoreboard(
    period_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    objectives = scoped(db, Objective, org).filter(Objective.period_key == period_key).all()
    scores = [compute_objective_score(db, o) for o in objectives]
    ranked = rank_by_priority(scores)

    by_department: dict[str, list[ObjectiveScore]] = {}
    for s in scores:
        by_department.setdefault(s.objective.department, []).append(s)
    department_scores = {dept: compute_department_score(dept_scores) for dept, dept_scores in by_department.items()}
    company_score = compute_company_score(department_scores)

    return OKRScoreboard(
        period_key=period_key,
        company_score=company_score,
        department_scores=department_scores,
        objectives=[_objective_out(db, s.objective, s) for s in ranked],
    )


@router.get("/api/okrs/kpi-options", response_model=list[str])
def kpi_link_options(current_user: User = Depends(get_current_user)):
    """KPI keys available for linking a metric Key Result -- backs the
    frontend's dropdown so it never has to hardcode or guess valid keys."""
    return known_kpi_keys()


@router.post("/api/objectives/{objective_id}/explain", response_model=ObjectiveExplanation)
def explain(
    objective_id: int,
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "okr.management")
    objective = _get_objective_or_404(db, objective_id, org)
    score = compute_objective_score(db, objective)
    text, generated_by = explain_objective(db, objective, score, language=lang)
    return ObjectiveExplanation(objective_id=objective_id, explanation=text, generated_by=generated_by)
