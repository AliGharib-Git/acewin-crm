from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audit import record_action
from app.database import get_db
from app.deps import enforce_permission, enforce_within_limit, get_current_org, get_current_user
from app.models import AgentActionStatus, Company, Contact, Deal, Organization, PipelineStage, User
from app.schemas import CompanyCreate, CompanyOut, CompanyUpdate, Page
from app.tenancy import get_or_404, scoped

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _serialize(db: Session, org: Organization, company: Company) -> CompanyOut:
    contact_count = scoped(db, Contact, org).filter(Contact.company_id == company.id).count()
    open_deals = (
        scoped(db, Deal, org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(Deal.company_id == company.id, PipelineStage.is_won.is_(False), PipelineStage.is_lost.is_(False))
        .all()
    )
    total_open = float(sum(float(d.value) for d in open_deals))
    data = CompanyOut.model_validate(company)
    data.contact_count = contact_count
    data.open_deal_value = total_open
    return data


@router.get("", response_model=Page)
def list_companies(
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    query = scoped(db, Company, org)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Company.name.ilike(like), Company.industry.ilike(like)))
    total = query.count()
    companies = query.order_by(Company.name).offset((page - 1) * page_size).limit(page_size).all()
    items = [_serialize(db, org, c) for c in companies]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    enforce_permission(db, current_user, "companies:create")
    enforce_within_limit(db, org, "companies")
    company = Company(**payload.model_dump(), organization_id=org.id)
    db.add(company)
    db.commit()
    db.refresh(company)
    record_action(
        db, current_user, "companies:create", source="api", status=AgentActionStatus.success,
        arguments=payload.model_dump(), entity_type="company", entity_id=company.id, organization_id=org.id,
    )
    return _serialize(db, org, company)


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    company = get_or_404(db, Company, company_id, org, detail="Company not found")
    return _serialize(db, org, company)


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    company = get_or_404(db, Company, company_id, org, detail="Company not found")
    enforce_permission(db, current_user, "companies:update")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    record_action(
        db, current_user, "companies:update", source="api", status=AgentActionStatus.success,
        arguments={"company_id": company_id, **data}, entity_type="company", entity_id=company.id, organization_id=org.id,
    )
    return _serialize(db, org, company)


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    company = get_or_404(db, Company, company_id, org, detail="Company not found")
    enforce_permission(db, current_user, "companies:delete")
    db.delete(company)
    db.commit()
    record_action(
        db, current_user, "companies:delete", source="api", status=AgentActionStatus.success,
        arguments={"company_id": company_id}, entity_type="company", entity_id=company_id, organization_id=org.id,
    )
    return None
