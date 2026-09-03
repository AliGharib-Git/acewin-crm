from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import record_action
from app.database import get_db
from app.deps import get_current_admin, get_current_org, get_current_user
from app.models import AgentActionStatus, Deal, Organization, PipelineStage, User
from app.schemas import PipelineStageCreate, PipelineStageOut, PipelineStageUpdate
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/pipeline-stages", tags=["pipeline"])


@router.get("", response_model=list[PipelineStageOut])
def list_stages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    return scoped(db, PipelineStage, org).order_by(PipelineStage.order).all()


@router.post("", response_model=PipelineStageOut, status_code=201)
def create_stage(
    payload: PipelineStageCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    stage = PipelineStage(**payload.model_dump(), organization_id=org.id)
    db.add(stage)
    db.commit()
    db.refresh(stage)
    record_action(
        db, admin, "pipeline_stages:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="pipeline_stage", entity_id=stage.id, organization_id=org.id,
    )
    return stage


@router.patch("/{stage_id}", response_model=PipelineStageOut)
def update_stage(
    stage_id: int,
    payload: PipelineStageUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    stage = get_or_404(db, PipelineStage, stage_id, org, detail="Stage not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(stage, field, value)
    db.commit()
    db.refresh(stage)
    record_action(
        db, admin, "pipeline_stages:update", source="api", status=AgentActionStatus.success,
        arguments={"stage_id": stage_id, **data}, entity_type="pipeline_stage", entity_id=stage.id, organization_id=org.id,
    )
    return stage


@router.delete("/{stage_id}", status_code=204)
def delete_stage(
    stage_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    stage = get_or_404(db, PipelineStage, stage_id, org, detail="Stage not found")
    deals_in_stage = scoped(db, Deal, org).filter(Deal.stage_id == stage_id).count()
    if deals_in_stage > 0:
        raise HTTPException(status_code=400, detail="Move or delete the deals in this stage before removing it")
    db.delete(stage)
    db.commit()
    record_action(
        db, admin, "pipeline_stages:delete", source="api", status=AgentActionStatus.success,
        arguments={"stage_id": stage_id}, entity_type="pipeline_stage", entity_id=stage_id, organization_id=org.id,
    )
    return None
