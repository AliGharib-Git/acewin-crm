from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.permissions import ALL_PERMISSION_KEYS as _ALL_PERMISSION_KEYS
from app.ai.permissions import PERMISSION_CATALOG
from app.audit import record_action
from app.database import get_db
from app.deps import enforce_within_limit, get_current_admin, get_current_org, get_current_user
from app.models import AgentActionStatus, Organization, User
from app.schemas import UserCreate, UserOut, UserPermissionsUpdate, UserRoleUpdate
from app.security import hash_password
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/permissions/catalog", response_model=dict[str, list[str]])
def permissions_catalog(admin: User = Depends(get_current_admin)):
    """Every permission key that can be individually restricted, grouped
    by resource -- powers the checkbox list in the admin's "restrict
    this account" UI. Admin-only: it's only useful alongside the
    endpoint below, and no reason to expose the org's permission
    layout to non-admins."""
    return PERMISSION_CATALOG


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    return scoped(db, User, org).order_by(User.full_name).all()


@router.post("", response_model=UserOut, status_code=201)
def invite_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    """Adds a teammate directly to the caller's organization. A real
    email-invitation flow (pending invite -> accept -> set own
    password) is a natural follow-up; for now the admin sets an initial
    password and shares it out of band, which keeps this endpoint
    honest about what it actually does rather than pretending to send
    an email that isn't wired up."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    enforce_within_limit(db, org, "users")
    user = User(
        organization_id=org.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    record_action(
        db, admin, "users:invite", source="api", status=AgentActionStatus.success,
        arguments={"email": payload.email, "role": payload.role.value}, entity_type="user", entity_id=user.id,
    )
    return user


@router.patch("/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    user = get_or_404(db, User, user_id, org, detail="User not found")
    previous_role = user.role.value
    user.role = payload.role
    db.commit()
    db.refresh(user)
    record_action(
        db, admin, "users:update_role", source="api", status=AgentActionStatus.success,
        arguments={"user_id": user_id, "new_role": payload.role.value},
        previous_state={"role": previous_role}, entity_type="user", entity_id=user.id,
    )
    return user


@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    user = get_or_404(db, User, user_id, org, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    record_action(
        db, admin, "users:toggle_active", source="api", status=AgentActionStatus.success,
        arguments={"user_id": user_id, "is_active": user.is_active}, entity_type="user", entity_id=user.id,
    )
    return user


@router.patch("/{user_id}/permissions", response_model=UserOut)
def update_permissions(
    user_id: int,
    payload: UserPermissionsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    """Sets the full list of permission keys this one account is
    restricted from -- on top of whatever its role would otherwise
    allow (see app/ai/permissions.py). This narrows access only; it can
    never grant a permission the user's role doesn't already have, so
    restricting a member's already-absent "deals:delete" is a no-op,
    not an error -- unknown/irrelevant keys are simply ignored rather
    than rejected, since the picker only ever sends real catalog keys
    anyway."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot restrict your own account")
    user = get_or_404(db, User, user_id, org, detail="User not found")

    valid_keys = sorted(set(payload.restricted_permissions) & _ALL_PERMISSION_KEYS)
    previous = user.restricted_permissions
    user.restricted_permissions = valid_keys
    db.commit()
    db.refresh(user)
    record_action(
        db, admin, "users:update_permissions", source="api", status=AgentActionStatus.success,
        arguments={"user_id": user_id, "restricted_permissions": valid_keys},
        previous_state={"restricted_permissions": previous}, entity_type="user", entity_id=user.id,
    )
    return user
