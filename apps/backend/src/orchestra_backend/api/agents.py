from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from orchestra_backend.agents import service
from orchestra_backend.agents.schemas import (
    AgentCreate,
    AgentDetail,
    AgentOut,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionOut,
)
from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse

router = APIRouter(
    tags=["agents"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


def _known(c: ContainerDep):  # noqa: ANN202 - RuntimeRegistry acts as the known-runtime set
    return c.extras["registry"]


@router.get("/companies/{company_id}/agents", response_model=list[AgentOut])
def list_agents(
    c: ContainerDep, company_id: uuid.UUID, include_archived: bool = False
) -> list[AgentOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [
            AgentOut.model_validate(a)
            for a in service.list_agents(s, company_id, include_archived=include_archived)
        ]


@router.post(
    "/companies/{company_id}/agents",
    response_model=AgentDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_agent(c: ContainerDep, company_id: uuid.UUID, body: AgentCreate) -> AgentDetail:
    with c.tx() as s:
        agent = service.create_agent(s, company_id, body, _known(c))
        return service.detail(s, agent)


@router.get("/agents/{agent_id}", response_model=AgentDetail)
def get_agent(c: ContainerDep, agent_id: uuid.UUID) -> AgentDetail:
    with c.tx() as s:
        return service.detail(s, service.get_agent(s, agent_id))


@router.patch("/agents/{agent_id}", response_model=AgentDetail)
def update_agent(c: ContainerDep, agent_id: uuid.UUID, body: AgentUpdate) -> AgentDetail:
    with c.tx() as s:
        return service.detail(s, service.update_agent(s, agent_id, body))


@router.get("/agents/{agent_id}/versions", response_model=list[AgentVersionOut])
def list_versions(c: ContainerDep, agent_id: uuid.UUID) -> list[AgentVersionOut]:
    with c.tx() as s:
        return [service.version_out(v) for v in service.list_versions(s, agent_id)]


@router.post(
    "/agents/{agent_id}/versions", response_model=AgentDetail, status_code=status.HTTP_201_CREATED
)
def create_version(c: ContainerDep, agent_id: uuid.UUID, body: AgentVersionCreate) -> AgentDetail:
    with c.tx() as s:
        service.create_version(s, agent_id, body, _known(c))
        return service.detail(s, service.get_agent(s, agent_id))


def _transition(c: ContainerDep, agent_id: uuid.UUID, action: str) -> AgentDetail:
    with c.tx() as s:
        return service.detail(s, service.transition(s, agent_id, action))


@router.post("/agents/{agent_id}/activate", response_model=AgentDetail)
def activate(c: ContainerDep, agent_id: uuid.UUID) -> AgentDetail:
    return _transition(c, agent_id, "activate")


@router.post("/agents/{agent_id}/deactivate", response_model=AgentDetail)
def deactivate(c: ContainerDep, agent_id: uuid.UUID) -> AgentDetail:
    return _transition(c, agent_id, "deactivate")


@router.post("/agents/{agent_id}/archive", response_model=AgentDetail)
def archive(c: ContainerDep, agent_id: uuid.UUID) -> AgentDetail:
    return _transition(c, agent_id, "archive")
