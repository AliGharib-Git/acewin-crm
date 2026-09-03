"""
EntitlementService: the ONE place a router asks "is this org allowed to
do X". Routers must never write `if org.plan == "pro":` themselves
(see product spec section 8) -- they call `require_feature()` /
`require_within_limit()` here, which resolves the org's *effective*
plan (respecting trial expiry -- see subscription_service.effective_plan)
against app/billing/plans.py, and raises a structured, upgrade-aware
error if it's not allowed. The frontend is expected to only ever
reflect what these checks already decided, never make the decision
itself (section 8: "Frontend should only reflect backend authorization").
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.billing import plans, usage
from app.billing.subscription_service import effective_plan, get_or_create
from app.models import Organization


def _limit_response(code: str, message: str, **details) -> dict:
    # Mirrors the structured-error shape from the product spec (section
    # 34): { code, message, details }. Carried as HTTPException.detail
    # rather than a top-level {"success": false, "error": {...}} envelope
    # since that would require a conversation-wide exception-handler
    # change (out of scope for this phase) -- every field the spec asks
    # for is still present, just nested under FastAPI's own "detail" key.
    return {"code": code, "message": message, "details": details}


def effective_has_feature(subscription, plan, feature_code: str) -> bool:
    """Same question as plans.has_feature, but checks a Platform Admin's
    per-tenant override (see Subscription.feature_overrides) first. An
    override always wins over the plan, in either direction -- it can
    grant a feature the plan doesn't include, or revoke one it does."""
    override = subscription.feature_overrides.get(feature_code)
    if override is not None:
        return override
    return plans.has_feature(plan, feature_code)


def effective_limit(subscription, plan, metric: str) -> int | None:
    """Same question as plans.get_limit, but checks a Platform Admin's
    per-tenant override (see Subscription.limit_overrides) first."""
    if metric in subscription.limit_overrides:
        return subscription.limit_overrides[metric]
    return plans.get_limit(plan, metric)


def require_feature(db: Session, org: Organization, feature_code: str) -> None:
    subscription = get_or_create(db, org)
    plan = effective_plan(subscription)
    if effective_has_feature(subscription, plan, feature_code):
        return

    # Find the cheapest plan that *would* unlock this, for a useful
    # upgrade prompt instead of a bare "no".
    unlocking_plan = next((p for p in plans.PLAN_ORDER if plans.has_feature(p, feature_code)), None)

    raise HTTPException(
        status_code=402,  # Payment Required -- distinct from 403 (forbidden regardless of plan)
        detail=_limit_response(
            "FEATURE_NOT_AVAILABLE",
            f"'{feature_code}' is not available on the {plan.value} plan.",
            feature_code=feature_code,
            current_plan=plan.value,
            upgrade_to=unlocking_plan.value if unlocking_plan else None,
        ),
    )


def require_within_limit(db: Session, org: Organization, metric: str, increment: int = 1) -> None:
    """Call BEFORE creating the record(s) that would push usage over the
    limit -- i.e. "would this org still be within its limit after this
    write", not "is it within limit right now". `increment` lets a bulk
    import check "can N more contacts fit" in one call."""
    subscription = get_or_create(db, org)
    plan = effective_plan(subscription)
    limit = effective_limit(subscription, plan, metric)
    if limit is None:  # unlimited on this plan (or explicitly overridden to unlimited)
        return

    current = usage.current_usage(db, org, metric)
    if current + increment <= limit:
        return

    unlocking_plan = next(
        (p for p in plans.PLAN_ORDER if (plans.get_limit(p, metric) is None or plans.get_limit(p, metric) >= current + increment)),
        None,
    )

    raise HTTPException(
        status_code=402,
        detail=_limit_response(
            "USAGE_LIMIT_REACHED",
            f"This would exceed your plan's {metric} limit ({current}/{limit} used).",
            metric=metric,
            current_usage=current,
            limit=limit,
            percent_used=round(current / limit * 100, 1) if limit else 100.0,
            current_plan=plan.value,
            upgrade_to=unlocking_plan.value if unlocking_plan else None,
        ),
    )
