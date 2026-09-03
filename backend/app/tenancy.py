"""
Shared tenant-isolation helpers.

Every model that belongs to an Organization (Contact, Company, Deal,
Task, Activity, PipelineStage, Tag, KPITarget, Objective,
AgentActionLog, ...) must be reached through these helpers rather than
a bare `db.query(Model).get(id)` -- `.get()` and an unfiltered
`.query()` both happily return another tenant's row, which is exactly
the cross-tenant leak the product spec calls out as never acceptable.

Usage in a router:

    from app.tenancy import get_or_404, scoped

    contact = get_or_404(db, Contact, contact_id, org)
    contacts = scoped(db, Contact, org).filter(Contact.status == "lead").all()

A record that exists but belongs to a different organization returns
404, the same as a record that doesn't exist at all -- never 403,
since a 403 would confirm the record's existence to a user who has no
business knowing that.
"""
from typing import Type, TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Query, Session

from app.models import Organization

ModelT = TypeVar("ModelT")


def scoped(db: Session, model: Type[ModelT], org: Organization) -> Query:
    """A query for `model` pre-filtered to the current organization.
    `model` must have an `organization_id` column."""
    return db.query(model).filter(model.organization_id == org.id)  # type: ignore[attr-defined]


def get_or_404(db: Session, model: Type[ModelT], record_id: int, org: Organization, detail: str = "Not found") -> ModelT:
    record = scoped(db, model, org).filter(model.id == record_id).first()  # type: ignore[attr-defined]
    if record is None:
        raise HTTPException(status_code=404, detail=detail)
    return record
