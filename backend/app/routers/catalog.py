"""
Org-defined sales catalog: the price list a rep quotes from when building a
Deal (see DealItem in app/models.py and the `items` handling in
app/routers/deals.py). Two resources, both org-scoped like everything else
(see app/tenancy.py):

    CatalogCategory  -- a display grouping (e.g. "Subscription plans")
    CatalogItem      -- one sellable product/service/tariff, with a price,
                         currency and billing cadence (one-time/monthly/yearly)

Writes are admin-only (same reasoning as PipelineStage in
app/routers/pipeline.py: this is shared, org-wide price-list data, not a
personal record) -- everyone in the org can read it, since every rep needs
it to quote a deal.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.audit import record_action
from app.database import get_db
from app.deps import get_current_admin, get_current_org, get_current_user
from app.models import AgentActionStatus, CatalogCategory, CatalogItem, DealItem, Organization, User
from app.schemas import (
    CatalogCategoryCreate,
    CatalogCategoryOut,
    CatalogCategoryUpdate,
    CatalogItemCreate,
    CatalogItemOut,
    CatalogItemUpdate,
)
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def _category_to_out(category: CatalogCategory) -> CatalogCategoryOut:
    out = CatalogCategoryOut.model_validate(category)
    out.item_count = len(category.items)
    return out


@router.get("/categories", response_model=list[CatalogCategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    categories = (
        scoped(db, CatalogCategory, org).options(joinedload(CatalogCategory.items)).order_by(CatalogCategory.order, CatalogCategory.name).all()
    )
    return [_category_to_out(c) for c in categories]


@router.post("/categories", response_model=CatalogCategoryOut, status_code=201)
def create_category(
    payload: CatalogCategoryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    existing = scoped(db, CatalogCategory, org).filter(CatalogCategory.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="A category with this name already exists")
    category = CatalogCategory(**payload.model_dump(), organization_id=org.id)
    db.add(category)
    db.commit()
    db.refresh(category)
    record_action(
        db, admin, "catalog_categories:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="catalog_category", entity_id=category.id, organization_id=org.id,
    )
    return _category_to_out(category)


@router.patch("/categories/{category_id}", response_model=CatalogCategoryOut)
def update_category(
    category_id: int,
    payload: CatalogCategoryUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    category = get_or_404(db, CatalogCategory, category_id, org, detail="Category not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    record_action(
        db, admin, "catalog_categories:update", source="api", status=AgentActionStatus.success,
        arguments={"category_id": category_id, **data}, entity_type="catalog_category", entity_id=category.id, organization_id=org.id,
    )
    return _category_to_out(category)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    category = get_or_404(db, CatalogCategory, category_id, org, detail="Category not found")
    # Deleting a category never deletes its items -- they just become
    # uncategorized (category_id -> NULL via the FK's ON DELETE SET NULL),
    # the same "don't cascade-destroy sellable items over a display
    # grouping" reasoning as Contact.company_id.
    db.delete(category)
    db.commit()
    record_action(
        db, admin, "catalog_categories:delete", source="api", status=AgentActionStatus.success,
        arguments={"category_id": category_id}, entity_type="catalog_category", entity_id=category_id, organization_id=org.id,
    )
    return None


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def _item_to_out(item: CatalogItem) -> CatalogItemOut:
    out = CatalogItemOut.model_validate(item)
    out.category_name = item.category.name if item.category else None
    return out


@router.get("/items", response_model=list[CatalogItemOut])
def list_items(
    category_id: int | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    query = scoped(db, CatalogItem, org).options(joinedload(CatalogItem.category))
    if category_id is not None:
        query = query.filter(CatalogItem.category_id == category_id)
    if not include_inactive:
        query = query.filter(CatalogItem.is_active.is_(True))
    items = query.order_by(CatalogItem.name).all()
    return [_item_to_out(i) for i in items]


@router.post("/items", response_model=CatalogItemOut, status_code=201)
def create_item(
    payload: CatalogItemCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    if payload.category_id is not None:
        get_or_404(db, CatalogCategory, payload.category_id, org, detail="Invalid category")
    item = CatalogItem(**payload.model_dump(), organization_id=org.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    record_action(
        db, admin, "catalog_items:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="catalog_item", entity_id=item.id, organization_id=org.id,
    )
    return _item_to_out(item)


@router.patch("/items/{item_id}", response_model=CatalogItemOut)
def update_item(
    item_id: int,
    payload: CatalogItemUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    item = get_or_404(db, CatalogItem, item_id, org, detail="Item not found")
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data and data["category_id"] is not None:
        get_or_404(db, CatalogCategory, data["category_id"], org, detail="Invalid category")
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    record_action(
        db, admin, "catalog_items:update", source="api", status=AgentActionStatus.success,
        arguments={"item_id": item_id, **data}, entity_type="catalog_item", entity_id=item.id, organization_id=org.id,
    )
    return _item_to_out(item)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    org: Organization = Depends(get_current_org),
):
    item = get_or_404(db, CatalogItem, item_id, org, detail="Item not found")
    # Items already quoted on deals keep their DealItem snapshot (name +
    # unit_price were copied at quote time -- see models.py:DealItem), so
    # deleting a catalog item never rewrites historical deals; it only
    # detaches deal_items.catalog_item_id via ON DELETE SET NULL.
    in_use = scoped(db, DealItem, org).filter(DealItem.catalog_item_id == item_id).count()
    db.delete(item)
    db.commit()
    record_action(
        db, admin, "catalog_items:delete", source="api", status=AgentActionStatus.success,
        arguments={"item_id": item_id, "quoted_on_deals": in_use}, entity_type="catalog_item", entity_id=item_id, organization_id=org.id,
    )
    return None
