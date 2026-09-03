"""
Unified audit trail + undo, covering both the Copilot Action Agent and
the REST API.

Every write anywhere in ACEWIN -- a human clicking "Delete" in the UI,
or the Copilot calling a tool -- is recorded by app.audit.record_action
(see app/audit.py) into the same AgentActionLog table, distinguished
by `source` ("api" | "copilot"). This router only ever *reads* that
trail and, for undoable entries (currently: Copilot tool calls that
registered an undo_fn -- see app/ai/tools.py), replays the tool's own
registered undo function. It never mutates CRM data directly, keeping
a single source of truth for "how do we reverse action X" in
app/ai/tools.py itself.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.ai.tools import ToolContext, ToolError, undo_action
from app.database import get_db
from app.deps import get_current_org, get_current_user
from app.models import AgentActionLog, Organization, User, UserRole
from app.schemas import AgentActionLogOut, Page
from app.tenancy import scoped

router = APIRouter(prefix="/api/agent-actions", tags=["agent-actions"])


def _to_out(log: AgentActionLog) -> AgentActionLogOut:
    return AgentActionLogOut(
        id=log.id,
        tool_name=log.tool_name,
        source=log.source,
        status=log.status.value,
        arguments=json.loads(log.arguments_json) if log.arguments_json else {},
        result=json.loads(log.result_json) if log.result_json else None,
        error_message=log.error_message,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        is_undoable=log.is_undoable and log.undone_at is None,
        undone_at=log.undone_at,
        user_name=log.user.full_name if log.user else None,
        created_at=log.created_at,
    )


@router.get("", response_model=Page)
def list_actions(
    entity_type: str | None = None,
    entity_id: int | None = None,
    source: str | None = Query(None, description="Filter by 'api' or 'copilot'."),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    """ACEWIN's unified audit trail. Admins see every user's actions
    (both REST and Copilot) within their own organization; everyone
    else sees only their own -- the same ownership boundary enforced
    when the actions themselves were performed (see app/ai/permissions.py)."""
    query = scoped(db, AgentActionLog, org)
    if current_user.role != UserRole.admin:
        query = query.filter(AgentActionLog.user_id == current_user.id)
    if entity_type:
        query = query.filter(AgentActionLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AgentActionLog.entity_id == entity_id)
    if source:
        query = query.filter(AgentActionLog.source == source)

    total = query.count()
    logs = query.order_by(desc(AgentActionLog.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return Page(items=[_to_out(l) for l in logs], total=total, page=page, page_size=page_size)


@router.post("/{action_id}/undo", response_model=AgentActionLogOut)
def undo(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    log = scoped(db, AgentActionLog, org).filter(AgentActionLog.id == action_id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if current_user.role != UserRole.admin and log.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only undo your own actions")

    ctx = ToolContext(db=db, current_user=current_user, org=org)
    try:
        undo_action(ctx, log)
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.refresh(log)
    return _to_out(log)
