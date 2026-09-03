from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_org, get_current_user
from app.gamification import engine as gamification_engine
from app.models import Activity, ActivityType, Contact, Deal, Organization, PointSourceType, User
from app.schemas import ActivityCreate, ActivityOut
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/activities", tags=["activities"])

# Point-worthy activity types per the R&D doc's source table -- a bare
# "note" or an automatic "status_change" entry doesn't represent real
# outbound engagement the way a logged call or meeting does.
_POINT_WORTHY_TYPES = {ActivityType.call, ActivityType.meeting}
_MIN_CONTENT_LENGTH = 10
_DUPLICATE_WINDOW_MINUTES = 5


def _sync_gamification(db: Session, org: Organization, activity: Activity) -> None:
    if activity.type not in _POINT_WORTHY_TYPES:
        return
    if not activity.content or len(activity.content.strip()) < _MIN_CONTENT_LENGTH:
        return
    if not activity.created_by_id:
        return

    # Anti-abuse (section 6): the same person logging the same kind of
    # activity against the same contact/deal within a few minutes reads
    # as a duplicate/spam click, not two real touches -- skip awarding
    # (the activity itself is still saved either way).
    window_start = activity.created_at - timedelta(minutes=_DUPLICATE_WINDOW_MINUTES)
    duplicate_query = db.query(Activity.id).filter(
        Activity.organization_id == org.id,
        Activity.created_by_id == activity.created_by_id,
        Activity.type == activity.type,
        Activity.id != activity.id,
        Activity.created_at >= window_start,
        Activity.created_at < activity.created_at,
    )
    if activity.contact_id is not None:
        duplicate_query = duplicate_query.filter(Activity.contact_id == activity.contact_id)
    if activity.deal_id is not None:
        duplicate_query = duplicate_query.filter(Activity.deal_id == activity.deal_id)
    if duplicate_query.first() is not None:
        return

    user = db.query(User).filter(User.id == activity.created_by_id).first()
    if user is None:
        return
    activity_type_fa = {"call": "تماس", "meeting": "جلسه"}.get(activity.type.value, activity.type.value)
    gamification_engine.award_points(
        db, org, user, PointSourceType.activity_logged, f"activity:{activity.id}", 1,
        reason_en=f"Logged a {activity.type.value}",
        reason_fa=f"ثبت یک {activity_type_fa}",
        occurred_at=activity.created_at,
    )


@router.get("", response_model=list[ActivityOut])
def list_activities(
    contact_id: int | None = None,
    deal_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    if not contact_id and not deal_id:
        raise HTTPException(status_code=400, detail="Provide contact_id or deal_id")
    query = scoped(db, Activity, org).options(joinedload(Activity.created_by))
    if contact_id:
        query = query.filter(Activity.contact_id == contact_id)
    if deal_id:
        query = query.filter(Activity.deal_id == deal_id)
    return query.order_by(Activity.created_at.desc()).all()


@router.post("", response_model=ActivityOut, status_code=201)
def create_activity(
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    if not payload.contact_id and not payload.deal_id:
        raise HTTPException(status_code=400, detail="An activity must relate to a contact or a deal")
    # A contact_id/deal_id borrowed from another tenant must be rejected
    # up front rather than silently creating a cross-tenant-linked row.
    if payload.contact_id is not None:
        get_or_404(db, Contact, payload.contact_id, org, detail="Contact not found")
    if payload.deal_id is not None:
        get_or_404(db, Deal, payload.deal_id, org, detail="Deal not found")
    activity = Activity(**payload.model_dump(), created_by_id=current_user.id, organization_id=org.id)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    _sync_gamification(db, org, activity)
    return activity
