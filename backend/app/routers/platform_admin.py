"""
Platform Admin API: cross-tenant management for the one operator
account(s) listed in PLATFORM_ADMIN_EMAILS (see app/config.py and
app/deps.py:get_current_platform_admin) -- deliberately separate from
UserRole.admin, which is scoped to a single organization like every
other tenant-owned concept in this app.

Every route here is gated by get_current_platform_admin and, unlike
every other router in this codebase, intentionally does NOT depend on
get_current_org -- a Platform Admin's whole job is reaching *across*
tenants, which get_current_org exists specifically to prevent for
ordinary requests. The org to act on is always taken from the URL path
(`org_id`), never inferred from the caller's own membership.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.billing import plans as plan_defs
from app.billing import usage as usage_service
from app.billing.subscription_service import approve_trial as approve_trial_service
from app.billing.subscription_service import effective_plan, get_or_create, is_trial_expired
from app.database import get_db
from app.deps import get_current_platform_admin
from app.models import (
    AgentActionLog,
    Organization,
    PublicFeedback,
    SalesLead,
    SubscriptionStatus,
    SupportRequest,
    SupportRequestStatus,
    User,
)
from app.schemas import (
    OrgFeatureOverridesUpdate,
    OrgLimitOverridesUpdate,
    OrgStatusUpdate,
    OrgSubscriptionAdminUpdate,
    PlatformAgentActionLogOut,
    PlatformOrganizationDetailOut,
    PlatformOrganizationOut,
    Page,
    PublicFeedbackAdminOut,
    PublicFeedbackAdminUpdate,
    SalesLeadAdminOut,
    SalesLeadAdminUpdate,
    SupportRequestAdminOut,
    SupportRequestAdminUpdate,
)

router = APIRouter(
    prefix="/api/platform-admin",
    tags=["platform-admin"],
    dependencies=[Depends(get_current_platform_admin)],
)


def _get_org_or_404(db: Session, org_id: int) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _org_out(db: Session, org: Organization) -> PlatformOrganizationOut:
    subscription = get_or_create(db, org)
    plan = effective_plan(subscription)
    user_count = db.query(User).filter(User.organization_id == org.id).count()
    return PlatformOrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        created_at=org.created_at,
        user_count=user_count,
        plan=subscription.plan.value,
        effective_plan=plan.value,
        status=subscription.status.value,
        trial_ends_at=subscription.trial_ends_at,
        is_trial_expired=is_trial_expired(subscription),
        limit_overrides=subscription.limit_overrides,
        feature_overrides=subscription.feature_overrides,
    )


@router.get("/organizations", response_model=list[PlatformOrganizationOut])
def list_organizations(db: Session = Depends(get_db)):
    """Every tenant in the system, newest first -- the Platform Admin's
    main triage view."""
    orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()
    return [_org_out(db, org) for org in orgs]


@router.get("/organizations/{org_id}", response_model=PlatformOrganizationDetailOut)
def get_organization(org_id: int, db: Session = Depends(get_db)):
    org = _get_org_or_404(db, org_id)
    subscription = get_or_create(db, org)
    plan = effective_plan(subscription)
    base = _org_out(db, org)

    usage_rows = []
    for metric, limit in plan_defs.PLAN_DEFINITIONS[plan].limits.items():
        effective = subscription.limit_overrides.get(metric, limit)
        try:
            current = usage_service.current_usage(db, org, metric)
        except NotImplementedError:
            continue
        usage_rows.append(
            {
                "metric": metric,
                "current": current,
                "limit": effective,
                "percent_used": round(current / effective * 100, 1) if effective else None,
            }
        )

    all_features = sorted({f for definition in plan_defs.PLAN_DEFINITIONS.values() for f in definition.features})

    return PlatformOrganizationDetailOut(**base.model_dump(), usage=usage_rows, available_features=all_features)


@router.patch("/organizations/{org_id}/status", response_model=PlatformOrganizationOut)
def update_organization_status(org_id: int, payload: OrgStatusUpdate, db: Session = Depends(get_db)):
    """Enable/disable an organization's access outright. A disabled org's
    users are refused at get_current_org (see app/deps.py) on their very
    next request regardless of plan/subscription -- this is a hard kill
    switch, above and beyond entitlements."""
    org = _get_org_or_404(db, org_id)
    org.is_active = payload.is_active
    db.commit()
    db.refresh(org)
    return _org_out(db, org)


@router.patch("/organizations/{org_id}/subscription", response_model=PlatformOrganizationOut)
def update_organization_subscription(org_id: int, payload: OrgSubscriptionAdminUpdate, db: Session = Depends(get_db)):
    """Direct subscription edit -- plan, status, billing cycle, trial
    end -- with no restrictions on target plan, including any plan
    still marked `coming_soon` on the public pricing page: a Platform
    Admin hand-picking an early customer is exactly the case that flag
    isn't meant to block."""
    org = _get_org_or_404(db, org_id)
    subscription = get_or_create(db, org)

    if payload.plan is not None:
        subscription.plan = payload.plan
    if payload.status is not None:
        subscription.status = payload.status
    if payload.billing_cycle is not None:
        subscription.billing_cycle = payload.billing_cycle
    if payload.clear_trial_end:
        subscription.trial_ends_at = None
    elif payload.trial_ends_at is not None:
        subscription.trial_ends_at = payload.trial_ends_at

    db.commit()
    db.refresh(subscription)
    return _org_out(db, org)


@router.post("/organizations/{org_id}/subscription/approve-trial", response_model=PlatformOrganizationOut)
def approve_organization_trial(org_id: int, db: Session = Depends(get_db)):
    """Approve a `pending_trial` org's request and start its 14-day
    Basic trial from right now (see subscription_service.approve_trial).
    A Platform Admin who wants something other than the standard 14
    days -- a shorter trial, or skipping straight to a paid plan -- can
    still use PATCH .../subscription directly instead; this endpoint is
    just the one-click "yes, start their trial" action for the common
    case that email notification points them at."""
    org = _get_org_or_404(db, org_id)
    subscription = get_or_create(db, org)
    if subscription.status != SubscriptionStatus.pending_trial:
        raise HTTPException(
            status_code=400,
            detail="This organization has no pending trial request to approve.",
        )
    approve_trial_service(db, subscription)
    return _org_out(db, org)


@router.patch("/organizations/{org_id}/limits", response_model=PlatformOrganizationOut)
def update_organization_limits(org_id: int, payload: OrgLimitOverridesUpdate, db: Session = Depends(get_db)):
    """Full replace of this org's numeric limit overrides -- e.g. give
    one company's Copilot a custom `ai_requests_per_month` quota above
    or below what its plan alone would allow. See app/billing/
    entitlements.py:effective_limit for how this is consulted."""
    org = _get_org_or_404(db, org_id)
    subscription = get_or_create(db, org)

    known_metrics = set(plan_defs.PLAN_DEFINITIONS[subscription.plan].limits.keys())
    unknown = set(payload.overrides) - known_metrics
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown metric(s): {', '.join(sorted(unknown))}")

    subscription.limit_overrides = payload.overrides
    db.commit()
    db.refresh(subscription)
    return _org_out(db, org)


@router.patch("/organizations/{org_id}/features", response_model=PlatformOrganizationOut)
def update_organization_features(org_id: int, payload: OrgFeatureOverridesUpdate, db: Session = Depends(get_db)):
    """Full replace of this org's feature overrides -- force-grant a
    feature its plan doesn't include, or force-revoke one it does. See
    app/billing/entitlements.py:effective_has_feature."""
    org = _get_org_or_404(db, org_id)
    subscription = get_or_create(db, org)

    all_features = {f for definition in plan_defs.PLAN_DEFINITIONS.values() for f in definition.features}
    unknown = set(payload.overrides) - all_features
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown feature code(s): {', '.join(sorted(unknown))}")

    subscription.feature_overrides = payload.overrides
    db.commit()
    db.refresh(subscription)
    return _org_out(db, org)


# --- Requests tab: support requests + cross-tenant action feed --------


def _support_request_out(request: SupportRequest) -> SupportRequestAdminOut:
    return SupportRequestAdminOut(
        id=request.id,
        subject=request.subject,
        message=request.message,
        status=request.status.value,
        admin_reply=request.admin_reply,
        created_at=request.created_at,
        resolved_at=request.resolved_at,
        organization_id=request.organization_id,
        organization_name=request.organization.name if request.organization else f"org #{request.organization_id}",
        user_name=request.user.full_name if request.user else "-",
        user_email=request.user.email if request.user else "-",
    )


@router.get("/requests", response_model=list[SupportRequestAdminOut])
def list_requests(
    status: str | None = Query(None, description="Filter by 'open', 'in_progress', or 'resolved'."),
    db: Session = Depends(get_db),
):
    """Every support request across every tenant, newest first -- the
    manual half of the Requests tab (see list_actions below for the
    automatic half: every meaningful action any user took)."""
    query = db.query(SupportRequest)
    if status:
        query = query.filter(SupportRequest.status == SupportRequestStatus(status))
    requests = query.order_by(desc(SupportRequest.created_at)).all()
    return [_support_request_out(r) for r in requests]


@router.patch("/requests/{request_id}", response_model=SupportRequestAdminOut)
def update_request(request_id: int, payload: SupportRequestAdminUpdate, db: Session = Depends(get_db)):
    """A Platform Admin replying to and/or resolving one request. Setting
    status to 'resolved' stamps resolved_at automatically; moving off
    'resolved' back to 'open'/'in_progress' clears it, so the timestamp
    always reflects the most recent resolution rather than the first."""
    request = db.query(SupportRequest).filter(SupportRequest.id == request_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    if payload.admin_reply is not None:
        request.admin_reply = payload.admin_reply
    if payload.status is not None:
        new_status = SupportRequestStatus(payload.status)
        request.status = new_status
        request.resolved_at = datetime.now(timezone.utc) if new_status == SupportRequestStatus.resolved else None

    db.commit()
    db.refresh(request)
    return _support_request_out(request)


# --- Requests tab: public homepage feedback (comments/complaints) -----


def _feedback_out(feedback: PublicFeedback) -> PublicFeedbackAdminOut:
    return PublicFeedbackAdminOut(
        id=feedback.id,
        name=feedback.name,
        email=feedback.email,
        category=feedback.category.value,
        message=feedback.message,
        status=feedback.status.value,
        admin_reply=feedback.admin_reply,
        created_at=feedback.created_at,
        resolved_at=feedback.resolved_at,
    )


@router.get("/feedback", response_model=list[PublicFeedbackAdminOut])
def list_feedback(
    status: str | None = Query(None, description="Filter by 'open', 'in_progress', or 'resolved'."),
    db: Session = Depends(get_db),
):
    """Every comment/complaint filed from the public homepage, newest
    first -- the anonymous-visitor sibling of list_requests above (see
    app/routers/feedback.py for where these come from)."""
    query = db.query(PublicFeedback)
    if status:
        query = query.filter(PublicFeedback.status == SupportRequestStatus(status))
    items = query.order_by(desc(PublicFeedback.created_at)).all()
    return [_feedback_out(f) for f in items]


@router.patch("/feedback/{feedback_id}", response_model=PublicFeedbackAdminOut)
def update_feedback(feedback_id: int, payload: PublicFeedbackAdminUpdate, db: Session = Depends(get_db)):
    """A Platform Admin replying to and/or resolving one piece of public
    feedback. Same resolved_at semantics as update_request above."""
    feedback = db.query(PublicFeedback).filter(PublicFeedback.id == feedback_id).first()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if payload.admin_reply is not None:
        feedback.admin_reply = payload.admin_reply
    if payload.status is not None:
        new_status = SupportRequestStatus(payload.status)
        feedback.status = new_status
        feedback.resolved_at = datetime.now(timezone.utc) if new_status == SupportRequestStatus.resolved else None

    db.commit()
    db.refresh(feedback)
    return _feedback_out(feedback)


# --- Requests tab: VIP "Contact sales" leads from the Pricing page ----


def _sales_lead_out(lead: SalesLead) -> SalesLeadAdminOut:
    return SalesLeadAdminOut(
        id=lead.id,
        contact_name=lead.contact_name,
        contact_email=lead.contact_email,
        contact_phone=lead.contact_phone,
        company_name=lead.company_name,
        message=lead.message,
        status=lead.status.value,
        admin_reply=lead.admin_reply,
        created_at=lead.created_at,
        resolved_at=lead.resolved_at,
        organization_id=lead.organization_id,
        organization_name=lead.organization.name if lead.organization else None,
        user_name=lead.user.full_name if lead.user else None,
        user_email=lead.user.email if lead.user else None,
    )


@router.get("/sales-leads", response_model=list[SalesLeadAdminOut])
def list_sales_leads(
    status: str | None = Query(None, description="Filter by 'open', 'in_progress', or 'resolved'."),
    db: Session = Depends(get_db),
):
    """Every VIP "Contact sales" lead filed from the Pricing page, newest
    first, across both signed-in admins and anonymous visitors (see
    app/routers/sales_leads.py) -- the sales-team sibling of
    list_requests/list_feedback above."""
    query = db.query(SalesLead)
    if status:
        query = query.filter(SalesLead.status == SupportRequestStatus(status))
    leads = query.order_by(desc(SalesLead.created_at)).all()
    return [_sales_lead_out(lead) for lead in leads]


@router.patch("/sales-leads/{lead_id}", response_model=SalesLeadAdminOut)
def update_sales_lead(lead_id: int, payload: SalesLeadAdminUpdate, db: Session = Depends(get_db)):
    """A Platform Admin (or whoever on the sales team follows up) marking
    a lead in progress/resolved and/or leaving a note. Same resolved_at
    semantics as update_request/update_feedback above."""
    lead = db.query(SalesLead).filter(SalesLead.id == lead_id).first()
    if lead is None:
        raise HTTPException(status_code=404, detail="Sales lead not found")

    if payload.admin_reply is not None:
        lead.admin_reply = payload.admin_reply
    if payload.status is not None:
        new_status = SupportRequestStatus(payload.status)
        lead.status = new_status
        lead.resolved_at = datetime.now(timezone.utc) if new_status == SupportRequestStatus.resolved else None

    db.commit()
    db.refresh(lead)
    return _sales_lead_out(lead)


@router.get("/actions", response_model=Page)
def list_actions(
    organization_id: int | None = None,
    source: str | None = Query(None, description="Filter by 'api' or 'copilot'."),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """The automatic half of the Requests tab: every meaningful action
    (every write, human or Copilot) any user in any organization took --
    the same AgentActionLog rows app/audit.py:record_action writes and
    app/routers/agent_actions.py exposes per-tenant, here read across
    every tenant at once for the Platform Admin's own "whoever signs up
    and does anything, I can see it" view."""
    query = db.query(AgentActionLog)
    if organization_id is not None:
        query = query.filter(AgentActionLog.organization_id == organization_id)
    if source:
        query = query.filter(AgentActionLog.source == source)

    total = query.count()
    logs = query.order_by(desc(AgentActionLog.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    org_names = {org.id: org.name for org in db.query(Organization.id, Organization.name).all()}
    items = [
        PlatformAgentActionLogOut(
            id=log.id,
            tool_name=log.tool_name,
            source=log.source,
            status=log.status.value,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            organization_id=log.organization_id,
            organization_name=org_names.get(log.organization_id, f"org #{log.organization_id}"),
            user_name=log.user.full_name if log.user else None,
            created_at=log.created_at,
        )
        for log in logs
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)
