from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.capabilities import service
from orchestra_backend.capabilities.schemas import (
    AccessDecision,
    AgentSkillOut,
    AttachSkill,
    GrantTool,
    SkillCreate,
    SkillDetail,
    SkillVersionIn,
    SkillVersionOut,
    ToolCreate,
    ToolIn,
    ToolOut,
)
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse

router = APIRouter(
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


# ----- skills -----


@router.get("/companies/{company_id}/skills", response_model=list[SkillDetail], tags=["skills"])
def list_skills(c: ContainerDep, company_id: uuid.UUID) -> list[SkillDetail]:
    with c.tx() as s:
        get_company(s, company_id)
        return [service.skill_detail(s, k) for k in service.list_skills(s, company_id)]


@router.post(
    "/companies/{company_id}/skills",
    response_model=SkillDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["skills"],
)
def create_skill(c: ContainerDep, company_id: uuid.UUID, body: SkillCreate) -> SkillDetail:
    with c.tx() as s:
        return service.skill_detail(s, service.create_skill(s, company_id, body))


@router.get("/skills/{skill_id}/versions", response_model=list[SkillVersionOut], tags=["skills"])
def list_skill_versions(c: ContainerDep, skill_id: uuid.UUID) -> list[SkillVersionOut]:
    with c.tx() as s:
        return [service.version_out(v) for v in service.list_skill_versions(s, skill_id)]


@router.post(
    "/skills/{skill_id}/versions",
    response_model=SkillDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["skills"],
)
def create_skill_version(c: ContainerDep, skill_id: uuid.UUID, body: SkillVersionIn) -> SkillDetail:
    with c.tx() as s:
        return service.skill_detail(s, service.create_skill_version(s, skill_id, body))


@router.post("/skills/{skill_id}/archive", response_model=SkillDetail, tags=["skills"])
def archive_skill(c: ContainerDep, skill_id: uuid.UUID) -> SkillDetail:
    with c.tx() as s:
        return service.skill_detail(s, service.archive_skill(s, skill_id))


@router.get("/agents/{agent_id}/skills", response_model=list[AgentSkillOut], tags=["skills"])
def agent_skills(c: ContainerDep, agent_id: uuid.UUID) -> list[AgentSkillOut]:
    with c.tx() as s:
        return service.agent_skills(s, agent_id)


@router.post("/agents/{agent_id}/skills", response_model=list[AgentSkillOut], tags=["skills"])
def attach_skill(c: ContainerDep, agent_id: uuid.UUID, body: AttachSkill) -> list[AgentSkillOut]:
    with c.tx() as s:
        service.attach_skill(s, agent_id, body)
        return service.agent_skills(s, agent_id)


@router.delete(
    "/agents/{agent_id}/skills/{skill_id}", response_model=list[AgentSkillOut], tags=["skills"]
)
def detach_skill(c: ContainerDep, agent_id: uuid.UUID, skill_id: uuid.UUID) -> list[AgentSkillOut]:
    with c.tx() as s:
        service.detach_skill(s, agent_id, skill_id)
        return service.agent_skills(s, agent_id)


# ----- tools -----


@router.get("/companies/{company_id}/tools", response_model=list[ToolOut], tags=["tools"])
def list_tools(c: ContainerDep, company_id: uuid.UUID) -> list[ToolOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [service.tool_out(t) for t in service.list_tools(s, company_id)]


@router.post(
    "/companies/{company_id}/tools",
    response_model=ToolOut,
    status_code=status.HTTP_201_CREATED,
    tags=["tools"],
)
def create_tool(c: ContainerDep, company_id: uuid.UUID, body: ToolCreate) -> ToolOut:
    with c.tx() as s:
        return service.tool_out(service.create_tool(s, company_id, body))


@router.put("/tools/{tool_id}", response_model=ToolOut, tags=["tools"])
def update_tool(c: ContainerDep, tool_id: uuid.UUID, body: ToolIn) -> ToolOut:
    with c.tx() as s:
        return service.tool_out(service.update_tool(s, tool_id, body))


@router.post("/tools/{tool_id}/archive", response_model=ToolOut, tags=["tools"])
def archive_tool(c: ContainerDep, tool_id: uuid.UUID) -> ToolOut:
    with c.tx() as s:
        return service.tool_out(service.archive_tool(s, tool_id))


@router.get("/agents/{agent_id}/tool-access", response_model=list[AccessDecision], tags=["tools"])
def tool_access(c: ContainerDep, agent_id: uuid.UUID) -> list[AccessDecision]:
    with c.tx() as s:
        return service.agent_tool_access(s, agent_id)


@router.post("/agents/{agent_id}/tools", response_model=list[AccessDecision], tags=["tools"])
def grant_tool(c: ContainerDep, agent_id: uuid.UUID, body: GrantTool) -> list[AccessDecision]:
    with c.tx() as s:
        service.grant_tool(s, agent_id, body)
        return service.agent_tool_access(s, agent_id)


@router.delete(
    "/agents/{agent_id}/tools/{tool_id}", response_model=list[AccessDecision], tags=["tools"]
)
def revoke_tool(c: ContainerDep, agent_id: uuid.UUID, tool_id: uuid.UUID) -> list[AccessDecision]:
    with c.tx() as s:
        service.revoke_tool(s, agent_id, tool_id)
        return service.agent_tool_access(s, agent_id)
