"""Contact engagement scoring: "how well is this lead/customer actually
being followed up on, right now" -- a number a rep can sort/scan by,
computed fresh on every read rather than stored, the same reasoning as
app/kpi/engine.py and app/okr/engine.py (code is the source of truth for
how a derived metric is computed; the DB only holds the raw facts it's
computed from). This is deliberately independent of `Contact.priority`
(see models.py:ContactPriority), which is the rep's own judgment call
on how important the contact is -- this module only measures *tending
to*, not *worth*.

Score is 0-100, built from three things a rep would actually look at:
  - recency: how long since the last logged activity (note/call/email/
    meeting) -- a lead going quiet is the single strongest "needs
    follow-up" signal.
  - volume: how much engagement has accumulated in total -- a handful
    of touches read as more "worked" than a single note.
  - pipeline weight: whether there's real money attached (open deals),
    since a well-engaged lead with a large open deal is a different
    priority than one with none.

Not folded in: `Contact.priority` and `Contact.status`, both already
surfaced separately (see app/routers/contacts.py) -- mixing a
rep-assigned value judgment into a "how tended-to" score would make
neither one legible on its own.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from app.models import Contact, TaskStatus


@dataclass
class EngagementResult:
    score: int  # 0-100
    label: str  # "low" | "medium" | "high"
    total_activities: int
    last_activity_at: datetime | None
    days_since_last_activity: int | None
    open_deal_count: int
    open_deal_value: float
    open_task_count: int


def _recency_points(last_activity_at: datetime | None) -> tuple[int, int | None]:
    if last_activity_at is None:
        return 0, None
    now = datetime.now(timezone.utc)
    reference = last_activity_at if last_activity_at.tzinfo else last_activity_at.replace(tzinfo=timezone.utc)
    days = max((now - reference).days, 0)
    if days <= 3:
        return 40, days
    if days <= 7:
        return 28, days
    if days <= 30:
        return 14, days
    return 0, days


def _volume_points(total_activities: int) -> int:
    return min(total_activities * 5, 30)


def _pipeline_points(open_deal_count: int, open_deal_value: float) -> int:
    if open_deal_count == 0:
        return 0
    points = 12  # having at least one open deal at all is worth more than its size
    if open_deal_value >= 500_000_000:  # value is stored in Rials (Numeric(14,2)) -- see Deal.value
        points += 18
    elif open_deal_value >= 100_000_000:
        points += 12
    elif open_deal_value > 0:
        points += 6
    return min(points, 30)


def _label_for(score: int) -> str:
    if score >= 65:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def compute_engagement(contact: Contact) -> EngagementResult:
    """Reads the already-loaded `activities`/`deals`/`tasks` relationships
    off a Contact instance -- callers that need this for a whole page of
    contacts should eager-load those the same way app/routers/contacts.py
    already eager-loads company/assigned_to/tags, to avoid N+1 queries."""
    activities = contact.activities or []
    total_activities = len(activities)
    last_activity_at = activities[0].created_at if activities else None  # relationship is ordered desc

    open_deals = [d for d in (contact.deals or []) if d.stage is not None and not d.stage.is_won and not d.stage.is_lost]
    open_deal_value = float(sum(d.value for d in open_deals))
    open_task_count = len([t for t in (contact.tasks or []) if t.status == TaskStatus.pending])

    recency_pts, days_since = _recency_points(last_activity_at)
    score = recency_pts + _volume_points(total_activities) + _pipeline_points(len(open_deals), open_deal_value)
    score = max(0, min(score, 100))

    return EngagementResult(
        score=score,
        label=_label_for(score),
        total_activities=total_activities,
        last_activity_at=last_activity_at,
        days_since_last_activity=days_since,
        open_deal_count=len(open_deals),
        open_deal_value=open_deal_value,
        open_task_count=open_task_count,
    )
