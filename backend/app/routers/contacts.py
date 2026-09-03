from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_permission, enforce_within_limit, get_current_org, get_current_user
from app.models import AgentActionStatus, Company, Contact, ContactPriority, ContactStatus, Deal, Organization, Tag, User
from app.schemas import ContactCreate, ContactListItem, ContactOut, ContactUpdate, EngagementOut, Page
from app.scoring.engine import compute_engagement
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

# Highest-priority-first ordering for the `sort=priority` option below --
# SQL sorts enums alphabetically by default (high, low, medium), which
# isn't the order a rep actually wants ("show me who matters most
# first"), so this CASE expression maps each value to its rank instead.
_PRIORITY_RANK = case(
    (Contact.priority == ContactPriority.high, 0),
    (Contact.priority == ContactPriority.medium, 1),
    (Contact.priority == ContactPriority.low, 2),
    else_=1,
)


def _base_query(db: Session, org: Organization):
    return scoped(db, Contact, org).options(
        joinedload(Contact.company),
        joinedload(Contact.assigned_to),
        selectinload(Contact.tags),
        # Selectinload (a separate query), not joinedload, for these three
        # -- joining three collections onto Contact at once would multiply
        # rows into a cartesian product. Needed eagerly here (rather than
        # left lazy) because compute_engagement() below reads all three
        # for every contact on the page.
        selectinload(Contact.activities),
        selectinload(Contact.deals).joinedload(Deal.stage),
        selectinload(Contact.tasks),
    )


def _validate_refs(db: Session, org: Organization, company_id: int | None, assigned_to_id: int | None) -> None:
    """company_id and assigned_to_id are client-supplied foreign keys into
    other tenant-owned tables (Company, User). Left unchecked, a caller
    could point a contact at another organization's company/user id and
    have that company_name / assigned_to leak back out through
    ContactOut -- the same cross-tenant leak app/tenancy.py warns about,
    just reached through an FK instead of a path param."""
    if company_id is not None:
        get_or_404(db, Company, company_id, org, detail="Invalid company")
    if assigned_to_id is not None:
        get_or_404(db, User, assigned_to_id, org, detail="Invalid assigned_to_id")


def _engagement_out(contact: Contact) -> EngagementOut:
    return EngagementOut(**compute_engagement(contact).__dict__)


def _to_list_item(contact: Contact) -> ContactListItem:
    item = ContactListItem.model_validate(contact)
    item.company_name = contact.company.name if contact.company else None
    item.engagement = _engagement_out(contact)
    return item


def _to_detail(contact: Contact) -> ContactOut:
    item = ContactOut.model_validate(contact)
    item.company_name = contact.company.name if contact.company else None
    item.engagement = _engagement_out(contact)
    return item


@router.get("", response_model=Page)
def list_contacts(
    search: str | None = None,
    status: ContactStatus | None = None,
    priority: ContactPriority | None = None,
    tag_id: int | None = None,
    company_id: int | None = None,
    sort: str | None = Query(
        None, description="'priority' to show the highest-priority contacts first, then most recently updated."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    query = _base_query(db, org)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Contact.first_name.ilike(like), Contact.last_name.ilike(like), Contact.email.ilike(like))
        )
    if status:
        query = query.filter(Contact.status == status)
    if priority:
        query = query.filter(Contact.priority == priority)
    if company_id:
        query = query.filter(Contact.company_id == company_id)
    if tag_id:
        query = query.filter(Contact.tags.any(Tag.id == tag_id))

    total = query.distinct().count()
    if sort == "priority":
        query = query.order_by(_PRIORITY_RANK, Contact.updated_at.desc())
    else:
        query = query.order_by(Contact.updated_at.desc())
    contacts = query.offset((page - 1) * page_size).limit(page_size).all()
    return Page(items=[_to_list_item(c) for c in contacts], total=total, page=page, page_size=page_size)


@router.post("", response_model=ContactOut, status_code=201)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_permission(db, current_user, "contacts:create")
    enforce_within_limit(db, org, "contacts")
    _validate_refs(db, org, payload.company_id, payload.assigned_to_id)
    data = payload.model_dump(exclude={"tag_ids"})
    contact = Contact(**data, organization_id=org.id)
    if payload.tag_ids:
        # Tags must belong to the same tenant -- filtering by org here
        # (not just id) means a tag_id borrowed from another
        # organization is silently dropped rather than attached.
        contact.tags = scoped(db, Tag, org).filter(Tag.id.in_(payload.tag_ids)).all()
    db.add(contact)
    db.commit()
    db.refresh(contact)
    record_action(
        db, current_user, "contacts:create", source="api", status=AgentActionStatus.success,
        arguments=data, entity_type="contact", entity_id=contact.id, organization_id=org.id,
    )
    return _to_detail(contact)


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    contact = _base_query(db, org).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _to_detail(contact)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    contact = get_or_404(db, Contact, contact_id, org, detail="Contact not found")
    enforce_permission(db, current_user, "contacts:update", {"contact_id": contact_id})
    data = payload.model_dump(exclude_unset=True, exclude={"tag_ids"})
    _validate_refs(db, org, data.get("company_id"), data.get("assigned_to_id"))
    for field, value in data.items():
        setattr(contact, field, value)
    if payload.tag_ids is not None:
        contact.tags = scoped(db, Tag, org).filter(Tag.id.in_(payload.tag_ids)).all()
    db.commit()
    db.refresh(contact)
    record_action(
        db, current_user, "contacts:update", source="api", status=AgentActionStatus.success,
        arguments={"contact_id": contact_id, **data}, entity_type="contact", entity_id=contact.id, organization_id=org.id,
    )
    return _to_detail(contact)


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    contact = get_or_404(db, Contact, contact_id, org, detail="Contact not found")
    enforce_permission(db, current_user, "contacts:delete", {"contact_id": contact_id})
    db.delete(contact)
    db.commit()
    record_action(
        db, current_user, "contacts:delete", source="api", status=AgentActionStatus.success,
        arguments={"contact_id": contact_id}, entity_type="contact", entity_id=contact_id, organization_id=org.id,
    )
    return None
