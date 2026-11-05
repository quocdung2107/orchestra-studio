from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from orchestra_backend.agents import service as agents
from orchestra_backend.agents.schemas import AgentCreate, AgentDefinition, RuntimePreference
from orchestra_backend.capabilities import service as caps
from orchestra_backend.capabilities.schemas import (
    AttachSkill,
    GrantTool,
    SkillCreate,
    SkillVersionIn,
    ToolCreate,
)
from orchestra_backend.companies.models import Company
from orchestra_backend.companies.schemas import CompanyCreate
from orchestra_backend.companies.service import create_company
from orchestra_backend.core.errors import NotFoundError
from orchestra_backend.events.catalog import TemplateInstantiated
from orchestra_backend.events.service import append_event
from orchestra_backend.organization import service as org
from orchestra_backend.organization.schemas import DepartmentCreate
from orchestra_backend.templates_svc.loader import load_company_templates


def instantiate_company(
    session: Session,
    root: Path,
    template_id: str,
    known_runtimes: set[str],
    name: str | None = None,
) -> Company:
    """Builds everything through domain services, inside the caller's single transaction."""
    tpl = load_company_templates(root).get(template_id)
    if tpl is None:
        raise NotFoundError("Template not found", details={"template_id": template_id})
    company = create_company(
        session,
        CompanyCreate(
            name=name or tpl.company.name,
            description=tpl.company.description,
            max_tool_level=tpl.company.max_tool_level,
        ),
    )
    append_event(
        session,
        company_id=company.id,
        event_type="template.instantiated",
        source="templates",
        payload=TemplateInstantiated(template_id=tpl.id, template_kind="company"),
    )

    dept_ids = {}
    for d in tpl.departments:  # parents are listed before children (validated order below)
        dept = org.create_department(
            session,
            company.id,
            DepartmentCreate(
                name=d.name,
                description=d.description,
                parent_department_id=dept_ids[d.parent] if d.parent else None,
                max_tool_level=d.max_tool_level,
            ),
        )
        dept_ids[d.key] = dept.id

    skill_ids = {}
    for s in tpl.skills:
        skill = caps.create_skill(
            session,
            company.id,
            SkillCreate(
                name=s.name,
                description=s.description,
                version=SkillVersionIn(instructions=s.instructions, input_hints=s.input_hints),
            ),
            created_by="template",
        )
        skill_ids[s.name] = skill.id

    tool_ids = {}
    for t in tpl.tools:
        tool = caps.create_tool(
            session,
            company.id,
            ToolCreate(
                key=t.key,
                name=t.name,
                description=t.description,
                permission_level=t.permission_level,
                input_schema=t.input_schema,
                policy=t.policy,
            ),
        )
        tool_ids[t.key] = tool.id

    agent_ids = {}
    for a in tpl.agents:  # managers are listed before their reports
        agent = agents.create_agent(
            session,
            company.id,
            AgentCreate(
                name=a.name,
                role=a.role,
                description=a.description,
                department_id=dept_ids[a.department] if a.department else None,
                reports_to_agent_id=agent_ids[a.reports_to] if a.reports_to else None,
                definition=AgentDefinition(instructions=a.instructions),
                runtime=RuntimePreference(runtime_id=a.runtime),
            ),
            known_runtimes,
            created_by="template",
        )
        agent_ids[a.key] = agent.id
        for s in a.skills:
            caps.attach_skill(session, agent.id, AttachSkill(skill_id=skill_ids[s]))
        for k in a.tools:
            caps.grant_tool(
                session, agent.id, GrantTool(tool_id=tool_ids[k]), granted_by="template"
            )
        if a.activate:
            agents.transition(session, agent.id, "activate")
    return company
