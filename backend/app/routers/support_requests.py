"""
Support requests: the "ask the Platform Admin for anything" channel any
signed-in user (any role, any organization) can use from inside the app --
a bug report, a feature ask, a billing question, or literally anything
they need that isn't a self-service action elsewhere in the CRM.

Every request lands in two places the moment it's filed: the
`support_requests` table (read cross-tenant by the Platform Admin panel's
"Requests" tab -- see app/routers/platform_admin.py) and an admin
notification email (app/email.py). This router only ever touches the
requesting user's own organization/rows; the cross-tenant read+reply side
lives in platform_admin.py, gated the same way every other Platform Admin
route is (get_current_platform_admin).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_org, get_current_user
from app.email import send_admin_notification
from app.models import Organization, SupportRequest, User
from app.schemas import SupportRequestCreate, SupportRequestOut

router = APIRouter(prefix="/api/support-requests", tags=["support-requests"])


@router.get("", response_model=list[SupportRequestOut])
def list_my_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The current user's own requests and their status/reply, newest
    first -- deliberately scoped to `user_id`, not the whole org, since
    a request is a personal message to the Platform Admin, not a
    shared org record."""
    requests = (
        db.query(SupportRequest)
        .filter(SupportRequest.user_id == current_user.id)
        .order_by(desc(SupportRequest.created_at))
        .all()
    )
    return requests


@router.post("", response_model=SupportRequestOut, status_code=201)
def create_request(
    payload: SupportRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    request = SupportRequest(
        organization_id=org.id,
        user_id=current_user.id,
        subject=payload.subject,
        message=payload.message,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    send_admin_notification(
        subject=f"[ACEWIN] New request: {payload.subject} — {org.name}",
        body=(
            f"Organization: {org.name}\n"
            f"User: {current_user.full_name} <{current_user.email}>\n"
            f"Subject: {payload.subject}\n\n"
            f"{payload.message}\n\n"
            f"Request ID: {request.id}\n"
        ),
    )
    return request
