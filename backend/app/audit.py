"""
Unified audit trail for every mutating action in ACEWIN, whether it was
performed by a human through the REST API or by the Copilot Action
Agent through tool-calling.

Both paths write to the same `AgentActionLog` table via `record_action`
below, distinguished only by `source` ("api" | "copilot"). That means
one place -- and one query -- answers "show me everything that
happened to deal #42" regardless of whether it happened through the
UI or the AI:

    GET /api/agent-actions?entity_type=deal&entity_id=42

Kept as its own module (rather than living inside app/ai/tools.py) so
REST routers can import it without importing anything AI-related.
"""
import json
import logging

from sqlalchemy.orm import Session

from app.email import send_admin_notification
from app.models import AgentActionLog, AgentActionStatus, User

logger = logging.getLogger("acewin.audit")


def record_action(
    db: Session,
    user: User,
    action_name: str,
    *,
    source: str,
    status: AgentActionStatus,
    arguments: dict | None = None,
    result: dict | None = None,
    error_message: str | None = None,
    is_undoable: bool = False,
    previous_state: dict | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    organization_id: int | None = None,
) -> AgentActionLog | None:
    """Writes one audit row and returns it (or None on failure).

    Never raises: a logging failure must never take down -- or appear
    to block -- the CRM action it's trying to record. Uses its own
    commit, independent of whatever transaction the caller's own
    mutation used, so the two can't interfere with each other.

    `organization_id` should always be passed by callers that have a
    resolved tenant (i.e. every REST router). It falls back to
    `user.organization_id` when omitted so existing call sites (and the
    Copilot dispatcher, which always acts as a specific user) keep
    writing correctly-scoped audit rows without every call site needing
    an update.
    """
    try:
        log = AgentActionLog(
            organization_id=organization_id if organization_id is not None else user.organization_id,
            user_id=user.id,
            tool_name=action_name,
            source=source,
            status=status,
            arguments_json=json.dumps(arguments or {}, default=str),
            result_json=json.dumps(result, default=str) if result is not None else None,
            error_message=error_message,
            entity_type=entity_type,
            entity_id=entity_id,
            is_undoable=is_undoable,
            previous_state_json=json.dumps(previous_state, default=str) if previous_state is not None else None,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        if status == AgentActionStatus.success:
            _notify_admin_of_action(log, user, action_name, source, arguments, entity_type, entity_id)

        return log
    except Exception:
        db.rollback()
        return None


def _notify_admin_of_action(
    log: AgentActionLog,
    user: User,
    action_name: str,
    source: str,
    arguments: dict | None,
    entity_type: str | None,
    entity_id: int | None,
) -> None:
    """Mirrors every successful write to the Platform Admin's inbox, on
    top of it already being queryable in the Platform Admin panel's
    "Requests" tab (GET /api/platform-admin/actions). Best-effort and
    isolated from the audit write itself: a notification failure (or an
    unconfigured SMTP_HOST -- see app/email.py) must never make it look
    like the underlying CRM action failed, so any exception here is
    swallowed rather than propagated.
    """
    try:
        org_name = user.organization.name if user.organization else f"org #{user.organization_id}"
        who = f"{user.full_name} <{user.email}>"
        where = f"{entity_type} #{entity_id}" if entity_type else "-"
        subject = f"[ACEWIN] {action_name} — {org_name}"
        body = (
            f"Action: {action_name}\n"
            f"Source: {source}\n"
            f"Organization: {org_name}\n"
            f"User: {who}\n"
            f"Entity: {where}\n"
            f"Arguments: {json.dumps(arguments or {}, default=str, ensure_ascii=False)}\n"
            f"Log ID: {log.id}\n"
        )
        send_admin_notification(subject, body)
    except Exception:
        logger.exception("Failed to prepare admin notification for action %s", action_name)
