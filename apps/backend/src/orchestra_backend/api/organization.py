from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.organization import service
from orchestra_backend.organization.schemas import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    LayoutUpdate,
    OrgGraph,
)

router = APIRouter(
    tags=["organization"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


@router.get("/companies/{company_id}/departments", response_model=list[DepartmentOut])
def list_departments(
    c: ContainerDep, company_id: uuid.UUID, include_archived: bool = False
) -> list[DepartmentOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [
            DepartmentOut.model_validate(d)
            for d in service.list_departments(s, company_id, include_archived=include_archived)
        ]


@router.post(
    "/companies/{company_id}/departments",
    response_model=DepartmentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    c: ContainerDep, company_id: uuid.UUID, body: DepartmentCreate
) -> DepartmentOut:
    with c.tx() as s:
        return DepartmentOut.model_validate(service.create_department(s, company_id, body))


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    c: ContainerDep, department_id: uuid.UUID, body: DepartmentUpdate
) -> DepartmentOut:
    with c.tx() as s:
        return DepartmentOut.model_validate(service.update_department(s, department_id, body))


@router.post("/departments/{department_id}/archive", response_model=DepartmentOut)
def archive_department(c: ContainerDep, department_id: uuid.UUID) -> DepartmentOut:
    with c.tx() as s:
        return DepartmentOut.model_validate(service.archive_department(s, department_id))


@router.get("/companies/{company_id}/org", response_model=OrgGraph)
def org_graph(c: ContainerDep, company_id: uuid.UUID) -> OrgGraph:
    with c.tx() as s:
        return service.org_graph(s, company_id)


@router.put(
    "/companies/{company_id}/org/layout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def save_layout(c: ContainerDep, company_id: uuid.UUID, body: LayoutUpdate) -> Response:
    with c.tx() as s:
        service.save_layout(s, company_id, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
