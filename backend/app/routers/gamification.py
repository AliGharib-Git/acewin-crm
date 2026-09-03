"""
Gamification Engine API (Pro feature -- "gamification.core", see
app/billing/plans.py). Every number here is computed live from
PointsLedger by app/gamification/engine.py, exactly like the KPI
Engine computes live from Deal/Task -- nothing about a user's score is
ever cached or hand-editable through this API.

Two authorization axes, same pattern as every other Pro-gated router
(see app/routers/kpis.py):
  - enforce_feature(..., "gamification.core") -- does this org's PLAN
    include gamification at all (402 if not).
  - the org-level enabled/disabled toggle (GamificationSettings) -- a
    plan-eligible org can still have gamification switched off; that's
    reflected as `enabled: false` in the response body, not an error,
    since it's a legitimate admin preference, not a fault.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_feature, get_current_admin, get_current_org, get_current_user
from app.gamification import engine
from app.models import AgentActionStatus, Organization, PointSourceType, User
from app.schemas import (
    AdminLedgerEntryOut,
    AdminLedgerPage,
    AdminUserSummaryOut,
    BadgeOut,
    GamificationSettingsOut,
    GamificationSettingsUpdate,
    GamificationSummaryOut,
    LeaderboardEntryOut,
    LedgerEntryOut,
    LedgerPage,
)

router = APIRouter(prefix="/api/gamification", tags=["gamification"])


@router.get("/me", response_model=GamificationSummaryOut)
def get_my_summary(
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    if not engine.is_enabled(db, org):
        return GamificationSummaryOut(enabled=False)

    s = engine.user_summary(db, org, current_user)
    token_name, token_icon = engine.token_label(db, org, lang)
    return GamificationSummaryOut(
        enabled=True,
        total_points=s.total_points,
        level=s.level,
        level_title=s.level_title_fa if lang == "fa" else s.level_title_en,
        points_in_level=s.points_in_level,
        points_for_next_level=s.points_for_next_level,
        progress_ratio=s.progress_ratio,
        weekly_points=s.weekly_points,
        monthly_points=s.monthly_points,
        weekly_rank=s.weekly_rank,
        monthly_rank=s.monthly_rank,
        badge_count=s.badge_count,
        token_name=token_name,
        token_icon=token_icon,
        tasks_completed=s.tasks_completed,
        tasks_total=s.tasks_total,
        tasks_overdue=s.tasks_overdue,
    )


@router.get("/leaderboard", response_model=list[LeaderboardEntryOut])
def get_leaderboard(
    period: str = Query("weekly", pattern="^(weekly|monthly|all_time)$"),
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    if not engine.is_enabled(db, org):
        return []

    entries = engine.leaderboard(db, org, period)
    return [
        LeaderboardEntryOut(
            user_id=e.user_id,
            full_name=e.full_name,
            role=e.role,
            is_you=e.user_id == current_user.id,
            points=e.points,
            rank=e.rank,
            level=e.level,
            level_title=e.level_title_fa if lang == "fa" else e.level_title_en,
        )
        for e in entries
    ]


@router.get("/badges", response_model=list[BadgeOut])
def get_my_badges(
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    if not engine.is_enabled(db, org):
        return []

    fa = lang == "fa"
    return [
        BadgeOut(
            code=badge.code,
            name=badge.name_fa if fa else badge.name_en,
            description=badge.description_fa if fa else badge.description_en,
            icon_key=badge.icon_key,
            is_seasonal=badge.is_seasonal,
            earned=user_badge is not None,
            awarded_at=user_badge.awarded_at if user_badge else None,
        )
        for badge, user_badge in engine.user_badges(db, org, current_user)
    ]


@router.get("/ledger", response_model=LedgerPage)
def get_my_ledger(
    lang: str = Query("en", pattern="^(en|fa)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    if not engine.is_enabled(db, org):
        return LedgerPage(items=[], total=0, page=page, page_size=page_size)

    fa = lang == "fa"
    rows, total = engine.user_ledger(db, org, current_user, page, page_size)
    return LedgerPage(
        items=[
            LedgerEntryOut(
                id=r.id,
                source_type=r.source_type.value,
                points=r.points,
                reason=r.reason_fa if fa else r.reason_en,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/settings", response_model=GamificationSettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    s = engine.get_or_create_settings(db, org)
    return GamificationSettingsOut(
        enabled=s.enabled,
        leaderboard_default_period=s.leaderboard_default_period,
        include_admins_in_leaderboard=s.include_admins_in_leaderboard,
        token_name_en=s.token_name_en,
        token_name_fa=s.token_name_fa,
        token_icon=s.token_icon,
    )


@router.put("/settings", response_model=GamificationSettingsOut)
def update_settings(
    payload: GamificationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    s = engine.get_or_create_settings(db, org)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        # An admin clearing the text field back to empty should fall
        # back to the stock label, not store an empty currency name.
        if field in ("token_name_en", "token_name_fa", "token_icon") and not (value or "").strip():
            continue
        setattr(s, field, value)
    db.commit()
    db.refresh(s)

    record_action(
        db, current_user, "gamification:update_settings", source="api", status=AgentActionStatus.success,
        arguments=data, entity_type="gamification_settings", entity_id=org.id, organization_id=org.id,
    )
    return GamificationSettingsOut(
        enabled=s.enabled,
        leaderboard_default_period=s.leaderboard_default_period,
        include_admins_in_leaderboard=s.include_admins_in_leaderboard,
        token_name_en=s.token_name_en,
        token_name_fa=s.token_name_fa,
        token_icon=s.token_icon,
    )


# ---------------------------------------------------------------------------
# Admin panel -- org-wide view of the whole program, not just "my own
# score". Every endpoint here requires get_current_admin, same pattern
# as PUT /settings above.
# ---------------------------------------------------------------------------


@router.get("/admin/users", response_model=list[AdminUserSummaryOut])
def admin_list_users(
    lang: str = Query("en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    fa = lang == "fa"
    return [
        AdminUserSummaryOut(
            user_id=r.user_id,
            full_name=r.full_name,
            role=r.role,
            total_points=r.total_points,
            level=r.level,
            level_title=r.level_title_fa if fa else r.level_title_en,
            badge_count=r.badge_count,
            weekly_points=r.weekly_points,
            monthly_points=r.monthly_points,
            tasks_completed=r.tasks_completed,
            tasks_total=r.tasks_total,
            tasks_overdue=r.tasks_overdue,
        )
        for r in engine.admin_user_overview(db, org)
    ]


@router.get("/admin/ledger", response_model=AdminLedgerPage)
def admin_list_ledger(
    lang: str = Query("en", pattern="^(en|fa)$"),
    user_id: int | None = Query(None),
    source_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    enforce_feature(db, org, "gamification.core")
    fa = lang == "fa"

    parsed_source_type: PointSourceType | None = None
    if source_type:
        try:
            parsed_source_type = PointSourceType(source_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid source_type")

    rows, total = engine.admin_ledger(db, org, page, page_size, user_id=user_id, source_type=parsed_source_type)
    return AdminLedgerPage(
        items=[
            AdminLedgerEntryOut(
                id=r.id,
                user_id=r.user_id,
                full_name=r.user.full_name if r.user else "",
                source_type=r.source_type.value,
                points=r.points,
                reason=r.reason_fa if fa else r.reason_en,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
