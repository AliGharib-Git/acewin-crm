from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_permission, get_current_org, get_current_user
from app.models import AgentActionStatus, Organization, Tag, User
from app.schemas import TagCreate, TagOut
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    return scoped(db, Tag, org).order_by(Tag.name).all()


@router.post("", response_model=TagOut, status_code=201)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_permission(db, current_user, "tags:create")
    existing = scoped(db, Tag, org).filter(Tag.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="A tag with this name already exists")
    tag = Tag(**payload.model_dump(), organization_id=org.id)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    record_action(
        db, current_user, "tags:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="tag", entity_id=tag.id, organization_id=org.id,
    )
    return tag


@router.delete("/{tag_id}", status_code=204)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    tag = get_or_404(db, Tag, tag_id, org, detail="Tag not found")
    enforce_permission(db, current_user, "tags:delete")
    db.delete(tag)
    db.commit()
    record_action(
        db, current_user, "tags:delete", source="api", status=AgentActionStatus.success,
        arguments={"tag_id": tag_id}, entity_type="tag", entity_id=tag_id, organization_id=org.id,
    )
    return None
