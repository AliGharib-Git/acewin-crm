"""
Gamification Engine -- Phase 1 (see docs/gamification-rnd.md).

Mirrors the KPI Engine's philosophy (app/kpi/engine.py): a user's total
points, level, and leaderboard position are always DERIVED live from
PointsLedger, never cached on User -- so they can never desync from the
audit trail they're computed from. The only things persisted directly
are the ledger rows themselves (see models.py:PointsLedger) and
UserBadge rows once a badge is earned.

Two decisions the R&D doc left open (section 9) are settled here, with
the reasoning kept next to the code that encodes them rather than only
in the doc:
  1. Leaderboard defaults to WEEKLY (doc's own recommendation, for
     fairness -- a new hire shouldn't be compared against a 2-year
     veteran on an all-time board by default).
  2. Admins are INCLUDED in the leaderboard by default, but an org can
     flip GamificationSettings.include_admins_in_leaderboard off if a
     manager's own activity shouldn't read as "competing" with their
     team -- see section 3.4.
Real-world rewards (Phase 3) and per-user leaderboard opt-out
(Phase 2) are out of scope here by design, not by oversight.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.gamification.badges import BADGE_RULES
from app.models import (
    Badge,
    GamificationSettings,
    Organization,
    PointSourceType,
    PointsLedger,
    Task,
    TaskStatus,
    User,
    UserBadge,
    UserRole,
)

# ---------------------------------------------------------------------------
# Settings / on-off switch
# ---------------------------------------------------------------------------


def get_or_create_settings(db: Session, org: Organization) -> GamificationSettings:
    row = db.query(GamificationSettings).filter(GamificationSettings.organization_id == org.id).first()
    if row is None:
        row = GamificationSettings(organization_id=org.id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def is_enabled(db: Session, org: Organization) -> bool:
    return get_or_create_settings(db, org).enabled


def token_label(db: Session, org: Organization, language: str = "en") -> tuple[str, str]:
    """(name, icon) for the org's custom points currency -- e.g. ("سکه
    اکرمی", "🪙") -- falls back to the generic "Points"/"امتیاز" default
    an org gets until an admin renames it (see GamificationSettings)."""
    s = get_or_create_settings(db, org)
    return (s.token_name_fa if language == "fa" else s.token_name_en), s.token_icon


# ---------------------------------------------------------------------------
# Levels
#
# threshold(n) = cumulative points needed to REACH level n+1 (n starting
# at 1), i.e. threshold(0) = 0 -- everyone starts at level 1 with zero
# points. Linear-progressive curve (100 * n^1.3), per section 3.2: each
# level takes a bit more than the last, mobile-game style, not a steep
# RPG curve.
# ---------------------------------------------------------------------------


def threshold(n: int) -> int:
    if n <= 0:
        return 0
    return round(100 * (n ** 1.3))


# Level-band titles (section 3.2) -- branded, not "Level 1/2/3". Each
# entry is (minimum level, name_en, name_fa); bands are looked up by
# the highest matching minimum.
_LEVEL_TITLES: list[tuple[int, str, str]] = [
    (1, "Beginner", "مبتدی"),
    (3, "Active", "فعال"),
    (6, "Professional", "حرفه‌ای"),
    (10, "Sales Champion", "قهرمان فروش"),
    (15, "Legendary", "افسانه‌ای"),
]


def level_title(level: int, language: str = "en") -> str:
    title = _LEVEL_TITLES[0]
    for band in _LEVEL_TITLES:
        if level >= band[0]:
            title = band
    return title[2] if language == "fa" else title[1]


def level_for_points(points: int) -> int:
    """Closed-form estimate refined by a small bounded correction loop --
    avoids an unbounded while-loop for very high point totals (a
    long-tenured top performer), while staying exact."""
    points = max(0, points)
    if points == 0:
        return 1
    # Invert threshold(n) = 100 * n^1.3  =>  n = (points/100) ** (1/1.3)
    guess = max(1, int((points / 100) ** (1 / 1.3)))
    n = guess
    while threshold(n) > points and n > 0:
        n -= 1
    while threshold(n + 1) <= points:
        n += 1
    return n + 1


@dataclass
class LevelProgress:
    level: int
    title_en: str
    title_fa: str
    points_in_level: int
    points_for_next_level: int
    progress_ratio: float  # 0..1


def level_progress(total: int) -> LevelProgress:
    total = max(0, total)
    lvl = level_for_points(total)
    lower = threshold(lvl - 1)
    upper = threshold(lvl)
    span = max(1, upper - lower)
    return LevelProgress(
        level=lvl,
        title_en=level_title(lvl, "en"),
        title_fa=level_title(lvl, "fa"),
        points_in_level=total - lower,
        points_for_next_level=span,
        progress_ratio=round(min(1.0, (total - lower) / span), 4),
    )


def total_points(db: Session, org_id: int, user_id: int) -> int:
    return (
        db.query(func.coalesce(func.sum(PointsLedger.points), 0))
        .filter(PointsLedger.organization_id == org_id, PointsLedger.user_id == user_id)
        .scalar()
        or 0
    )


# ---------------------------------------------------------------------------
# Anti-abuse: soft monthly caps per source (section 6 -- "quantity must
# not crush quality" / Goodhart's Law guard). A cap of None means
# uncapped (deal_won is capped implicitly by the formula itself, not a
# raw count cap).
# ---------------------------------------------------------------------------

_MONTHLY_SOFT_CAPS: dict[PointSourceType, int | None] = {
    PointSourceType.deal_won: None,
    PointSourceType.task_completed: 60,  # ~2/day average ceiling
    PointSourceType.activity_logged: 40,  # ~40 qualifying calls/meetings a month
    PointSourceType.contact_converted: None,
    PointSourceType.streak_bonus: None,
    PointSourceType.team_assist: None,
}


def _points_this_month(db: Session, org_id: int, user_id: int, source_type: PointSourceType, as_of: datetime | None = None) -> int:
    now = as_of or datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.coalesce(func.sum(PointsLedger.points), 0))
        .filter(
            PointsLedger.organization_id == org_id,
            PointsLedger.user_id == user_id,
            PointsLedger.source_type == source_type,
            PointsLedger.points > 0,
            PointsLedger.created_at >= start_of_month,
        )
        .scalar()
        or 0
    )


def _already_awarded(db: Session, org_id: int, source_type: PointSourceType, source_id: str) -> bool:
    """Idempotency guard: has this exact event already produced a ledger
    row? Keyed on source_type+source_id, org-scoped -- not per-user,
    since a source_id ("deal:123") is only ever awarded to one user."""
    return (
        db.query(PointsLedger.id)
        .filter(
            PointsLedger.organization_id == org_id,
            PointsLedger.source_type == source_type,
            PointsLedger.source_id == source_id,
        )
        .first()
        is not None
    )


# ---------------------------------------------------------------------------
# Awarding points
# ---------------------------------------------------------------------------


@dataclass
class AwardResult:
    ledger_entry: PointsLedger
    total_points: int
    leveled_up: bool
    previous_level: int
    new_badges: list[Badge] = field(default_factory=list)


def award_points(
    db: Session,
    org: Organization,
    user: User,
    source_type: PointSourceType,
    source_id: str,
    base_points: int,
    reason_en: str,
    reason_fa: str,
    occurred_at: datetime | None = None,
) -> AwardResult | None:
    """Awards points for one real CRM event. Returns None (no-op, no
    ledger row) when:
      - gamification is switched off for this org (design principle #6),
      - this exact event was already awarded (idempotency -- a retry or
        double-click must never double-award),
      - the source's soft monthly cap is already reached (anti-farming).
    A clamped-but-nonzero award still goes through at the reduced
    amount, so a user who's mostly at their cap still sees *some*
    feedback rather than a silent nothing.

    `occurred_at` backdates the ledger row to when the underlying event
    actually happened (a deal's closed_at, a task's completed_at, an
    activity's created_at) instead of "now" -- callers pass their
    entity's own timestamp, which is a no-op for live traffic (that
    timestamp IS "now" at the moment a deal gets marked Won) but is
    what makes historical/seed data show up on the right day's
    leaderboard instead of everything landing on "today".
    """
    if base_points <= 0:
        return None
    if not is_enabled(db, org):
        return None
    if _already_awarded(db, org.id, source_type, source_id):
        return None

    cap = _MONTHLY_SOFT_CAPS.get(source_type)
    points_to_award = base_points
    if cap is not None:
        remaining = cap - _points_this_month(db, org.id, user.id, source_type, as_of=occurred_at)
        if remaining <= 0:
            return None
        points_to_award = min(base_points, remaining)

    previous_total = total_points(db, org.id, user.id)
    previous_level = level_for_points(previous_total)

    entry = PointsLedger(
        organization_id=org.id,
        user_id=user.id,
        source_type=source_type,
        source_id=source_id,
        points=points_to_award,
        reason_en=reason_en,
        reason_fa=reason_fa,
    )
    if occurred_at is not None:
        entry.created_at = occurred_at
    db.add(entry)
    db.commit()
    db.refresh(entry)

    new_total = previous_total + points_to_award
    new_level = level_for_points(new_total)
    new_badges = evaluate_badges(db, org, user)

    return AwardResult(
        ledger_entry=entry,
        total_points=new_total,
        leveled_up=new_level > previous_level,
        previous_level=previous_level,
        new_badges=new_badges,
    )


def revoke_points_for_source(db: Session, org: Organization, source_type: PointSourceType, source_id: str, reason_en: str, reason_fa: str) -> PointsLedger | None:
    """Compensating entry for an event that no longer holds (a Deal that
    was won got deleted or moved out of the Won stage, a Task got
    reopened, ...). Never mutates or deletes the original row -- see
    PointsLedger's docstring. Idempotent: a source already revoked (its
    own ":revoke" source_id already exists) is left alone."""
    revoke_id = f"{source_id}:revoke"
    if _already_awarded(db, org.id, source_type, revoke_id):
        return None

    positive_total = (
        db.query(func.coalesce(func.sum(PointsLedger.points), 0))
        .filter(
            PointsLedger.organization_id == org.id,
            PointsLedger.source_type == source_type,
            PointsLedger.source_id == source_id,
            PointsLedger.points > 0,
        )
        .scalar()
        or 0
    )
    if positive_total <= 0:
        return None  # nothing was ever awarded for this event

    original = (
        db.query(PointsLedger)
        .filter(
            PointsLedger.organization_id == org.id,
            PointsLedger.source_type == source_type,
            PointsLedger.source_id == source_id,
            PointsLedger.points > 0,
        )
        .first()
    )
    entry = PointsLedger(
        organization_id=org.id,
        user_id=original.user_id,
        source_type=source_type,
        source_id=revoke_id,
        points=-positive_total,
        reason_en=reason_en,
        reason_fa=reason_fa,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------


def evaluate_badges(db: Session, org: Organization, user: User) -> list[Badge]:
    """Awards any badges `user` newly qualifies for, and returns them.
    Only evaluates rules for badges not already held (milestone badges
    can only ever be earned once -- see UserBadge's unique constraint),
    so this stays cheap even called after every single award."""
    already_held = {
        code
        for (code,) in db.query(Badge.code)
        .join(UserBadge, UserBadge.badge_id == Badge.id)
        .filter(UserBadge.user_id == user.id, UserBadge.organization_id == org.id, UserBadge.period_key.is_(None))
        .all()
    }
    catalog = {b.code: b for b in db.query(Badge).all()}

    newly_awarded: list[Badge] = []
    for rule in BADGE_RULES:
        if rule.is_seasonal or rule.code in already_held:
            continue
        badge_row = catalog.get(rule.code)
        if badge_row is None:
            continue  # catalog not synced yet -- see badges.sync_badge_catalog
        if rule.predicate(db, org.id, user.id):
            db.add(UserBadge(organization_id=org.id, user_id=user.id, badge_id=badge_row.id, period_key=None))
            newly_awarded.append(badge_row)

    if newly_awarded:
        db.commit()
    return newly_awarded


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


def _period_start(period: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if period == "weekly":
        # ISO week, Monday start. Gregorian, like the rest of the app's
        # reporting (KPI Engine, dashboard trends) -- a Jalali-calendar
        # week boundary is a reasonable Phase 2 refinement, not silently
        # assumed here.
        return (now - relativedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None  # all_time


@dataclass
class LeaderboardEntry:
    user_id: int
    full_name: str
    role: str
    points: int
    rank: int
    level: int
    level_title_en: str
    level_title_fa: str


def leaderboard(
    db: Session,
    org: Organization,
    period: str = "weekly",
    include_admins: bool | None = None,
) -> list[LeaderboardEntry]:
    """Organization-scoped only (design principle #2 -- never
    cross-tenant). `period` ranks by points EARNED in that window;
    `level`/title shown per entry is always the user's real, all-time
    level, since a level is a standing rank, not a weekly reset."""
    if include_admins is None:
        include_admins = get_or_create_settings(db, org).include_admins_in_leaderboard

    query = (
        db.query(User.id, User.full_name, User.role, func.coalesce(func.sum(PointsLedger.points), 0).label("points"))
        .join(PointsLedger, PointsLedger.user_id == User.id)
        .filter(PointsLedger.organization_id == org.id, User.organization_id == org.id, User.is_active.is_(True))
    )
    start = _period_start(period)
    if start is not None:
        query = query.filter(PointsLedger.created_at >= start)
    if not include_admins:
        query = query.filter(User.role != UserRole.admin)

    rows = query.group_by(User.id, User.full_name, User.role).having(func.sum(PointsLedger.points) > 0).order_by(func.sum(PointsLedger.points).desc()).all()

    entries: list[LeaderboardEntry] = []
    for rank, (user_id, full_name, role, points) in enumerate(rows, start=1):
        alltime = total_points(db, org.id, user_id)
        progress = level_progress(alltime)
        entries.append(
            LeaderboardEntry(
                user_id=user_id,
                full_name=full_name,
                role=role.value if hasattr(role, "value") else role,
                points=int(points),
                rank=rank,
                level=progress.level,
                level_title_en=progress.title_en,
                level_title_fa=progress.title_fa,
            )
        )
    return entries


# ---------------------------------------------------------------------------
# Accountability -- the flip side of points. A rewards program that only
# ever shows wins hides who's falling behind just as effectively as one
# that shows nothing at all. This is deliberately NOT a point penalty
# (points only ever go up from real work -- see design principle #3 in
# the R&D doc) -- it's a separate, always-visible follow-through number
# sitting right next to the reward numbers, in both the personal
# profile and the admin panel.
# ---------------------------------------------------------------------------

_ACCOUNTABILITY_WINDOW_DAYS = 30


@dataclass
class TaskAccountability:
    completed: int
    total: int
    overdue: int  # currently pending AND past its due date -- the "didn't do it, and it's late" count


def task_accountability(db: Session, org_id: int, user_id: int, days: int = _ACCOUNTABILITY_WINDOW_DAYS) -> TaskAccountability:
    """Of the tasks assigned to this user in the last `days` days: how
    many did they actually finish, and how many are sitting overdue
    right now (independent of the window -- an old overdue task doesn't
    stop being late just because it's outside the recent-activity
    lookback)? `total` only counts tasks that exist to be judged against
    -- someone with zero assigned tasks shows 0/0, not a misleading 0%."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    total = (
        db.query(func.count(Task.id))
        .filter(Task.organization_id == org_id, Task.assigned_to_id == user_id, Task.created_at >= since)
        .scalar()
        or 0
    )
    completed = (
        db.query(func.count(Task.id))
        .filter(
            Task.organization_id == org_id,
            Task.assigned_to_id == user_id,
            Task.created_at >= since,
            Task.status == TaskStatus.completed,
        )
        .scalar()
        or 0
    )
    overdue = (
        db.query(func.count(Task.id))
        .filter(
            Task.organization_id == org_id,
            Task.assigned_to_id == user_id,
            Task.status == TaskStatus.pending,
            Task.due_date.isnot(None),
            Task.due_date < datetime.now(timezone.utc),
        )
        .scalar()
        or 0
    )
    return TaskAccountability(completed=completed, total=total, overdue=overdue)


# ---------------------------------------------------------------------------
# Per-user summary (profile widget / dashboard widget)
# ---------------------------------------------------------------------------


@dataclass
class UserGamificationSummary:
    total_points: int
    level: int
    level_title_en: str
    level_title_fa: str
    points_in_level: int
    points_for_next_level: int
    progress_ratio: float
    weekly_points: int
    monthly_points: int
    weekly_rank: int | None
    monthly_rank: int | None
    badge_count: int
    tasks_completed: int
    tasks_total: int
    tasks_overdue: int


def _points_since(db: Session, org_id: int, user_id: int, start: datetime | None) -> int:
    query = db.query(func.coalesce(func.sum(PointsLedger.points), 0)).filter(
        PointsLedger.organization_id == org_id, PointsLedger.user_id == user_id
    )
    if start is not None:
        query = query.filter(PointsLedger.created_at >= start)
    return int(query.scalar() or 0)


def _rank_of(entries: list[LeaderboardEntry], user_id: int) -> int | None:
    for entry in entries:
        if entry.user_id == user_id:
            return entry.rank
    return None


def user_summary(db: Session, org: Organization, user: User) -> UserGamificationSummary:
    total = total_points(db, org.id, user.id)
    progress = level_progress(total)
    weekly_points = _points_since(db, org.id, user.id, _period_start("weekly"))
    monthly_points = _points_since(db, org.id, user.id, _period_start("monthly"))
    weekly_board = leaderboard(db, org, "weekly")
    monthly_board = leaderboard(db, org, "monthly")
    badge_count = (
        db.query(func.count(UserBadge.id))
        .filter(UserBadge.organization_id == org.id, UserBadge.user_id == user.id)
        .scalar()
        or 0
    )
    accountability = task_accountability(db, org.id, user.id)
    return UserGamificationSummary(
        total_points=total,
        level=progress.level,
        level_title_en=progress.title_en,
        level_title_fa=progress.title_fa,
        points_in_level=progress.points_in_level,
        points_for_next_level=progress.points_for_next_level,
        progress_ratio=progress.progress_ratio,
        weekly_points=weekly_points,
        monthly_points=monthly_points,
        weekly_rank=_rank_of(weekly_board, user.id),
        monthly_rank=_rank_of(monthly_board, user.id),
        badge_count=badge_count,
        tasks_completed=accountability.completed,
        tasks_total=accountability.total,
        tasks_overdue=accountability.overdue,
    )


def user_ledger(db: Session, org: Organization, user: User, page: int, page_size: int) -> tuple[list[PointsLedger], int]:
    query = (
        db.query(PointsLedger)
        .filter(PointsLedger.organization_id == org.id, PointsLedger.user_id == user.id)
        .order_by(PointsLedger.created_at.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


def user_badges(db: Session, org: Organization, user: User) -> list[tuple[Badge, UserBadge | None]]:
    """Full catalog, each paired with the user's UserBadge row if earned
    (None if not) -- lets the profile page render locked/unlocked state
    for every badge, not just the ones already won."""
    catalog = db.query(Badge).order_by(Badge.id).all()
    earned = {
        ub.badge_id: ub
        for ub in db.query(UserBadge)
        .options(joinedload(UserBadge.badge))
        .filter(UserBadge.organization_id == org.id, UserBadge.user_id == user.id)
        .all()
    }
    return [(badge, earned.get(badge.id)) for badge in catalog]


# ---------------------------------------------------------------------------
# Admin panel -- org-wide visibility into everyone's activity, not just
# "am I doing well" like the member-facing /me and /ledger. This is
# what section 5 of the R&D doc calls "an admin needs to see the whole
# program running, not just their own score."
# ---------------------------------------------------------------------------


@dataclass
class AdminUserRow:
    user_id: int
    full_name: str
    role: str
    total_points: int
    level: int
    level_title_en: str
    level_title_fa: str
    badge_count: int
    weekly_points: int
    monthly_points: int
    tasks_completed: int
    tasks_total: int
    tasks_overdue: int


def admin_user_overview(db: Session, org: Organization) -> list[AdminUserRow]:
    """Every active member of the org, sorted by total points -- WITH
    zero-point rows included, unlike leaderboard() (which only ranks
    people who've earned something). An admin auditing the whole
    program needs to see who hasn't engaged yet at all, not just who's
    winning -- and needs the follow-through numbers (tasks_completed /
    tasks_total / tasks_overdue) sitting right next to the points, not
    hidden in a separate report, since a high point total and a poor
    completion rate can both be true of the same person at once."""
    users = db.query(User).filter(User.organization_id == org.id, User.is_active.is_(True)).order_by(User.full_name).all()
    weekly_start = _period_start("weekly")
    monthly_start = _period_start("monthly")
    rows: list[AdminUserRow] = []
    for u in users:
        total = total_points(db, org.id, u.id)
        progress = level_progress(total)
        badge_count = (
            db.query(func.count(UserBadge.id))
            .filter(UserBadge.organization_id == org.id, UserBadge.user_id == u.id)
            .scalar()
            or 0
        )
        accountability = task_accountability(db, org.id, u.id)
        rows.append(
            AdminUserRow(
                user_id=u.id,
                full_name=u.full_name,
                role=u.role.value if hasattr(u.role, "value") else u.role,
                total_points=total,
                level=progress.level,
                level_title_en=progress.title_en,
                level_title_fa=progress.title_fa,
                badge_count=badge_count,
                weekly_points=_points_since(db, org.id, u.id, weekly_start),
                monthly_points=_points_since(db, org.id, u.id, monthly_start),
                tasks_completed=accountability.completed,
                tasks_total=accountability.total,
                tasks_overdue=accountability.overdue,
            )
        )
    rows.sort(key=lambda r: r.total_points, reverse=True)
    return rows


def admin_ledger(
    db: Session,
    org: Organization,
    page: int,
    page_size: int,
    user_id: int | None = None,
    source_type: PointSourceType | None = None,
) -> tuple[list[PointsLedger], int]:
    """The full org-wide feed behind the admin panel: every point ever
    awarded or revoked, across every member, optionally narrowed to one
    person or one source -- exactly what "the whole program running"
    looks like, not just one person's slice of it."""
    query = (
        db.query(PointsLedger)
        .options(joinedload(PointsLedger.user))
        .filter(PointsLedger.organization_id == org.id)
    )
    if user_id is not None:
        query = query.filter(PointsLedger.user_id == user_id)
    if source_type is not None:
        query = query.filter(PointsLedger.source_type == source_type)
    query = query.order_by(PointsLedger.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


# ---------------------------------------------------------------------------
# Deal-won point formula (section 3.1)
# ---------------------------------------------------------------------------

_DEAL_WON_BASE = 10
_DEAL_WON_VALUE_BONUS_CAP = 30  # hard ceiling on the value-scaled bonus, on top of the base
_TASK_COMPLETED_POINTS = 2
_ACTIVITY_LOGGED_POINTS = 1


def deal_won_points(db: Session, org: Organization, deal_value: float) -> int:
    """10 + round(value / avg_won_deal_value * 5), capped -- per section
    3.1. Falls back to just the base when there's no prior won-deal
    history to compare against yet (this org's very first won deal), so
    the formula never divides by zero or over-rewards an early outlier."""
    from app.models import Deal, PipelineStage

    avg_value = (
        db.query(func.avg(Deal.value))
        .join(PipelineStage, PipelineStage.id == Deal.stage_id)
        .filter(Deal.organization_id == org.id, PipelineStage.is_won.is_(True), Deal.value > 0)
        .scalar()
    )
    if not avg_value or avg_value <= 0:
        return _DEAL_WON_BASE
    bonus = round(float(deal_value) / float(avg_value) * 5)
    bonus = max(0, min(bonus, _DEAL_WON_VALUE_BONUS_CAP))
    return _DEAL_WON_BASE + bonus
