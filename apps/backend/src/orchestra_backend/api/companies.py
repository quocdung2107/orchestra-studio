from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies import service
from orchestra_backend.companies.schemas import CompanyCreate, CompanyOut, CompanyUpdate
from orchestra_backend.core.errors import ErrorResponse

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


@router.get("", response_model=list[CompanyOut])
def list_companies(c: ContainerDep, include_archived: bool = False) -> list[CompanyOut]:
    with c.tx() as s:
        rows = service.list_companies(s, include_archived=include_archived)
        return [CompanyOut.model_validate(r) for r in rows]


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(c: ContainerDep, body: CompanyCreate) -> CompanyOut:
    with c.tx() as s:
        return CompanyOut.model_validate(service.create_company(s, body))


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(c: ContainerDep, company_id: uuid.UUID) -> CompanyOut:
    with c.tx() as s:
        return CompanyOut.model_validate(service.get_company(s, company_id))


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(c: ContainerDep, company_id: uuid.UUID, body: CompanyUpdate) -> CompanyOut:
    with c.tx() as s:
        return CompanyOut.model_validate(service.update_company(s, company_id, body))


@router.post("/{company_id}/archive", response_model=CompanyOut)
def archive_company(c: ContainerDep, company_id: uuid.UUID) -> CompanyOut:
    with c.tx() as s:
        return CompanyOut.model_validate(service.archive_company(s, company_id))
