from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.permissions import PermissionDeniedError, require_permission_for
from app.config import settings
from app.database import get_db
from app.models import Organization, User, UserRole
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    email = decode_access_token(credentials.credentials)
    if email is None:
        raise unauthorized

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise unauthorized
    return user


def get_current_org(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    """Resolves the tenant for the current request from the
    authenticated user's `organization_id` -- never from a client-
    supplied header, query param or body field, since that would let a
    caller simply ask for another tenant's data.

    This is the ONE place tenant context is derived. Every router that
    touches a tenant-owned table (Contact, Deal, Company, Task,
    Activity, PipelineStage, Tag, KPITarget, Objective/KeyResult,
    AgentActionLog, ...) must depend on this and filter its queries by
    `organization_id == org.id`, and must set `organization_id = org.id`
    on every record it creates. Reusable helpers for that pattern live
    in app.tenancy.
    """
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if org is None or not org.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization not found or inactive")
    return org


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def is_platform_admin(user: User) -> bool:
    """Whether `user` has cross-tenant Platform Admin access -- an
    email allowlist (PLATFORM_ADMIN_EMAILS), deliberately independent
    of UserRole/organization_id, since this one operator account needs
    to see and manage every tenant, not just the one it happens to
    belong to. See app/config.py for the settings field and
    app/routers/platform_admin.py for what it unlocks."""
    return user.email.lower() in settings.platform_admin_email_list


def get_current_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
    return user


def enforce_permission(db: Session, user: User, permission: str, arguments: dict | None = None) -> None:
    """FastAPI-friendly wrapper around app.ai.permissions.require_permission_for:
    the same role + ownership rules the Copilot Action Agent enforces on
    its tools, applied to a REST endpoint. Converts a denial into a 403
    instead of a raw PermissionDeniedError, since routers should never
    need to import that exception type themselves.

    `arguments` carries whatever the ownership check needs, e.g.
    {"task_id": 42} -- see app/ai/permissions.py's _OWNERSHIP_CHECKS.
    """
    try:
        require_permission_for(db, user, permission, arguments or {})
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def enforce_feature(db: Session, org: Organization, feature_code: str) -> None:
    """Thin re-export so routers only need `from app.deps import ...` for
    both role/ownership permission checks (enforce_permission, above)
    and plan/entitlement checks -- one import line, two related but
    distinct axes of authorization (who you are vs. what your org pays
    for). See app/billing/entitlements.py for the actual logic."""
    from app.billing.entitlements import require_feature

    require_feature(db, org, feature_code)


def enforce_within_limit(db: Session, org: Organization, metric: str, increment: int = 1) -> None:
    from app.billing.entitlements import require_within_limit

    require_within_limit(db, org, metric, increment)
