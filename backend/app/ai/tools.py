"""
Backend tool registry for the ACEWIN Copilot Action Agent.

Core rule from the project spec: the Copilot never generates SQL and
never fabricates CRM data. It can only act through the tools defined
here. Read tools query real data through the same SQLAlchemy models the
REST API uses. Write tools (create_task, update_task, create_deal,
update_deal_stage) apply the same model validation the REST API does --
the model can request a change, but it still goes through real
SQLAlchemy inserts/updates, and every result reports back the exact
record that changed.

Every write tool call additionally goes through `call_tool`'s dispatch
pipeline, which enforces, in order:

    1. Permission check   (app/ai/permissions.py -- role + ownership)
    2. Snapshot            (capture "before" state, for tools that support undo)
    3. Execute             (the tool's own handler -- unchanged business logic)
    4. Audit log            (AgentActionLog row: who, what, result, undoable?)

This mirrors the architecture the project spec asks for:

    LLM -> Tool Calling -> CRM Service Layer -> Database

The LLM never touches the database directly -- every tool call passes
through this file, and every one of them (success, denial, or error) is
recorded in AgentActionLog for compliance and for `POST
/api/agent-actions/{id}/undo` to reverse later.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.client import ToolDefinition
from app.ai.permissions import PermissionDeniedError, require_permission
from app.audit import record_action
from app.billing.entitlements import require_feature as enforce_feature
from app.models import (
    Activity,
    AgentActionLog,
    AgentActionStatus,
    Company,
    Contact,
    ContactStatus,
    Deal,
    Organization,
    PipelineStage,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.tenancy import scoped


class ToolError(RuntimeError):
    """Raised when a tool can't be executed (bad arguments, permission
    denied, nothing to undo, etc). The Copilot must surface this
    honestly rather than guessing."""


@dataclass
class ToolContext:
    """Everything a tool is allowed to touch. `org` is the tenant every
    query and mutation in this file MUST be scoped to -- the Copilot
    reasons over natural language, not ids, so nothing here can rely on
    a client-supplied id alone being trustworthy; every lookup below
    filters by `org.id` (via app.tenancy.scoped) the same way the REST
    routers do, which is what makes "AI cannot bypass tenant isolation"
    actually true rather than just documented."""

    db: Session
    current_user: User
    org: Organization


# Snapshot: capture whatever `undo` will need to restore prior state.
# Returns None when there is nothing to restore (e.g. before a *create*).
SnapshotFn = Callable[[ToolContext, dict], "dict | None"]
# Undo: given the original arguments, the tool's original result, and the
# snapshot captured beforehand, reverse the effect and return a small
# confirmation dict (shown to the user the same way a normal tool result is).
UndoFn = Callable[[ToolContext, dict, dict, "dict | None"], dict]


@dataclass
class RegisteredTool:
    definition: ToolDefinition
    handler: Callable[[ToolContext, dict], dict]
    writes: bool = False
    capture_snapshot: SnapshotFn | None = None
    undo_fn: UndoFn | None = None


_REGISTRY: dict[str, RegisteredTool] = {}

# tool_name -> (entity_type, key to read the id from -- checked in the
# tool's result first, falling back to its arguments). Used only to make
# the audit log filterable/readable ("show me everything the agent did to
# deal #42") -- it has no bearing on what the tool actually does.
_ENTITY_ID_KEYS: dict[str, tuple[str, str]] = {
    "create_task": ("task", "task_id"),
    "update_task": ("task", "task_id"),
    "create_deal": ("deal", "deal_id"),
    "update_deal_stage": ("deal", "deal_id"),
}


def register_tool(
    name: str,
    description: str,
    parameters: dict,
    *,
    writes: bool = False,
    capture_snapshot: SnapshotFn | None = None,
    undo_fn: UndoFn | None = None,
):
    """Decorator: registers a function as a Copilot-callable tool.
    `parameters` is a JSON-schema object describing accepted arguments,
    in the shape most LLM function-calling APIs expect.

    `writes`, `capture_snapshot` and `undo_fn` are only relevant for
    tools that mutate CRM data -- see app/ai/permissions.py for the
    permission side of the same tools (keyed by tool name, so nothing
    else needs to change here to add a new writable tool)."""

    def decorator(fn: Callable[[ToolContext, dict], dict]):
        _REGISTRY[name] = RegisteredTool(
            definition=ToolDefinition(name=name, description=description, parameters=parameters),
            handler=fn,
            writes=writes,
            capture_snapshot=capture_snapshot,
            undo_fn=undo_fn,
        )
        return fn

    return decorator


def list_tool_definitions() -> list[ToolDefinition]:
    return [tool.definition for tool in _REGISTRY.values()]


def _extract_entity(tool_name: str, args: dict, result: dict | None) -> tuple[str | None, int | None]:
    info = _ENTITY_ID_KEYS.get(tool_name)
    if not info:
        return None, None
    entity_type, key = info
    raw_id = (result or {}).get(key, args.get(key))
    try:
        return entity_type, int(raw_id) if raw_id is not None else None
    except (TypeError, ValueError):
        return entity_type, None


def _log_action(
    context: ToolContext,
    tool_name: str,
    arguments: dict,
    *,
    status: AgentActionStatus,
    result: dict | None = None,
    error_message: str | None = None,
    is_undoable: bool = False,
    previous_state: dict | None = None,
) -> AgentActionLog | None:
    """Thin wrapper around the shared audit writer (app/audit.py),
    fixing source="copilot" and deriving entity_type/entity_id from the
    tool's own naming convention -- kept here (rather than inlined at
    each call site) so call_tool/undo_action stay uncluttered."""
    entity_type, entity_id = _extract_entity(tool_name, arguments, result)
    return record_action(
        context.db,
        context.current_user,
        tool_name,
        source="copilot",
        status=status,
        arguments=arguments,
        result=result,
        error_message=error_message,
        is_undoable=is_undoable,
        previous_state=previous_state,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def call_tool(name: str, arguments: dict, context: ToolContext) -> dict:
    """The Action Agent's single entry point for executing a tool.
    Only tools registered with `writes=True` go through permission
    checks and the audit-log pipeline -- read-only tools (dashboard
    lookups, analytics, find_contact, ...) execute directly, exactly as
    before, since they can't be undone and don't need authorization
    beyond "is this an authenticated CRM user" (already enforced by the
    Copilot router itself)."""
    tool = _REGISTRY.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool '{name}'. Available tools: {', '.join(_REGISTRY)}")

    arguments = arguments or {}

    if not tool.writes:
        return tool.handler(context, arguments)

    # Plan gate for the whole Action Agent (not just the Copilot chat
    # itself, already gated by "ai.copilot" in routers/copilot.py) --
    # a Basic-plan org can ask the Copilot questions but cannot let it
    # write to the CRM. One check here covers every writes=True tool
    # (create_task, update_deal_stage, ...) without each needing its
    # own entitlement check.
    try:
        enforce_feature(context.db, context.org, "ai.actions")
    except HTTPException as exc:
        message = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
        _log_action(context, name, arguments, status=AgentActionStatus.denied, error_message=message)
        raise ToolError(message) from exc

    try:
        require_permission(context.db, context.current_user, name, arguments)
    except PermissionDeniedError as exc:
        _log_action(context, name, arguments, status=AgentActionStatus.denied, error_message=str(exc))
        raise ToolError(str(exc)) from exc

    previous_state = tool.capture_snapshot(context, arguments) if tool.capture_snapshot else None

    try:
        result = tool.handler(context, arguments)
    except ToolError as exc:
        _log_action(context, name, arguments, status=AgentActionStatus.error, error_message=str(exc))
        raise

    log = _log_action(
        context,
        name,
        arguments,
        status=AgentActionStatus.success,
        result=result,
        is_undoable=tool.undo_fn is not None,
        previous_state=previous_state,
    )
    if log is not None and tool.undo_fn is not None:
        result = {**result, "action_log_id": log.id}
    return result


def undo_action(context: ToolContext, log: AgentActionLog) -> dict:
    """Reverses a previously logged write action. This is the service-layer
    function -- callable from a REST router, from a future 'undo my last
    action' Copilot tool, or from anywhere else -- so it must enforce
    authorization itself rather than trusting the caller to have already
    checked it. Two independent checks:

    1. Ownership of the *log entry* -- only the user who performed the
       original action (or an admin) may undo it at all.
    2. The normal tool permission check, re-evaluated against whoever is
       undoing it now -- covers the case where a role's permissions
       changed between the original action and the undo request.
    """
    if log.undone_at is not None:
        raise ToolError("This action has already been undone.")
    if not log.is_undoable:
        raise ToolError("This action does not support undo.")
    if context.current_user.role != UserRole.admin and log.user_id != context.current_user.id:
        raise ToolError("You can only undo your own actions.")

    tool = _REGISTRY.get(log.tool_name)
    if tool is None or tool.undo_fn is None:
        raise ToolError("This action does not support undo.")

    arguments = json.loads(log.arguments_json) if log.arguments_json else {}
    try:
        require_permission(context.db, context.current_user, log.tool_name, arguments)
    except PermissionDeniedError as exc:
        raise ToolError(str(exc)) from exc

    result = json.loads(log.result_json) if log.result_json else {}
    previous_state = json.loads(log.previous_state_json) if log.previous_state_json else None

    undo_result = tool.undo_fn(context, arguments, result, previous_state)

    log.undone_at = datetime.now(timezone.utc)
    log.undone_by_id = context.current_user.id
    log.status = AgentActionStatus.undone
    context.db.commit()
    return undo_result


# ---------------------------------------------------------------------------
# Read-only tools, wired to real CRM Core data (Layer 1).
# ---------------------------------------------------------------------------


@register_tool(
    name="get_dashboard_summary",
    description="Get the current CRM dashboard summary: contact/company counts, open pipeline value, deals won this month, and task load.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_dashboard_summary(ctx: ToolContext, args: dict) -> dict:
    db = ctx.db
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    open_deals = (
        scoped(db, Deal, ctx.org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(PipelineStage.is_won.is_(False), PipelineStage.is_lost.is_(False))
        .all()
    )
    won_this_month = (
        scoped(db, Deal, ctx.org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(PipelineStage.is_won.is_(True), Deal.closed_at >= month_start)
        .all()
    )

    return {
        "total_contacts": scoped(db, Contact, ctx.org).count(),
        "total_companies": scoped(db, Company, ctx.org).count(),
        "open_deals_count": len(open_deals),
        "open_deals_value": float(sum(float(d.value) for d in open_deals)),
        "won_this_month_count": len(won_this_month),
        "won_this_month_value": float(sum(float(d.value) for d in won_this_month)),
        "tasks_due_today": scoped(db, Task, ctx.org)
        .filter(Task.status == TaskStatus.pending, Task.due_date >= today_start, Task.due_date <= today_end)
        .count(),
        "overdue_tasks": scoped(db, Task, ctx.org)
        .filter(Task.status == TaskStatus.pending, Task.due_date < today_start)
        .count(),
    }


@register_tool(
    name="list_upcoming_tasks",
    description="List pending tasks due within the next N days, optionally filtered by type (general/call).",
    parameters={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "description": "How many days ahead to look. Default 7.", "default": 7},
            "task_type": {"type": "string", "enum": ["general", "call"], "description": "Optional task type filter."},
        },
        "required": [],
    },
)
def list_upcoming_tasks(ctx: ToolContext, args: dict) -> dict:
    days = int(args.get("days", 7))
    if days < 1 or days > 90:
        raise ToolError("`days` must be between 1 and 90.")

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days)

    query = scoped(ctx.db, Task, ctx.org).filter(
        Task.status == TaskStatus.pending,
        Task.due_date.isnot(None),
        Task.due_date <= horizon,
    )
    if args.get("task_type"):
        query = query.filter(Task.task_type == args["task_type"])

    tasks = query.order_by(Task.due_date.asc()).limit(50).all()
    return {
        "count": len(tasks),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "priority": t.priority.value,
                "task_type": t.task_type.value,
                "contact": f"{t.contact.first_name} {t.contact.last_name}" if t.contact else None,
                "overdue": bool(t.due_date and t.due_date < now),
            }
            for t in tasks
        ],
    }


@register_tool(
    name="find_inactive_customers",
    description=(
        "Find contacts with status 'customer' who have had no logged activity "
        "(note/call/email/meeting) in the last N days -- useful for churn/risk follow-up."
    ),
    parameters={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "description": "Inactivity window in days. Default 30.", "default": 30}
        },
        "required": [],
    },
)
def find_inactive_customers(ctx: ToolContext, args: dict) -> dict:
    days = int(args.get("days", 30))
    if days < 1 or days > 365:
        raise ToolError("`days` must be between 1 and 365.")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = ctx.db

    last_activity_subq = (
        db.query(Activity.contact_id, func.max(Activity.created_at).label("last_activity_at"))
        .filter(Activity.organization_id == ctx.org.id)
        .group_by(Activity.contact_id)
        .subquery()
    )

    customers = (
        scoped(db, Contact, ctx.org)
        .add_columns(last_activity_subq.c.last_activity_at)
        .outerjoin(last_activity_subq, Contact.id == last_activity_subq.c.contact_id)
        .filter(Contact.status == ContactStatus.customer)
        .all()
    )

    inactive = [
        (contact, last_activity_at)
        for contact, last_activity_at in customers
        if last_activity_at is None or last_activity_at < cutoff
    ]

    return {
        "count": len(inactive),
        "window_days": days,
        "customers": [
            {
                "id": contact.id,
                "name": f"{contact.first_name} {contact.last_name}",
                "company": contact.company.name if contact.company else None,
                "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
            }
            for contact, last_activity_at in inactive
        ],
    }


# ---------------------------------------------------------------------------
# Write/action tools. These let the Copilot actually DO things ("schedule a
# call with Amin Rezaei tomorrow at 10am", "move that deal to Won", "add a
# follow-up task") instead of only reporting on data. Every write goes
# through the same SQLAlchemy models/validation the REST API uses -- the
# model can request a change, but the database rules (enums, foreign keys)
# still apply, and every result reports back the exact record that changed
# so nothing is silently invented.
# ---------------------------------------------------------------------------


def _find_contact(db, org: Organization, name: str) -> Contact:
    """Case-insensitive first+last name lookup, since the model gets a name
    from natural language, never a database id."""
    name = (name or "").strip()
    if not name:
        raise ToolError("A contact name is required.")

    pattern = f"%{name}%"
    matches = (
        scoped(db, Contact, org)
        .filter((Contact.first_name + " " + Contact.last_name).ilike(pattern))
        .limit(6)
        .all()
    )
    if not matches:
        raise ToolError(f"No contact found matching '{name}'. Ask the user to confirm the spelling, or search by another name.")
    if len(matches) > 1:
        options = ", ".join(f"{c.first_name} {c.last_name} (id={c.id})" for c in matches)
        raise ToolError(f"'{name}' matches more than one contact: {options}. Ask the user which one they mean, then retry with contact_id.")
    return matches[0]


def _find_stage(db, org: Organization, name: str) -> PipelineStage:
    name = (name or "").strip()
    pattern = f"%{name}%"
    matches = scoped(db, PipelineStage, org).filter(PipelineStage.name.ilike(pattern)).all()
    if not matches:
        stages = ", ".join(s.name for s in scoped(db, PipelineStage, org).order_by(PipelineStage.order).all())
        raise ToolError(f"No pipeline stage matches '{name}'. Available stages: {stages}.")
    if len(matches) > 1:
        options = ", ".join(s.name for s in matches)
        raise ToolError(f"'{name}' matches more than one stage: {options}. Ask the user to be more specific.")
    return matches[0]


def _parse_datetime(value: str) -> datetime:
    if not value:
        raise ToolError("A due date/time is required, as an ISO 8601 string (e.g. 2026-08-02T10:00:00).")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolError(f"Could not parse '{value}' as an ISO 8601 datetime. Use e.g. 2026-08-02T10:00:00.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _optional_parsed(value: str | None) -> datetime | None:
    return _parse_datetime(value) if value else None


# ---------------------------------------------------------------------------
# Snapshot / undo pairs for each write tool. Kept next to each other and
# next to the tool they belong to, since they must stay in lockstep: the
# snapshot's shape is exactly what undo consumes.
# ---------------------------------------------------------------------------


def _undo_delete_task(ctx: ToolContext, args: dict, result: dict, previous_state: dict | None) -> dict:
    """Undo for create_task: the task didn't exist before, so undo just
    removes it."""
    task_id = result.get("task_id")
    task = scoped(ctx.db, Task, ctx.org).filter(Task.id == int(task_id)).first() if task_id is not None else None
    if task is None:
        raise ToolError(f"Task #{task_id} no longer exists -- nothing to undo.")
    ctx.db.delete(task)
    ctx.db.commit()
    return {"undone": True, "deleted_task_id": task_id}


def _snapshot_task(ctx: ToolContext, args: dict) -> dict | None:
    """Captures a task's mutable fields before update_task changes them."""
    task_id = args.get("task_id")
    task = scoped(ctx.db, Task, ctx.org).filter(Task.id == int(task_id)).first() if task_id is not None else None
    if task is None:
        return None
    return {
        "title": task.title,
        "due_date": _optional_iso(task.due_date),
        "priority": task.priority.value,
        "status": task.status.value,
        "completed_at": _optional_iso(task.completed_at),
    }


def _undo_restore_task(ctx: ToolContext, args: dict, result: dict, previous_state: dict | None) -> dict:
    if not previous_state:
        raise ToolError("No prior state was recorded for this task -- cannot undo.")
    task_id = result.get("task_id", args.get("task_id"))
    task = scoped(ctx.db, Task, ctx.org).filter(Task.id == int(task_id)).first() if task_id is not None else None
    if task is None:
        raise ToolError(f"Task #{task_id} no longer exists -- cannot undo.")
    task.title = previous_state["title"]
    task.due_date = _optional_parsed(previous_state.get("due_date"))
    task.priority = TaskPriority(previous_state["priority"])
    task.status = TaskStatus(previous_state["status"])
    task.completed_at = _optional_parsed(previous_state.get("completed_at"))
    ctx.db.commit()
    ctx.db.refresh(task)
    return {"undone": True, "task_id": task.id, "restored_status": task.status.value, "restored_due_date": _optional_iso(task.due_date)}


def _undo_delete_deal(ctx: ToolContext, args: dict, result: dict, previous_state: dict | None) -> dict:
    """Undo for create_deal: the deal didn't exist before, so undo just
    removes it."""
    deal_id = result.get("deal_id")
    deal = scoped(ctx.db, Deal, ctx.org).filter(Deal.id == int(deal_id)).first() if deal_id is not None else None
    if deal is None:
        raise ToolError(f"Deal #{deal_id} no longer exists -- nothing to undo.")
    ctx.db.delete(deal)
    ctx.db.commit()
    return {"undone": True, "deleted_deal_id": deal_id}


def _snapshot_deal_stage(ctx: ToolContext, args: dict) -> dict | None:
    """Captures a deal's stage/closed_at before update_deal_stage changes them."""
    deal_id = args.get("deal_id")
    deal = scoped(ctx.db, Deal, ctx.org).filter(Deal.id == int(deal_id)).first() if deal_id is not None else None
    if deal is None:
        return None
    return {"stage_id": deal.stage_id, "closed_at": _optional_iso(deal.closed_at)}


def _undo_restore_deal_stage(ctx: ToolContext, args: dict, result: dict, previous_state: dict | None) -> dict:
    if not previous_state:
        raise ToolError("No prior state was recorded for this deal -- cannot undo.")
    deal_id = result.get("deal_id", args.get("deal_id"))
    deal = scoped(ctx.db, Deal, ctx.org).filter(Deal.id == int(deal_id)).first() if deal_id is not None else None
    if deal is None:
        raise ToolError(f"Deal #{deal_id} no longer exists -- cannot undo.")
    stage = scoped(ctx.db, PipelineStage, ctx.org).filter(PipelineStage.id == previous_state["stage_id"]).first()
    if stage is None:
        raise ToolError("The deal's previous pipeline stage no longer exists -- cannot undo.")
    deal.stage = stage
    deal.closed_at = _optional_parsed(previous_state.get("closed_at"))
    ctx.db.commit()
    ctx.db.refresh(deal)
    return {"undone": True, "deal_id": deal.id, "restored_stage": stage.name}


@register_tool(
    name="find_contact",
    description="Look up a CRM contact by name (partial match ok) to get their id before creating a task or deal for them.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Full or partial contact name, e.g. 'Amin Rezaei'."}},
        "required": ["name"],
    },
)
def find_contact_tool(ctx: ToolContext, args: dict) -> dict:
    contact = _find_contact(ctx.db, ctx.org, args.get("name", ""))
    return {
        "id": contact.id,
        "name": f"{contact.first_name} {contact.last_name}",
        "status": contact.status.value,
        "company": contact.company.name if contact.company else None,
    }


@register_tool(
    name="create_task",
    description=(
        "Create a new CRM task, call reminder, or appointment/meeting. Use task_type='call' for phone "
        "call reminders or meetings/appointments; use 'general' for any other to-do. Provide either "
        "contact_id (if already known from a prior tool call) or contact_name (to look it up)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short task title, e.g. 'Call with Amin Rezaei'."},
            "due_date": {"type": "string", "description": "ISO 8601 datetime, e.g. 2026-08-02T10:00:00. Resolve relative phrases like 'tomorrow' using the current date given in your instructions."},
            "task_type": {"type": "string", "enum": ["general", "call"], "default": "general"},
            "priority": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
            "contact_name": {"type": "string", "description": "Contact's name, if this task relates to a specific person."},
            "contact_id": {"type": "integer", "description": "Contact id, if already known."},
            "reminder_minutes_before": {"type": "integer", "description": "For call/appointment tasks: minutes before due_date to remind. Default 15."},
        },
        "required": ["title", "due_date"],
    },
    writes=True,
    undo_fn=_undo_delete_task,
)
def create_task_tool(ctx: ToolContext, args: dict) -> dict:
    db = ctx.db
    contact = None
    if args.get("contact_id"):
        contact = scoped(db, Contact, ctx.org).filter(Contact.id == int(args["contact_id"])).first()
        if contact is None:
            raise ToolError(f"No contact with id {args['contact_id']}.")
    elif args.get("contact_name"):
        contact = _find_contact(db, ctx.org, args["contact_name"])

    task_type_value = args.get("task_type", "general")
    if task_type_value not in (TaskType.general.value, TaskType.call.value):
        raise ToolError("task_type must be 'general' or 'call'.")

    priority_value = args.get("priority", "medium")
    if priority_value not in (p.value for p in TaskPriority):
        raise ToolError("priority must be 'low', 'medium' or 'high'.")

    task = Task(
        organization_id=ctx.org.id,
        title=args["title"],
        due_date=_parse_datetime(args["due_date"]),
        task_type=TaskType(task_type_value),
        priority=TaskPriority(priority_value),
        status=TaskStatus.pending,
        reminder_minutes_before=int(args["reminder_minutes_before"]) if args.get("reminder_minutes_before") is not None else (15 if task_type_value == "call" else None),
        contact=contact,
        assigned_to=ctx.current_user,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "created": True,
        "task_id": task.id,
        "title": task.title,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "task_type": task.task_type.value,
        "contact": f"{contact.first_name} {contact.last_name}" if contact else None,
    }


@register_tool(
    name="update_task",
    description="Update an existing task: reschedule (due_date), change priority/status/title, or mark it done (status='completed').",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "integer"},
            "title": {"type": "string"},
            "due_date": {"type": "string", "description": "New ISO 8601 datetime."},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            "status": {"type": "string", "enum": ["pending", "completed"]},
        },
        "required": ["task_id"],
    },
    writes=True,
    capture_snapshot=_snapshot_task,
    undo_fn=_undo_restore_task,
)
def update_task_tool(ctx: ToolContext, args: dict) -> dict:
    db = ctx.db
    task = scoped(db, Task, ctx.org).filter(Task.id == int(args.get("task_id", 0))).first()
    if task is None:
        raise ToolError(f"No task with id {args.get('task_id')}.")

    if args.get("title"):
        task.title = args["title"]
    if args.get("due_date"):
        task.due_date = _parse_datetime(args["due_date"])
    if args.get("priority"):
        if args["priority"] not in (p.value for p in TaskPriority):
            raise ToolError("priority must be 'low', 'medium' or 'high'.")
        task.priority = TaskPriority(args["priority"])
    if args.get("status"):
        if args["status"] not in (s.value for s in TaskStatus):
            raise ToolError("status must be 'pending' or 'completed'.")
        task.status = TaskStatus(args["status"])
        task.completed_at = datetime.now(timezone.utc) if task.status == TaskStatus.completed else None

    db.commit()
    db.refresh(task)
    return {
        "updated": True,
        "task_id": task.id,
        "title": task.title,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "priority": task.priority.value,
        "status": task.status.value,
    }


@register_tool(
    name="create_deal",
    description="Create a new deal in the pipeline. Provide either stage_name (e.g. 'Proposal Sent') or it defaults to the first stage.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "value": {"type": "number", "description": "Deal value in the CRM's currency."},
            "stage_name": {"type": "string", "description": "Pipeline stage name, partial match ok. Defaults to the first stage if omitted."},
            "contact_name": {"type": "string"},
            "contact_id": {"type": "integer"},
            "probability": {"type": "integer", "description": "0-100. Optional."},
        },
        "required": ["title", "value"],
    },
    writes=True,
    undo_fn=_undo_delete_deal,
)
def create_deal_tool(ctx: ToolContext, args: dict) -> dict:
    db = ctx.db
    if args.get("stage_name"):
        stage = _find_stage(db, ctx.org, args["stage_name"])
    else:
        stage = scoped(db, PipelineStage, ctx.org).order_by(PipelineStage.order).first()
        if stage is None:
            raise ToolError("No pipeline stages exist yet -- create one in Settings first.")

    contact = None
    if args.get("contact_id"):
        contact = scoped(db, Contact, ctx.org).filter(Contact.id == int(args["contact_id"])).first()
    elif args.get("contact_name"):
        contact = _find_contact(db, ctx.org, args["contact_name"])

    deal = Deal(
        organization_id=ctx.org.id,
        title=args["title"],
        value=float(args["value"]),
        probability=int(args.get("probability", 50)),
        stage=stage,
        contact=contact,
        company=contact.company if contact else None,
        assigned_to=ctx.current_user,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)

    return {
        "created": True,
        "deal_id": deal.id,
        "title": deal.title,
        "value": float(deal.value),
        "stage": stage.name,
        "contact": f"{contact.first_name} {contact.last_name}" if contact else None,
    }


@register_tool(
    name="update_deal_stage",
    description="Move a deal to a different pipeline stage (e.g. mark it Won/Lost, or advance it to the next stage).",
    parameters={
        "type": "object",
        "properties": {
            "deal_id": {"type": "integer"},
            "stage_name": {"type": "string", "description": "Target stage name, partial match ok, e.g. 'Won' or 'Negotiation'."},
        },
        "required": ["deal_id", "stage_name"],
    },
    writes=True,
    capture_snapshot=_snapshot_deal_stage,
    undo_fn=_undo_restore_deal_stage,
)
def update_deal_stage_tool(ctx: ToolContext, args: dict) -> dict:
    db = ctx.db
    deal = scoped(db, Deal, ctx.org).filter(Deal.id == int(args.get("deal_id", 0))).first()
    if deal is None:
        raise ToolError(f"No deal with id {args.get('deal_id')}.")

    stage = _find_stage(db, ctx.org, args.get("stage_name", ""))
    deal.stage = stage
    if stage.is_won or stage.is_lost:
        deal.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(deal)

    return {"updated": True, "deal_id": deal.id, "title": deal.title, "new_stage": stage.name}


# ---------------------------------------------------------------------------
# Analytics Engine tools (Layer 3). These call the same functions the
# /api/analytics/* REST endpoints use, so the Copilot's numbers always match
# the dashboards -- there is only one implementation of each AI module.
# ---------------------------------------------------------------------------


def _analytics_tool(name: str, description: str, parameters: dict, fn: Callable[[dict], dict]):
    @register_tool(name=name, description=description, parameters=parameters)
    def _wrapped(ctx: ToolContext, args: dict) -> dict:
        from app.analytics.loader import DatasetNotFoundError

        try:
            return fn(args)
        except DatasetNotFoundError as exc:
            raise ToolError(str(exc)) from exc

    return _wrapped


def _lazy_import_models():
    from app.analytics import models

    return models


_analytics_tool(
    "run_customer_segmentation",
    "Segment customers into groups (Champions, Loyal, At Risk, New/Low Value) using RFM clustering on real order history.",
    {"type": "object", "properties": {}, "required": []},
    lambda args: _lazy_import_models().customer_segmentation(),
)

_analytics_tool(
    "run_churn_prediction",
    "Predict which customers are at risk of churning, with an overall churn rate and a ranked at-risk list.",
    {
        "type": "object",
        "properties": {"window_days": {"type": "integer", "description": "Days of inactivity considered churn. Default 180."}},
        "required": [],
    },
    lambda args: _lazy_import_models().churn_prediction(churn_window_days=int(args.get("window_days", 180))),
)

_analytics_tool(
    "run_clv_prediction",
    "Predict customer lifetime value (CLV) and return the top customers by predicted value.",
    {"type": "object", "properties": {"top_n": {"type": "integer", "description": "How many customers to return. Default 20."}}, "required": []},
    lambda args: _lazy_import_models().clv_prediction(top_n=int(args.get("top_n", 20))),
)

_analytics_tool(
    "run_lead_scoring",
    "Score customers 0-100 on likelihood of becoming a repeat buyer.",
    {"type": "object", "properties": {"top_n": {"type": "integer", "description": "How many leads to return. Default 20."}}, "required": []},
    lambda args: _lazy_import_models().lead_scoring(top_n=int(args.get("top_n", 20))),
)

_analytics_tool(
    "run_revenue_forecast",
    "Forecast revenue for the next N months from historical monthly sales.",
    {"type": "object", "properties": {"months_ahead": {"type": "integer", "description": "Months to forecast. Default 3."}}, "required": []},
    lambda args: _lazy_import_models().revenue_forecast(months_ahead=int(args.get("months_ahead", 3))),
)

_analytics_tool(
    "run_sales_trend_analysis",
    "Analyse month-over-month sales trends: revenue, order counts, growth rate, best/worst months.",
    {"type": "object", "properties": {}, "required": []},
    lambda args: _lazy_import_models().sales_trend_analysis(),
)

_analytics_tool(
    "run_customer_behaviour_analysis",
    "Analyse customer behaviour: repeat purchase rate, basket size, payment method mix, top categories.",
    {"type": "object", "properties": {}, "required": []},
    lambda args: _lazy_import_models().customer_behaviour_analysis(),
)

_analytics_tool(
    "run_risk_detection",
    "Detect at-risk customers (low satisfaction, late deliveries, going cold), flagging high-value accounts especially.",
    {"type": "object", "properties": {"top_n": {"type": "integer", "description": "How many flagged customers to return. Default 20."}}, "required": []},
    lambda args: _lazy_import_models().risk_detection(top_n=int(args.get("top_n", 20))),
)

_analytics_tool(
    "run_next_best_action",
    "Recommend the next best action per customer based on their segment.",
    {"type": "object", "properties": {"top_n": {"type": "integer", "description": "How many customers to return. Default 20."}}, "required": []},
    lambda args: _lazy_import_models().next_best_action(top_n=int(args.get("top_n", 20))),
)

_analytics_tool(
    "run_business_performance_evaluation",
    "Return a KPI scorecard: revenue trend, on-time delivery rate, review score, repeat purchase rate.",
    {"type": "object", "properties": {}, "required": []},
    lambda args: _lazy_import_models().business_performance_evaluation(),
)

_analytics_tool(
    "run_executive_insights",
    "Get a synthesized executive summary combining churn, sales trend, performance and risk data.",
    {"type": "object", "properties": {}, "required": []},
    lambda args: _lazy_import_models().executive_insights(),
)
