from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_permission, enforce_within_limit, get_current_org, get_current_user
from app.gamification import engine as gamification_engine
from app.models import AgentActionStatus, CatalogItem, Company, Contact, Deal, DealItem, Organization, PipelineStage, PointSourceType, User
from app.schemas import DealCreate, DealItemInput, DealItemOut, DealOut, DealUpdate, Page
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/deals", tags=["deals"])


def _resolve_deal_items(db: Session, org: Organization, items_payload: list[DealItemInput]) -> tuple[list[DealItem], float]:
    """Turns client-supplied line items into DealItem rows with a price
    snapshot taken NOW (see DealItem's docstring for why it's a snapshot,
    not a live reference), plus their total. Raises 404 if a
    catalog_item_id doesn't belong to this org, 400 if a custom line (no
    catalog_item_id) is missing the name it needs."""
    resolved: list[DealItem] = []
    total = 0.0
    for entry in items_payload:
        if entry.catalog_item_id is not None:
            catalog_item = get_or_404(db, CatalogItem, entry.catalog_item_id, org, detail="Invalid catalog item")
            name = entry.name or catalog_item.name
            unit_price = entry.unit_price if entry.unit_price is not None else float(catalog_item.price)
        else:
            if not entry.name or not entry.name.strip():
                raise HTTPException(status_code=400, detail="A custom line item needs a name")
            name = entry.name.strip()
            unit_price = entry.unit_price or 0
        quantity = entry.quantity or 1
        resolved.append(DealItem(catalog_item_id=entry.catalog_item_id, name=name, unit_price=unit_price, quantity=quantity))
        total += unit_price * quantity
    return resolved, total


def _sync_gamification(db: Session, org: Organization, deal: Deal, was_won_before: bool, is_won_now: bool) -> None:
    """Deal-won points are credited to the deal's owner (assigned_to), not
    the user who happened to click drag-drop -- an unassigned deal can't
    be credited to anyone. Only fires on an actual Won-boundary crossing
    (see call sites), never on every edit of an already-won deal."""
    if not deal.assigned_to_id or was_won_before == is_won_now:
        return
    owner = db.query(User).filter(User.id == deal.assigned_to_id).first()
    if owner is None:
        return
    if is_won_now:
        points = gamification_engine.deal_won_points(db, org, float(deal.value or 0))
        gamification_engine.award_points(
            db, org, owner, PointSourceType.deal_won, f"deal:{deal.id}", points,
            reason_en=f'Won deal "{deal.title}"',
            reason_fa=f"بستن معامله «{deal.title}»",
            occurred_at=deal.closed_at,
        )
    else:
        gamification_engine.revoke_points_for_source(
            db, org, PointSourceType.deal_won, f"deal:{deal.id}",
            reason_en=f'Deal "{deal.title}" is no longer Won',
            reason_fa=f"معامله «{deal.title}» دیگر برد محسوب نمی‌شود",
        )


def _base_query(db: Session, org: Organization):
    return scoped(db, Deal, org).options(
        joinedload(Deal.stage), joinedload(Deal.contact), joinedload(Deal.company), joinedload(Deal.assigned_to), joinedload(Deal.items)
    )


def _validate_refs(
    db: Session, org: Organization, contact_id: int | None, company_id: int | None, assigned_to_id: int | None
) -> None:
    """contact_id, company_id and assigned_to_id are client-supplied FKs
    into other tenant-owned tables. Unvalidated, a caller could point a
    deal at another organization's contact/company/user id and have its
    name leak back out through DealOut's contact_name/company_name/
    assigned_to fields -- the same cross-tenant leak activities.py
    already guards against for its own contact_id/deal_id."""
    if contact_id is not None:
        get_or_404(db, Contact, contact_id, org, detail="Invalid contact")
    if company_id is not None:
        get_or_404(db, Company, company_id, org, detail="Invalid company")
    if assigned_to_id is not None:
        get_or_404(db, User, assigned_to_id, org, detail="Invalid assigned_to_id")


def _to_out(deal: Deal) -> DealOut:
    item = DealOut.model_validate(deal)
    item.stage_name = deal.stage.name if deal.stage else None
    item.contact_name = f"{deal.contact.first_name} {deal.contact.last_name}".strip() if deal.contact else None
    item.company_name = deal.company.name if deal.company else None
    item.items = [
        DealItemOut(
            id=li.id,
            catalog_item_id=li.catalog_item_id,
            name=li.name,
            unit_price=float(li.unit_price),
            quantity=li.quantity,
            line_total=float(li.unit_price) * li.quantity,
        )
        for li in deal.items
    ]
    return item


@router.get("", response_model=Page)
def list_deals(
    stage_id: int | None = None,
    assigned_to_id: int | None = None,
    search: str | None = None,
    contact_id: int | None = None,
    company_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    query = _base_query(db, org)
    if stage_id:
        query = query.filter(Deal.stage_id == stage_id)
    if assigned_to_id:
        query = query.filter(Deal.assigned_to_id == assigned_to_id)
    if contact_id:
        query = query.filter(Deal.contact_id == contact_id)
    if company_id:
        query = query.filter(Deal.company_id == company_id)
    if search:
        query = query.filter(or_(Deal.title.ilike(f"%{search}%")))

    total = query.count()
    deals = query.order_by(Deal.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return Page(items=[_to_out(d) for d in deals], total=total, page=page, page_size=page_size)


@router.post("", response_model=DealOut, status_code=201)
def create_deal(
    payload: DealCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_permission(db, current_user, "deals:create")
    enforce_within_limit(db, org, "deals")
    stage = get_or_404(db, PipelineStage, payload.stage_id, org, detail="Invalid pipeline stage")
    _validate_refs(db, org, payload.contact_id, payload.company_id, payload.assigned_to_id)
    deal_items, items_total = _resolve_deal_items(db, org, payload.items)
    data = payload.model_dump(exclude={"items"})
    deal = Deal(**data, organization_id=org.id)
    if deal_items:
        # A quoted catalog total is the source of truth for the deal's
        # value the moment there's a quote to compute it from -- a
        # manually-typed `value` alongside real line items would just be
        # stale/wrong the instant they diverge.
        deal.value = items_total
    if stage.is_won or stage.is_lost:
        deal.closed_at = datetime.now(timezone.utc)
    for li in deal_items:
        li.organization_id = org.id
    deal.items = deal_items
    db.add(deal)
    db.commit()
    db.refresh(deal)
    record_action(
        db, current_user, "deals:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="deal", entity_id=deal.id, organization_id=org.id,
    )
    if stage.is_won:
        _sync_gamification(db, org, deal, was_won_before=False, is_won_now=True)
    return _to_out(deal)


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    deal = _base_query(db, org).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return _to_out(deal)


@router.patch("/{deal_id}", response_model=DealOut)
def update_deal(
    deal_id: int,
    payload: DealUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    deal = get_or_404(db, Deal, deal_id, org, detail="Deal not found")
    enforce_permission(db, current_user, "deals:update", {"deal_id": deal_id})

    was_won_before = deal.stage.is_won if deal.stage else False
    is_won_now = was_won_before

    data = payload.model_dump(exclude_unset=True)
    items_payload = data.pop("items", None)  # handled separately below -- not a plain column
    _validate_refs(db, org, data.get("contact_id"), data.get("company_id"), data.get("assigned_to_id"))
    new_stage_id = data.get("stage_id")
    if new_stage_id and new_stage_id != deal.stage_id:
        new_stage = get_or_404(db, PipelineStage, new_stage_id, org, detail="Invalid pipeline stage")
        if new_stage.is_won or new_stage.is_lost:
            deal.closed_at = datetime.now(timezone.utc)
        else:
            deal.closed_at = None
        is_won_now = new_stage.is_won

    for field, value in data.items():
        setattr(deal, field, value)

    if items_payload is not None:
        # Explicitly provided (even `[]`, which clears the quote) -> full
        # replace, same semantics as ContactUpdate.tag_ids.
        new_items, items_total = _resolve_deal_items(db, org, [DealItemInput(**entry) for entry in items_payload])
        for li in new_items:
            li.organization_id = org.id
        deal.items = new_items
        if new_items:
            deal.value = items_total

    db.commit()
    db.refresh(deal)
    record_action(
        db, current_user, "deals:update", source="api", status=AgentActionStatus.success,
        arguments={"deal_id": deal_id, **data}, entity_type="deal", entity_id=deal.id, organization_id=org.id,
    )
    _sync_gamification(db, org, deal, was_won_before, is_won_now)
    return _to_out(deal)


@router.delete("/{deal_id}", status_code=204)
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    deal = get_or_404(db, Deal, deal_id, org, detail="Deal not found")
    enforce_permission(db, current_user, "deals:delete", {"deal_id": deal_id})
    was_won = deal.stage.is_won if deal.stage else False
    deal_title = deal.title
    db.delete(deal)
    db.commit()
    record_action(
        db, current_user, "deals:delete", source="api", status=AgentActionStatus.success,
        arguments={"deal_id": deal_id}, entity_type="deal", entity_id=deal_id, organization_id=org.id,
    )
    if was_won:
        gamification_engine.revoke_points_for_source(
            db, org, PointSourceType.deal_won, f"deal:{deal_id}",
            reason_en=f'Deal "{deal_title}" was deleted',
            reason_fa=f"معامله «{deal_title}» حذف شد",
        )
    return None
