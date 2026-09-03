import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.billing.subscription_service import TRIAL_DAYS, get_or_create as get_or_create_subscription
from app.database import get_db
from app.defaults import create_default_pipeline_stages
from app.deps import get_current_user, is_platform_admin
from app.email import send_admin_notification
from app.models import Organization, User, UserRole
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(access_token: str, user: User) -> TokenResponse:
    """Builds the UserBrief with is_platform_admin filled in from the
    PLATFORM_ADMIN_EMAILS allowlist -- see schemas.UserBrief's docstring
    for why that can't just come from `from_attributes=True` alone."""
    resp = TokenResponse(access_token=access_token, user=user)
    resp.user.is_platform_admin = is_platform_admin(user)
    return resp


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "org"
    return base[:60]


def _unique_slug(db: Session, name: str) -> str:
    base = _slugify(name)
    slug = base
    suffix = 1
    while db.query(Organization).filter(Organization.slug == slug).first() is not None:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # Every registration provisions a brand-new tenant. There is
    # deliberately no "first user in the whole system becomes admin"
    # concept anymore -- that was a single-tenant shortcut. Every
    # organization gets exactly one first admin: whoever created it.
    org = Organization(name=payload.organization_name, slug=_unique_slug(db, payload.organization_name))
    db.add(org)
    db.flush()  # assigns org.id without committing yet, so this stays one transaction

    user = User(
        organization_id=org.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Every organization gets a Subscription row from the moment it
    # exists -- see app/billing/subscription_service.py for why "no
    # row yet" is never a valid state to leave an org in (every
    # entitlement/usage check assumes get_or_create() can find one).
    # This lands the org as `pending_trial`, not an already-running
    # trial -- the 14-day clock only starts once a Platform Admin
    # reviews and approves the request below.
    get_or_create_subscription(db, org)

    # Without at least one pipeline stage, Deal creation is impossible
    # (every deal requires a valid stage_id) -- a brand-new tenant must
    # not land on an empty, unusable Deals screen. See app/defaults.py.
    create_default_pipeline_stages(db, org)
    db.commit()

    # The trial doesn't self-activate -- an admin has to look at every
    # new signup first. Best-effort per app/email.py's contract (never
    # raises); the Platform Admin panel's Organizations tab is the real
    # queue this lands in either way (org.status == "pending_trial"),
    # this email is just the notification.
    send_admin_notification(
        subject=f"[ACEWIN] New trial request — {org.name}",
        body=(
            f"Organization: {org.name} (#{org.id})\n"
            f"Admin: {user.full_name} <{user.email}>\n\n"
            f"This organization just registered and is requesting the {TRIAL_DAYS}-day Basic trial.\n"
            f"Review it and, if it looks legitimate, approve the trial from the Platform Admin panel:\n"
            f"Organizations -> {org.name} -> Manage -> Approve trial.\n"
        ),
    )

    token = create_access_token(subject=user.email)
    return _token_response(token, user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    token = create_access_token(subject=user.email)
    return _token_response(token, user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    out = UserOut.model_validate(current_user)
    out.is_platform_admin = is_platform_admin(current_user)
    return out
