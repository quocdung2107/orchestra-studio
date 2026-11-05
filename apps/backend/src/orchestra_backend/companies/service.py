from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.companies.models import Company
from orchestra_backend.companies.schemas import CompanyCreate, CompanyUpdate
from orchestra_backend.core.errors import InvalidStateError, NotFoundError
from orchestra_backend.events.catalog import CompanyCreated, CompanyUpdated
from orchestra_backend.events.models import EventStream
from orchestra_backend.events.service import append_event

SOURCE = "api.companies"


def create_company(session: Session, data: CompanyCreate) -> Company:
    company = Company(name=data.name, description=data.description)
    session.add(company)
    session.flush()
    session.add(EventStream(company_id=company.id, last_sequence=0))
    session.flush()
    append_event(
        session,
        company_id=company.id,
        event_type="company.created",
        payload=CompanyCreated(name=company.name),
        source=SOURCE,
    )
    return company


def list_companies(session: Session, *, include_archived: bool = False) -> list[Company]:
    stmt = select(Company).order_by(Company.created_at)
    if not include_archived:
        stmt = stmt.where(Company.status == "active")
    return list(session.scalars(stmt))


def get_company(session: Session, company_id: uuid.UUID) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company not found", details={"company_id": str(company_id)})
    return company


def get_active_company(session: Session, company_id: uuid.UUID) -> Company:
    company = get_company(session, company_id)
    if company.status != "active":
        raise InvalidStateError("Company is archived")
    return company


def update_company(session: Session, company_id: uuid.UUID, data: CompanyUpdate) -> Company:
    company = get_active_company(session, company_id)
    changes = {
        k: v
        for k, v in data.model_dump(exclude_unset=True).items()
        if v is not None and getattr(company, k) != v
    }
    if not changes:
        return company
    for k, v in changes.items():
        setattr(company, k, v)
    append_event(
        session,
        company_id=company.id,
        event_type="company.updated",
        payload=CompanyUpdated(changes=changes),
        source=SOURCE,
    )
    return company


def archive_company(session: Session, company_id: uuid.UUID) -> Company:
    company = get_active_company(session, company_id)
    company.status = "archived"
    append_event(
        session, company_id=company.id, event_type="company.archived", payload={}, source=SOURCE
    )
    return company
