"""
Enterprise RBAC for ACEWIN -- the single source of truth for "who can do
what", shared by both access paths into the CRM:

    REST API  ----\
                   >---> require_permission_for() / require_permission() ---> _check_role() + _check_ownership()
    Copilot Agent -/

Every mutating action in the system -- whether a human clicked "Delete"
in the UI or the Copilot Action Agent called a tool -- is guarded by
exactly two checks, defined once, here:

1. Role permission -- does this user's role allow this *kind* of
   action at all? (`ROLE_PERMISSIONS`)
2. Ownership -- for actions on an *existing* record (as opposed to
   creating a new one), does this user own/manage that specific
   record, or are they an admin? (`_OWNERSHIP_CHECKS`)

Two entry points share that logic:

    require_permission_for(db, user, permission, arguments)
        Used directly by REST routers, which already know their own
        permission key (e.g. "contacts:update").

    require_permission(db, user, tool_name, arguments)
        Used by the Copilot tool dispatcher (app/ai/tools.py), which
        knows a *tool name* (e.g. "update_task") rather than a
        permission key -- TOOL_PERMISSIONS maps one to the other so a
        tool and its REST equivalent enforce identical rules.

Extending this for a new resource or role is additive: add a
permission key to ROLE_PERMISSIONS, and if the action mutates an
*existing* record, add an ownership check function to
_OWNERSHIP_CHECKS.
"""
import json
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.models import Contact, Deal, KeyResult, Objective, Task, User, UserRole


class PermissionDeniedError(RuntimeError):
    """Raised when the current user isn't allowed to perform an action.
    Kept distinct from ToolError (app/ai/tools.py) and from FastAPI's
    HTTPException so callers can decide how to surface it (a 403 from a
    REST router, a "denied" audit-log entry from the Copilot)."""


# ---------------------------------------------------------------------------
# 1. Role -> permitted permission keys. "*" means unrestricted (every
#    permission key, including ones added later).
#
#    Naming convention: "<resource>:<action>", e.g. "deals:update".
#    REST routers use these keys directly; Copilot tools map to them via
#    TOOL_PERMISSIONS below.
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[UserRole, set[str] | str] = {
    UserRole.admin: "*",
    UserRole.member: {
        # Members can create and edit their own work. Ownership (below)
        # restricts *update* to records assigned to them; *create*
        # always assigns the new record to the creator, so there's
        # nothing to own yet.
        "tasks:create", "tasks:update", "tasks:delete",
        "deals:create", "deals:update",
        "contacts:create", "contacts:update",
        "companies:create", "companies:update",
        "tags:create",
        # OKRs: setting company/department objectives is a leadership
        # function, so "objectives:create"/"objectives:delete" are
        # admin-only by omission. Once an objective exists, its owner
        # (assigned by whoever created it) can update it and manage its
        # Key Results and progress -- that's the day-to-day OKR work.
        "objectives:update",
        "key_results:create", "key_results:update", "key_results:delete", "key_results:progress",
        # Deliberately NOT granted to members -- destructive operations
        # on shared/organization-wide data (deleting a deal loses
        # pipeline history; deleting a company/contact/tag can affect
        # every other user's records) require an admin.
        # "deals:delete", "contacts:delete", "companies:delete", "tags:delete"
        #
        # "kpis:update_target" is also admin-only by omission -- a KPI
        # target is an org-wide goal (see app/kpi/engine.py), not a
        # personal setting, so it isn't granted to members here either.
    },
}

# ---------------------------------------------------------------------------
# 1b. Every permission key a role can ever hold, grouped by resource for
#     display purposes (e.g. the "restrict this account" admin UI). This
#     is deliberately the union of every key referenced anywhere above --
#     adding a new permission to ROLE_PERMISSIONS should also add it here
#     so it's restrictable/visible, but forgetting to isn't a security
#     hole (an unlisted key still enforces correctly, it's just invisible
#     to the picker).
# ---------------------------------------------------------------------------

PERMISSION_CATALOG: dict[str, list[str]] = {
    "contacts": ["contacts:create", "contacts:update", "contacts:delete"],
    "companies": ["companies:create", "companies:update", "companies:delete"],
    "deals": ["deals:create", "deals:update", "deals:delete"],
    "tasks": ["tasks:create", "tasks:update", "tasks:delete"],
    "tags": ["tags:create", "tags:delete"],
    "objectives": ["objectives:create", "objectives:update", "objectives:delete"],
    "key_results": ["key_results:create", "key_results:update", "key_results:delete", "key_results:progress"],
    "kpis": ["kpis:update_target"],
}

ALL_PERMISSION_KEYS: set[str] = {key for group in PERMISSION_CATALOG.values() for key in group}

# Copilot tool name -> permission key. Only write tools appear here;
# read-only tools (dashboard, analytics, find_contact, ...) are never
# permission-checked -- see app/ai/tools.py's call_tool.
TOOL_PERMISSIONS: dict[str, str] = {
    "create_task": "tasks:create",
    "update_task": "tasks:update",
    "create_deal": "deals:create",
    "update_deal_stage": "deals:update",
}


def _role_allows(role: UserRole, permission: str) -> bool:
    allowed = ROLE_PERMISSIONS.get(role, set())
    return allowed == "*" or permission in allowed


def get_restricted_permissions(user: User) -> set[str]:
    """Parses User.restricted_permissions (a JSON list) back into a set.
    Tolerant of empty/corrupt values -- a bad value should never make a
    permission check crash, and defaults to "nothing restricted" rather
    than "everything restricted" so it fails open to the role's normal
    grant, not closed.
    """
    try:
        raw = json.loads(user.restricted_permissions_json or "[]")
    except (TypeError, ValueError):
        return set()
    if not isinstance(raw, list):
        return set()
    return {key for key in raw if isinstance(key, str)}


# ---------------------------------------------------------------------------
# 2. Ownership checks for actions on an *existing* record. Admins bypass
#    ownership entirely; everyone else may only act on records assigned
#    to them (or unassigned records, which anyone may claim/edit).
# ---------------------------------------------------------------------------


@dataclass
class OwnershipContext:
    db: Session
    user: User
    arguments: dict


def _owns_task(ctx: OwnershipContext) -> None:
    task_id = ctx.arguments.get("task_id")
    task = ctx.db.get(Task, int(task_id)) if task_id is not None else None
    if task is None:
        return  # let the caller's own "not found" handling take over
    if task.assigned_to_id is not None and task.assigned_to_id != ctx.user.id:
        raise PermissionDeniedError(
            f"Task #{task_id} is assigned to someone else -- you can only act on tasks assigned to you."
        )


def _owns_deal(ctx: OwnershipContext) -> None:
    deal_id = ctx.arguments.get("deal_id")
    deal = ctx.db.get(Deal, int(deal_id)) if deal_id is not None else None
    if deal is None:
        return
    if deal.assigned_to_id is not None and deal.assigned_to_id != ctx.user.id:
        raise PermissionDeniedError(
            f"Deal #{deal_id} is assigned to someone else -- you can only act on deals assigned to you."
        )


def _owns_contact(ctx: OwnershipContext) -> None:
    contact_id = ctx.arguments.get("contact_id")
    contact = ctx.db.get(Contact, int(contact_id)) if contact_id is not None else None
    if contact is None:
        return
    if contact.assigned_to_id is not None and contact.assigned_to_id != ctx.user.id:
        raise PermissionDeniedError(
            f"Contact #{contact_id} is assigned to someone else -- you can only act on contacts assigned to you."
        )


def _owns_objective(ctx: OwnershipContext) -> None:
    """Used both for updating an Objective directly (arguments has
    "objective_id") and for creating a Key Result under one (same key)
    -- in both cases, the question is the same: does this user own the
    objective in question?"""
    objective_id = ctx.arguments.get("objective_id")
    objective = ctx.db.get(Objective, int(objective_id)) if objective_id is not None else None
    if objective is None:
        return
    if objective.owner_id is not None and objective.owner_id != ctx.user.id:
        raise PermissionDeniedError(
            f"Objective #{objective_id} is owned by someone else -- you can only manage objectives you own."
        )


def _owns_key_result(ctx: OwnershipContext) -> None:
    """A Key Result can be worked on by whoever owns it directly, OR by
    whoever owns its parent Objective (the person accountable for the
    objective can always manage its Key Results, even ones they
    delegated to someone else)."""
    kr_id = ctx.arguments.get("key_result_id")
    kr = ctx.db.get(KeyResult, int(kr_id)) if kr_id is not None else None
    if kr is None:
        return
    owners = {o for o in (kr.owner_id, kr.objective.owner_id if kr.objective else None) if o is not None}
    if owners and ctx.user.id not in owners:
        raise PermissionDeniedError(
            f"Key Result #{kr_id} is not assigned to you or your objective -- "
            "you can only act on Key Results you're responsible for."
        )


# permission key -> ownership check. Only permissions that mutate an
# *existing, ownable* record appear here. Permissions with no entry
# either create new records (nothing to own yet) or are admin-only
# (role check alone already settles it).
_OWNERSHIP_CHECKS: dict[str, Callable[[OwnershipContext], None]] = {
    "tasks:update": _owns_task,
    "tasks:delete": _owns_task,
    "deals:update": _owns_deal,
    "contacts:update": _owns_contact,
    "objectives:update": _owns_objective,
    "key_results:create": _owns_objective,  # arguments carries objective_id here, same check
    "key_results:update": _owns_key_result,
    "key_results:delete": _owns_key_result,
    "key_results:progress": _owns_key_result,
}


def _check_role(user: User, permission: str) -> None:
    if not _role_allows(user.role, permission):
        raise PermissionDeniedError(f"Your role ('{user.role.value}') does not have permission to '{permission}'.")
    if permission in get_restricted_permissions(user):
        raise PermissionDeniedError(f"Your account has been restricted from '{permission}' by an admin.")


def _check_ownership(db: Session, user: User, permission: str, arguments: dict) -> None:
    if user.role == UserRole.admin:
        return  # admins bypass ownership checks
    ownership_check = _OWNERSHIP_CHECKS.get(permission)
    if ownership_check is not None:
        ownership_check(OwnershipContext(db=db, user=user, arguments=arguments))


def require_permission_for(db: Session, user: User, permission: str, arguments: dict) -> None:
    """REST-facing entry point: `permission` is a key already known to
    the caller, e.g. "contacts:update". Raises PermissionDeniedError if
    `user` may not perform it (optionally scoped to `arguments`, e.g.
    {"contact_id": 42})."""
    _check_role(user, permission)
    _check_ownership(db, user, permission, arguments)


def require_permission(db: Session, user: User, tool_name: str, arguments: dict) -> None:
    """Copilot-facing entry point: `tool_name` is a registered tool name
    (e.g. "update_task"), translated to its permission key via
    TOOL_PERMISSIONS. No-op for tools that declare no permission
    (read-only tools, or a write tool that intentionally opts out)."""
    permission = TOOL_PERMISSIONS.get(tool_name)
    if permission is None:
        return
    require_permission_for(db, user, permission, arguments)
