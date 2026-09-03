from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_permission, get_current_org, get_current_user
from app.gamification import engine as gamification_engine
from app.models import AgentActionStatus, Contact, Deal, Organization, PointSourceType, Task, TaskStatus, TaskType, User
from app.schemas import Page, TaskCreate, TaskOut, TaskUpdate
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Anti-abuse (R&D doc section 6): a task created and immediately marked
# complete in the same breath is almost certainly bookkeeping, not real
# work -- require it to have existed for at least this long before it
# can earn points.
_MIN_TASK_AGE_FOR_POINTS_SECONDS = 60


def _sync_gamification_on_complete(db: Session, org: Organization, task: Task) -> None:
    if not task.assigned_to_id or not task.completed_at:
        return
    age_seconds = (task.completed_at - task.created_at).total_seconds()
    if age_seconds < _MIN_TASK_AGE_FOR_POINTS_SECONDS:
        return
    # "Due date respected" per the R&D doc's point-source table -- a task
    # with no due date at all isn't penalized (most tasks in this CRM are
    # optional-due-date), only one that was actually let slip.
    if task.due_date and task.completed_at > task.due_date:
        return
    owner = db.query(User).filter(User.id == task.assigned_to_id).first()
    if owner is None:
        return
    gamification_engine.award_points(
        db, org, owner, PointSourceType.task_completed, f"task:{task.id}", 2,
        reason_en=f'Completed task "{task.title}"',
        reason_fa=f"تکمیل تسک «{task.title}»",
        occurred_at=task.completed_at,
    )


def _sync_gamification_on_reopen_or_delete(db: Session, org: Organization, task_id: int, task_title: str) -> None:
    gamification_engine.revoke_points_for_source(
        db, org, PointSourceType.task_completed, f"task:{task_id}",
        reason_en=f'Task "{task_title}" is no longer completed',
        reason_fa=f"تسک «{task_title}» دیگر تکمیل‌شده نیست",
    )


def _base_query(db: Session, org: Organization):
    return scoped(db, Task, org).options(joinedload(Task.assigned_to), joinedload(Task.contact), joinedload(Task.deal))


def _validate_refs(
    db: Session, org: Organization, assigned_to_id: int | None, contact_id: int | None, deal_id: int | None
) -> None:
    """assigned_to_id, contact_id and deal_id are client-supplied FKs into
    other tenant-owned tables. Unvalidated, a caller could point a task
    at another organization's user/contact/deal id and have its name
    leak back out through TaskOut's assigned_to/contact_name/deal_title
    fields -- the same cross-tenant leak activities.py already guards
    against for its own contact_id/deal_id."""
    if assigned_to_id is not None:
        get_or_404(db, User, assigned_to_id, org, detail="Invalid assigned_to_id")
    if contact_id is not None:
        get_or_404(db, Contact, contact_id, org, detail="Invalid contact")
    if deal_id is not None:
        get_or_404(db, Deal, deal_id, org, detail="Invalid deal")


def _to_out(task: Task) -> TaskOut:
    item = TaskOut.model_validate(task)
    item.contact_name = f"{task.contact.first_name} {task.contact.last_name}".strip() if task.contact else None
    item.contact_phone = task.contact.phone if task.contact else None
    item.deal_title = task.deal.title if task.deal else None
    return item


@router.get("", response_model=Page)
def list_tasks(
    status: TaskStatus | None = None,
    task_type: TaskType | None = None,
    assigned_to_id: int | None = None,
    contact_id: int | None = None,
    deal_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    query = _base_query(db, org)
    if status:
        query = query.filter(Task.status == status)
    if task_type:
        query = query.filter(Task.task_type == task_type)
    if assigned_to_id:
        query = query.filter(Task.assigned_to_id == assigned_to_id)
    if contact_id:
        query = query.filter(Task.contact_id == contact_id)
    if deal_id:
        query = query.filter(Task.deal_id == deal_id)

    total = query.count()
    tasks = query.order_by(Task.due_date.is_(None), Task.due_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return Page(items=[_to_out(t) for t in tasks], total=total, page=page, page_size=page_size)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_permission(db, current_user, "tasks:create")
    _validate_refs(db, org, payload.assigned_to_id, payload.contact_id, payload.deal_id)
    task = Task(**payload.model_dump(), organization_id=org.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    record_action(
        db, current_user, "tasks:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="task", entity_id=task.id, organization_id=org.id,
    )
    return _to_out(task)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    task = _base_query(db, org).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_out(task)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    task = get_or_404(db, Task, task_id, org, detail="Task not found")
    enforce_permission(db, current_user, "tasks:update", {"task_id": task_id})

    data = payload.model_dump(exclude_unset=True)
    _validate_refs(db, org, data.get("assigned_to_id"), data.get("contact_id"), data.get("deal_id"))
    became_completed = False
    became_reopened = False
    if data.get("status") == TaskStatus.completed and task.status != TaskStatus.completed:
        task.completed_at = datetime.now(timezone.utc)
        became_completed = True
    elif data.get("status") == TaskStatus.pending and task.status == TaskStatus.completed:
        task.completed_at = None
        became_reopened = True

    for field, value in data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    record_action(
        db, current_user, "tasks:update", source="api", status=AgentActionStatus.success,
        arguments={"task_id": task_id, **data}, entity_type="task", entity_id=task.id, organization_id=org.id,
    )
    if became_completed:
        _sync_gamification_on_complete(db, org, task)
    elif became_reopened:
        _sync_gamification_on_reopen_or_delete(db, org, task.id, task.title)
    return _to_out(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    task = get_or_404(db, Task, task_id, org, detail="Task not found")
    enforce_permission(db, current_user, "tasks:delete", {"task_id": task_id})
    was_completed = task.status == TaskStatus.completed
    task_title = task.title
    db.delete(task)
    db.commit()
    record_action(
        db, current_user, "tasks:delete", source="api", status=AgentActionStatus.success,
        arguments={"task_id": task_id}, entity_type="task", entity_id=task_id, organization_id=org.id,
    )
    if was_completed:
        _sync_gamification_on_reopen_or_delete(db, org, task_id, task_title)
    return None
