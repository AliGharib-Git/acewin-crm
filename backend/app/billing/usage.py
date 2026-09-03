"""
UsageService: computes how much of each metered resource an
organization is ACTUALLY using right now, always live from real rows
-- never a separately-maintained counter that could drift from
reality. Cheap enough at this scale (COUNT queries on indexed
organization_id columns) that caching isn't worth the staleness risk
yet; if usage checks ever show up in profiling, memoize per-request
(not longer -- a stale "you're under the limit" is a real correctness
bug, not just a UX nit).
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AgentActionLog, Company, Contact, Deal, Organization, User

# Metrics with a real, live count. "storage_mb" appears in plan limits
# (see plans.py) but has NO implementation here: there is no file
# attachment / upload feature in this codebase yet (see product spec
# section on Data Migration / Attachments as future work), so reporting
# a fabricated storage number would violate "no fake production
# claims". compute_usage() below intentionally omits it; a caller that
# checks storage_mb before that feature exists will get a clear
# NotImplementedError rather than a silently-wrong "0 MB used".
_COUNTED_METRICS = {"users", "contacts", "companies", "deals", "ai_requests_per_month"}


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def current_usage(db: Session, org: Organization, metric: str) -> int:
    if metric not in _COUNTED_METRICS:
        raise NotImplementedError(
            f"Usage metric '{metric}' has no real counter implemented yet -- "
            "see app/billing/usage.py before enforcing a limit on it."
        )

    if metric == "users":
        return db.query(User).filter(User.organization_id == org.id).count()
    if metric == "contacts":
        return db.query(Contact).filter(Contact.organization_id == org.id).count()
    if metric == "companies":
        return db.query(Company).filter(Company.organization_id == org.id).count()
    if metric == "deals":
        return db.query(Deal).filter(Deal.organization_id == org.id).count()
    if metric == "ai_requests_per_month":
        now = datetime.now(timezone.utc)
        return (
            db.query(AgentActionLog)
            .filter(
                AgentActionLog.organization_id == org.id,
                AgentActionLog.source == "copilot",
                AgentActionLog.created_at >= _month_start(now),
            )
            .count()
        )
    raise AssertionError("unreachable -- _COUNTED_METRICS and this branch have drifted apart")


def usage_snapshot(db: Session, org: Organization) -> dict[str, int]:
    """Every counted metric at once, e.g. for a usage dashboard widget."""
    return {metric: current_usage(db, org, metric) for metric in sorted(_COUNTED_METRICS)}
