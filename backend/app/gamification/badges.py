"""
Badge catalog for the Gamification Engine.

Kept deliberately small for Phase 1 (5 milestone badges, per
docs/gamification-rnd.md section 3.3 and 7 -- "rare and meaningful, not
inflationary"). Each entry pairs a DB-seeded `Badge` row (see
sync_badge_catalog) with a predicate function that decides whether a
given user has newly earned it, evaluated from the PointsLedger --
never from a separate mutable "progress" counter, so a badge can never
drift out of sync with the ledger it's derived from.

Adding a badge: add one BadgeRule below (predicate reads the ledger /
user's level) -- sync_badge_catalog() picks it up on next app startup,
no migration needed, since `badges` is just a code-seeded reference
table (see Badge in app/models.py).
"""
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Badge, PointSourceType, PointsLedger


@dataclass(frozen=True)
class BadgeRule:
    code: str
    name_en: str
    name_fa: str
    description_en: str
    description_fa: str
    icon_key: str
    is_seasonal: bool
    # Returns True if `user` currently qualifies. Called only for badges
    # the user doesn't already hold (see engine.evaluate_badges), so
    # this only ever needs to answer "do they qualify right now" -- no
    # need to reason about "newly" qualifying.
    predicate: Callable[[Session, int, int], bool]


def _ledger_count(db: Session, org_id: int, user_id: int, source_type: PointSourceType) -> int:
    return (
        db.query(func.count(PointsLedger.id))
        .filter(
            PointsLedger.organization_id == org_id,
            PointsLedger.user_id == user_id,
            PointsLedger.source_type == source_type,
            PointsLedger.points > 0,  # count awards, not compensating rows
        )
        .scalar()
        or 0
    )


def _has_first_deal(db: Session, org_id: int, user_id: int) -> bool:
    return _ledger_count(db, org_id, user_id, PointSourceType.deal_won) >= 1


def _has_ten_deals(db: Session, org_id: int, user_id: int) -> bool:
    return _ledger_count(db, org_id, user_id, PointSourceType.deal_won) >= 10


def _has_25_tasks(db: Session, org_id: int, user_id: int) -> bool:
    return _ledger_count(db, org_id, user_id, PointSourceType.task_completed) >= 25


def _has_50_activities(db: Session, org_id: int, user_id: int) -> bool:
    return _ledger_count(db, org_id, user_id, PointSourceType.activity_logged) >= 50


def _is_rising_star(db: Session, org_id: int, user_id: int) -> bool:
    # Deliberately imported here (not at module scope) to avoid a
    # circular import -- engine.py imports badges.py to evaluate rules.
    from app.gamification.engine import level_for_points, total_points

    return level_for_points(total_points(db, org_id, user_id)) >= 5


BADGE_RULES: list[BadgeRule] = [
    BadgeRule(
        code="first_deal",
        name_en="First Deal",
        name_fa="اولین معامله",
        description_en="Closed your first won deal.",
        description_fa="اولین معامله‌ی خودتون رو با موفقیت بستید.",
        icon_key="badge_first_deal",
        is_seasonal=False,
        predicate=_has_first_deal,
    ),
    BadgeRule(
        code="ten_deals_won",
        name_en="Deal Closer",
        name_fa="معامله‌گر حرفه‌ای",
        description_en="Closed 10 won deals.",
        description_fa="۱۰ معامله رو با موفقیت بستید.",
        icon_key="badge_ten_deals",
        is_seasonal=False,
        predicate=_has_ten_deals,
    ),
    BadgeRule(
        code="task_finisher_25",
        name_en="Reliable",
        name_fa="قابل‌اعتماد",
        description_en="Completed 25 tasks on time.",
        description_fa="۲۵ تسک رو سر وقت تکمیل کردید.",
        icon_key="badge_task_finisher",
        is_seasonal=False,
        predicate=_has_25_tasks,
    ),
    BadgeRule(
        code="communicator_50",
        name_en="Communicator",
        name_fa="ارتباط‌گیر",
        description_en="Logged 50 meaningful calls or meetings.",
        description_fa="۵۰ تماس یا جلسه‌ی واقعی ثبت کردید.",
        icon_key="badge_communicator",
        is_seasonal=False,
        predicate=_has_50_activities,
    ),
    BadgeRule(
        code="rising_star",
        name_en="Rising Star",
        name_fa="ستاره‌ی در حال طلوع",
        description_en="Reached level 5.",
        description_fa="به سطح ۵ رسیدید.",
        icon_key="badge_rising_star",
        is_seasonal=False,
        predicate=_is_rising_star,
    ),
]

BADGE_RULES_BY_CODE: dict[str, BadgeRule] = {rule.code: rule for rule in BADGE_RULES}


def sync_badge_catalog(db: Session) -> None:
    """Idempotent upsert of BADGE_RULES into the `badges` table. Called
    once at app startup (see app/main.py), the same spirit as
    Base.metadata.create_all for the SQLite dev path -- the catalog
    lives in code (reviewed/deployed like any other logic, per the same
    reasoning as app/billing/plans.py) but UserBadge still needs a real
    foreign key to point at, hence the mirrored table."""
    existing = {b.code: b for b in db.query(Badge).all()}
    changed = False
    for rule in BADGE_RULES:
        row = existing.get(rule.code)
        if row is None:
            db.add(
                Badge(
                    code=rule.code,
                    name_en=rule.name_en,
                    name_fa=rule.name_fa,
                    description_en=rule.description_en,
                    description_fa=rule.description_fa,
                    icon_key=rule.icon_key,
                    is_seasonal=rule.is_seasonal,
                )
            )
            changed = True
        else:
            for field in ("name_en", "name_fa", "description_en", "description_fa", "icon_key", "is_seasonal"):
                if getattr(row, field) != getattr(rule, field):
                    setattr(row, field, getattr(rule, field))
                    changed = True
    if changed:
        db.commit()
