from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies.schemas import CompanyOut
from orchestra_backend.core.errors import ErrorResponse, NotFoundError
from orchestra_backend.templates_svc.loader import load_agent_templates, load_company_templates
from orchestra_backend.templates_svc.service import instantiate_company

router = APIRouter(tags=["templates"], responses={404: {"model": ErrorResponse}})


class TemplateInfo(BaseModel):
    id: str
    kind: Literal["company", "agent"]
    title: str
    description: str


class AgentPreset(BaseModel):
    id: str
    title: str
    name: str
    role: str
    instructions: str
    runtime: str


class InstantiateCompany(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)


@router.get("/templates", response_model=list[TemplateInfo])
def list_templates(c: ContainerDep) -> list[TemplateInfo]:
    root = c.settings.templates_dir
    out = [
        TemplateInfo(id=t.id, kind="company", title=t.title, description=t.description)
        for t in load_company_templates(root).values()
    ]
    out += [
        TemplateInfo(id=t.id, kind="agent", title=t.title, description=t.description)
        for t in load_agent_templates(root).values()
    ]
    return out


@router.get("/templates/agent/{template_id}", response_model=AgentPreset)
def agent_preset(c: ContainerDep, template_id: str) -> AgentPreset:
    t = load_agent_templates(c.settings.templates_dir).get(template_id)
    if t is None:
        raise NotFoundError("Template not found")
    return AgentPreset(
        id=t.id,
        title=t.title,
        name=t.name,
        role=t.role,
        instructions=t.instructions,
        runtime=t.runtime,
    )


@router.post(
    "/templates/company/{template_id}/instantiate",
    response_model=CompanyOut,
    status_code=status.HTTP_201_CREATED,
)
def instantiate(c: ContainerDep, template_id: str, body: InstantiateCompany) -> CompanyOut:
    with c.tx() as s:
        company = instantiate_company(
            s, c.settings.templates_dir, template_id, c.extras["registry"].ids(), name=body.name
        )
        return CompanyOut.model_validate(company)
