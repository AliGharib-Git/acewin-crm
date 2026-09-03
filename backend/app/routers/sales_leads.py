"""
Sales leads: the "Contact sales" request filed from the Pricing page's
VIP / Enterprise plan card (see frontend src/pages/Pricing.tsx). VIP is
custom/contact-sales pricing now (app/billing/plans.py), not a self-serve
checkout, so this is what clicking that plan's CTA actually does: file a
real, trackable lead that reaches the sales team, instead of opening a
bare mailto: link the platform has no record of.

Deliberately public (no get_current_user/get_current_org dependency,
like app/routers/feedback.py) since a logged-out visitor can be on the
Pricing page too. If a valid bearer token IS present, though, we quietly
attach the caller's own user/organization -- same spirit as
app/routers/support_requests.py -- so the sales team sees who they're
actually talking to instead of treating every lead as a cold one. An
invalid, missing, or expired token here is never an error; it just means
an anonymous lead.

Same two-destinations design as SupportRequest/PublicFeedback: lands in
the `sales_leads` table (read cross-tenant in the Platform Admin panel's
Requests tab -- see app/routers/platform_admin.py) and triggers an admin
notification email (app/email.py) the moment it's filed.
"""
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.email import send_admin_notification
from app.models import SalesLead, User
from app.schemas import SalesLeadCreate, SalesLeadOut
from app.security import decode_access_token

router = APIRouter(prefix="/api/sales-leads", tags=["sales-leads"])

_bearer = HTTPBearer(auto_error=False)


def _optional_caller(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Best-effort identify the caller without ever raising -- this
    endpoint must stay usable from the logged-out Pricing page, so a
    missing/invalid/expired token just means an anonymous lead, never a
    401."""
    if credentials is None:
        return None
    email = decode_access_token(credentials.credentials)
    if email is None:
        return None
    return db.query(User).filter(User.email == email).first()


@router.post("", response_model=SalesLeadOut, status_code=201)
def create_sales_lead(
    payload: SalesLeadCreate,
    db: Session = Depends(get_db),
    caller: User | None = Depends(_optional_caller),
):
    lead = SalesLead(
        organization_id=caller.organization_id if caller else None,
        user_id=caller.id if caller else None,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        company_name=payload.company_name,
        message=payload.message,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    caller_line = (
        f"Signed in as: {caller.full_name} <{caller.email}> (org #{caller.organization_id})\n"
        if caller
        else "Not signed in (anonymous visitor)\n"
    )
    send_admin_notification(
        subject=f"[ACEWIN] New VIP sales lead — {payload.contact_name}",
        body=(
            f"Contact: {payload.contact_name} <{payload.contact_email}>\n"
            f"Phone: {payload.contact_phone or '-'}\n"
            f"Company: {payload.company_name or '-'}\n"
            f"{caller_line}\n"
            f"{payload.message or '(no message)'}\n\n"
            f"Lead ID: {lead.id}\n"
        ),
    )
    return lead
