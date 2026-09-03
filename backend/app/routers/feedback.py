"""Public feedback: the homepage's "Comments & complaints" form (see
frontend src/pages/Home.tsx) -- anyone visiting the marketing site can
leave a comment, complaint, or question with no account required.

Deliberately outside get_current_org/get_current_user (unlike every
other router in this codebase): a site visitor filing this may not have
signed up yet. Like app/routers/support_requests.py, every submission
lands in two places at once: the `public_feedback` table (read
cross-tenant-ly, i.e. across the whole platform, in the Platform Admin
panel's Requests tab -- see app/routers/platform_admin.py) and an admin
notification email to ali@acewin.ir / PLATFORM_ADMIN_EMAILS (app/email.py).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.email import send_admin_notification
from app.models import PublicFeedback
from app.schemas import PublicFeedbackCreate, PublicFeedbackOut

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=PublicFeedbackOut, status_code=201)
def submit_feedback(payload: PublicFeedbackCreate, db: Session = Depends(get_db)):
    feedback = PublicFeedback(
        name=payload.name,
        email=payload.email,
        category=payload.category,
        message=payload.message,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    send_admin_notification(
        subject=f"[ACEWIN] New site feedback ({payload.category.value}) — {payload.name}",
        body=(
            f"From: {payload.name} <{payload.email or 'no email given'}>\n"
            f"Category: {payload.category.value}\n\n"
            f"{payload.message}\n\n"
            f"Feedback ID: {feedback.id}\n"
        ),
    )
    return feedback
