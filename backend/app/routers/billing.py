"""
Billing & Subscription API.

/plans is public (no auth) since a pricing page needs to render before
anyone logs in. Everything else requires an authenticated org context.
Plan changes are admin-only and, since no payment provider is wired up
(see app/billing/provider.py), take effect immediately with no payment
collected -- this is the honest current behavior, not a placeholder
hidden behind a fake checkout flow.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.billing import plans as plan_defs
from app.billing import usage as usage_service
from app.billing.entitlements import effective_limit
from app.billing.subscription_service import change_plan, effective_plan, get_or_create, is_trial_expired
from app.database import get_db
from app.deps import get_current_admin, get_current_org, get_current_user
from app.models import Organization, User
from app.schemas import PlanChangeRequest, PlanOut, SubscriptionOut, UsageMetricOut
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _plan_out(definition, current_plan) -> PlanOut:
    return PlanOut(
        plan=definition.plan.value,
        name=definition.name_en,
        tagline=definition.tagline_en,
        monthly_price_toman=definition.monthly_price_toman,
        yearly_price_toman=definition.yearly_price_toman,
        is_custom_pricing=definition.monthly_price_toman is None,
        is_coming_soon=definition.coming_soon,
        features=sorted(definition.features),
        limits=definition.limits,
        is_current=(current_plan is not None and definition.plan == current_plan),
    )


@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    """Public pricing-page data: every plan's price, features, and
    limits. Deliberately has no auth dependency so a logged-out visitor
    can see pricing; `is_current` will just always be False for them."""
    return [_plan_out(plan_defs.PLAN_DEFINITIONS[p], None) for p in plan_defs.PLAN_ORDER]


@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    subscription = get_or_create(db, org)
    plan = effective_plan(subscription)
    usage_rows = []
    for metric in plan_defs.PLAN_DEFINITIONS[plan].limits:
        limit = effective_limit(subscription, plan, metric)  # respects a Platform Admin override, if any
        try:
            current = usage_service.current_usage(db, org, metric)
        except NotImplementedError:
            continue  # metric has no real counter yet (e.g. storage_mb) -- omit rather than fabricate
        usage_rows.append(
            UsageMetricOut(
                metric=metric,
                current=current,
                limit=limit,
                percent_used=round(current / limit * 100, 1) if limit else None,
            )
        )

    return SubscriptionOut(
        plan=subscription.plan.value,
        effective_plan=plan.value,
        status=subscription.status.value,
        billing_cycle=subscription.billing_cycle,
        trial_ends_at=subscription.trial_ends_at,
        current_period_end=subscription.current_period_end,
        is_trial_expired=is_trial_expired(subscription),
        usage=usage_rows,
    )


@router.get("/plans/compare", response_model=list[PlanOut])
def compare_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    """Same as /plans but with `is_current` correctly set -- for the
    in-app "Compare Plans" / upgrade view, as opposed to the public,
    logged-out pricing page."""
    subscription = get_or_create(db, org)
    plan = effective_plan(subscription)
    return [_plan_out(plan_defs.PLAN_DEFINITIONS[p], plan) for p in plan_defs.PLAN_ORDER]


@router.patch("/subscription", response_model=SubscriptionOut)
def change_subscription_plan(
    payload: PlanChangeRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    """Admin-only, immediate, no payment collected -- see this module's
    docstring and app/billing/provider.py for why that's the honest
    behavior until a real payment gateway is integrated."""
    target_definition = plan_defs.PLAN_DEFINITIONS[payload.plan]
    if target_definition.coming_soon:
        # Belt-and-suspenders: the pricing page never renders a switch
        # button for a coming_soon plan, but the API itself must not
        # honor one either -- a UI-only gate is not a real gate.
        raise HTTPException(
            status_code=400,
            detail=f"The {target_definition.name_en} plan isn't available yet.",
        )

    subscription = get_or_create(db, org)
    change_plan(db, subscription, payload.plan, payload.billing_cycle)
    return get_subscription(db=db, current_user=admin, org=org)
