"""
SubscriptionService: the only code that should read or write the
Subscription table directly. Everything else (entitlement checks,
routers, the pricing page) goes through `effective_plan()` /
`get_or_create()` here rather than touching `Subscription.plan`
itself, since "which plan is this org actually on right now" is not
just `subscription.plan` -- an expired trial silently reverting to
Basic is a business rule, not a column read, and belongs in exactly
one place.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Organization, Subscription, SubscriptionPlan, SubscriptionStatus

# New organizations are offered a free 14-day trial of BASIC, and only
# Basic -- Pro and VIP are paid-from-day-one with no trial. Basic is the
# plan every org needs regardless of size (contacts/companies/deals/
# tasks), so trialing it is what actually gets a newly-registered admin
# using the product; Pro/VIP are deliberate upgrade decisions a team
# makes once it knows it needs more (higher limits, AI Actions, KPI/OKR,
# ERP, ...), not something to hand out for free during onboarding.
#
# The trial does NOT start itself at registration. A new org's
# Subscription is created `pending_trial` -- see get_or_create below --
# and only becomes `trialing` (with trial_ends_at actually set) once a
# Platform Admin reviews the signup and approves it via approve_trial().
# Registration already emails every admin in
# settings.admin_notification_email_list the moment the org is created
# (see app/routers/auth.py); approve_trial is what they call after that
# review, not something that fires on its own.
TRIAL_PLAN = SubscriptionPlan.basic
TRIAL_DAYS = 14


def get_or_create(db: Session, org: Organization) -> Subscription:
    """Every Organization must have exactly one Subscription (enforced
    by the unique constraint on organization_id) -- this creates the
    initial pending-trial request the first time it's needed rather
    than requiring every call site (routers, seed scripts, tests) to
    remember to. See approve_trial() for turning this into an actual
    running trial."""
    if org.subscription is not None:
        return org.subscription

    subscription = Subscription(
        organization_id=org.id,
        plan=TRIAL_PLAN,
        status=SubscriptionStatus.pending_trial,
        trial_ends_at=None,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def approve_trial(db: Session, subscription: Subscription) -> Subscription:
    """A Platform Admin approving a org's pending 14-day-trial request
    (see app/routers/platform_admin.py). Starts the clock from *now*,
    not from registration -- an org that waited three days for review
    still gets the full 14 days, not 11."""
    now = datetime.now(timezone.utc)
    subscription.status = SubscriptionStatus.trialing
    subscription.trial_ends_at = now + timedelta(days=TRIAL_DAYS)
    db.commit()
    db.refresh(subscription)
    return subscription


def effective_plan(subscription: Subscription) -> SubscriptionPlan:
    """The plan that should actually govern entitlement checks right
    now -- NOT necessarily `subscription.plan`. A trial that has run
    past `trial_ends_at`, or a subscription that's `past_due`/
    `canceled`, has effectively fallen back to Basic even though
    nothing has (yet) rewritten the `plan` column -- there's no billing
    cron in this codebase to do that rewrite, so this function is what
    makes an expired trial (or a lapsed Pro/VIP subscription) actually
    behave like Basic rather than silently keeping full access forever.
    Since the trial itself is always of Basic (see TRIAL_PLAN above),
    an expired Basic trial is a no-op here -- the org was already
    getting Basic-level access, it just now needs a paid subscription
    to keep it rather than trial access. A still-`pending_trial` org
    (awaiting Platform Admin approval -- see get_or_create/
    approve_trial above) behaves the same way: Basic-level access from
    the moment it registers, trial countdown or not."""
    now = datetime.now(timezone.utc)

    if subscription.status == SubscriptionStatus.trialing:
        if subscription.trial_ends_at and subscription.trial_ends_at < now:
            return SubscriptionPlan.basic
        return subscription.plan

    if subscription.status in (SubscriptionStatus.past_due, SubscriptionStatus.canceled, SubscriptionStatus.pending_trial):
        return SubscriptionPlan.basic

    return subscription.plan


def is_trial_expired(subscription: Subscription) -> bool:
    now = datetime.now(timezone.utc)
    return (
        subscription.status == SubscriptionStatus.trialing
        and subscription.trial_ends_at is not None
        and subscription.trial_ends_at < now
    )


def change_plan(db: Session, subscription: Subscription, plan: SubscriptionPlan, billing_cycle: str = "monthly") -> Subscription:
    """Admin-driven plan change with no payment collected -- see
    app/billing/provider.py's NullBillingProvider docstring for why
    that's the honest behavior right now. Ends any active trial."""
    subscription.plan = plan
    subscription.billing_cycle = billing_cycle
    subscription.status = SubscriptionStatus.active
    subscription.trial_ends_at = None
    db.commit()
    db.refresh(subscription)
    return subscription


def cancel(db: Session, subscription: Subscription) -> Subscription:
    subscription.status = SubscriptionStatus.canceled
    subscription.canceled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(subscription)
    return subscription
