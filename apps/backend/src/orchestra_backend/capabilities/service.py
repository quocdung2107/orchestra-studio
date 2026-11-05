"""Skills (ADR-0012) and tools + layered permissions (ADR-0013). No tool execution in P1."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent
from orchestra_backend.agents.service import get_agent
from orchestra_backend.capabilities.models import AgentSkill, AgentTool, Skill, SkillVersion, Tool
from orchestra_backend.capabilities.schemas import (
    LEVEL_NAMES,
    AccessDecision,
    AgentSkillOut,
    AttachSkill,
    GrantTool,
    SkillCreate,
    SkillDetail,
    SkillOut,
    SkillVersionIn,
    SkillVersionOut,
    ToolCreate,
    ToolIn,
    ToolOut,
    ToolPolicy,
)
from orchestra_backend.companies.models import Company
from orchestra_backend.companies.service import get_active_company
from orchestra_backend.core.errors import (
    ConflictError,
    DomainValidationError,
    InvalidStateError,
    NotFoundError,
)
from orchestra_backend.events.catalog import (
    AgentSkillAttached,
    AgentSkillDetached,
    AgentToolGranted,
    AgentToolRevoked,
    SkillCreated,
    SkillRef,
    SkillVersionCreated,
    ToolDefined,
    ToolRef,
)
from orchestra_backend.events.service import append_event
from orchestra_backend.organization.service import department_chain

SOURCE = "api.capabilities"


# =============== skills ===============


def get_skill(session: Session, skill_id: uuid.UUID) -> Skill:
    s = session.get(Skill, skill_id)
    if s is None:
        raise NotFoundError("Skill not found", details={"skill_id": str(skill_id)})
    return s


def version_out(v: SkillVersion) -> SkillVersionOut:
    return SkillVersionOut(
        id=v.id,
        skill_id=v.skill_id,
        version_number=v.version_number,
        instructions=v.instructions,
        input_hints=list(v.input_hints_json.get("hints", [])),
        created_by=v.created_by,
        created_at=v.created_at,
    )


def skill_detail(session: Session, skill: Skill) -> SkillDetail:
    latest = session.get(SkillVersion, skill.latest_version_id) if skill.latest_version_id else None
    return SkillDetail(
        **SkillOut.model_validate(skill).model_dump(),
        latest_version=version_out(latest) if latest else None,
        latest_version_number=latest.version_number if latest else None,
    )


def _add_skill_version(
    session: Session, skill: Skill, data: SkillVersionIn, created_by: str
) -> SkillVersion:
    last = session.scalar(
        select(func.max(SkillVersion.version_number)).where(SkillVersion.skill_id == skill.id)
    )
    v = SkillVersion(
        skill_id=skill.id,
        version_number=(last or 0) + 1,
        instructions=data.instructions,
        input_hints_json={"hints": data.input_hints},
        created_by=created_by,
    )
    session.add(v)
    session.flush()
    skill.latest_version_id = v.id
    append_event(
        session,
        company_id=skill.company_id,
        event_type="skill.version_created",
        source=SOURCE,
        payload=SkillVersionCreated(
            skill_id=skill.id, version_id=v.id, version_number=v.version_number
        ),
    )
    return v


def create_skill(
    session: Session, company_id: uuid.UUID, data: SkillCreate, created_by: str = "user"
) -> Skill:
    get_active_company(session, company_id)
    exists = session.scalar(
        select(Skill.id).where(Skill.company_id == company_id, Skill.name == data.name)
    )
    if exists is not None:
        raise ConflictError(f"Skill '{data.name}' already exists", code="duplicate_name")
    skill = Skill(company_id=company_id, name=data.name, description=data.description)
    session.add(skill)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="skill.created",
        source=SOURCE,
        payload=SkillCreated(skill_id=skill.id, name=skill.name),
    )
    _add_skill_version(session, skill, data.version, created_by)
    return skill


def list_skills(session: Session, company_id: uuid.UUID) -> list[Skill]:
    return list(
        session.scalars(
            select(Skill)
            .where(Skill.company_id == company_id, Skill.status == "active")
            .order_by(Skill.name)
        )
    )


def create_skill_version(session: Session, skill_id: uuid.UUID, data: SkillVersionIn) -> Skill:
    skill = get_skill(session, skill_id)
    if skill.status != "active":
        raise InvalidStateError("Skill is archived")
    _add_skill_version(session, skill, data, "user")
    return skill


def list_skill_versions(session: Session, skill_id: uuid.UUID) -> list[SkillVersion]:
    get_skill(session, skill_id)
    return list(
        session.scalars(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .order_by(SkillVersion.version_number.desc())
        )
    )


def archive_skill(session: Session, skill_id: uuid.UUID) -> Skill:
    skill = get_skill(session, skill_id)
    if skill.status != "active":
        raise InvalidStateError("Skill is already archived")
    if session.scalar(select(AgentSkill.agent_id).where(AgentSkill.skill_id == skill.id).limit(1)):
        raise ConflictError("Skill is still attached to agents", code="skill_in_use")
    skill.status = "archived"
    append_event(
        session,
        company_id=skill.company_id,
        event_type="skill.archived",
        source=SOURCE,
        payload=SkillRef(skill_id=skill.id),
    )
    return skill


def attach_skill(session: Session, agent_id: uuid.UUID, data: AttachSkill) -> AgentSkill:
    agent = get_agent(session, agent_id)
    if agent.status == "archived":
        raise InvalidStateError("Agent is archived")
    skill = get_skill(session, data.skill_id)
    if skill.company_id != agent.company_id:
        raise DomainValidationError("Skill belongs to another company", code="cross_company_link")
    if skill.status != "active":
        raise InvalidStateError("Skill is archived")
    version_id = data.skill_version_id or skill.latest_version_id
    version = session.get(SkillVersion, version_id) if version_id else None
    if version is None or version.skill_id != skill.id:
        raise DomainValidationError("Version does not belong to this skill")
    link = session.get(AgentSkill, (agent.id, skill.id))
    if link is None:
        link = AgentSkill(agent_id=agent.id, skill_id=skill.id, skill_version_id=version.id)
        session.add(link)
    elif link.skill_version_id == version.id:
        return link
    else:
        link.skill_version_id = version.id
    session.flush()
    append_event(
        session,
        company_id=agent.company_id,
        event_type="agent.skill_attached",
        source=SOURCE,
        payload=AgentSkillAttached(
            agent_id=agent.id,
            skill_id=skill.id,
            skill_version_id=version.id,
            version_number=version.version_number,
        ),
    )
    return link


def detach_skill(session: Session, agent_id: uuid.UUID, skill_id: uuid.UUID) -> None:
    agent = get_agent(session, agent_id)
    link = session.get(AgentSkill, (agent.id, skill_id))
    if link is None:
        raise NotFoundError("Skill is not attached to this agent")
    session.delete(link)
    append_event(
        session,
        company_id=agent.company_id,
        event_type="agent.skill_detached",
        source=SOURCE,
        payload=AgentSkillDetached(agent_id=agent.id, skill_id=skill_id),
    )


def agent_skills(session: Session, agent_id: uuid.UUID) -> list[AgentSkillOut]:
    get_agent(session, agent_id)
    out: list[AgentSkillOut] = []
    rows = session.scalars(select(AgentSkill).where(AgentSkill.agent_id == agent_id))
    for link in rows:
        skill = session.get(Skill, link.skill_id)
        ver = session.get(SkillVersion, link.skill_version_id)
        latest = session.get(SkillVersion, skill.latest_version_id) if skill else None
        if skill is None or ver is None:
            continue
        out.append(
            AgentSkillOut(
                skill_id=skill.id,
                skill_name=skill.name,
                skill_version_id=ver.id,
                version_number=ver.version_number,
                latest_version_number=latest.version_number if latest else ver.version_number,
                attached_at=link.attached_at,
            )
        )
    return sorted(out, key=lambda x: x.skill_name)


# =============== tools ===============


def get_tool(session: Session, tool_id: uuid.UUID) -> Tool:
    t = session.get(Tool, tool_id)
    if t is None:
        raise NotFoundError("Tool not found", details={"tool_id": str(tool_id)})
    return t


def tool_out(t: Tool) -> ToolOut:
    return ToolOut(
        id=t.id,
        company_id=t.company_id,
        key=t.key,
        name=t.name,
        description=t.description,
        version=t.version,
        permission_level=t.permission_level,
        permission_name=LEVEL_NAMES[t.permission_level],
        input_schema=t.input_schema_json,
        policy=ToolPolicy.model_validate(t.policy_json),
        status=t.status,  # type: ignore[arg-type]
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _definition(t: Tool) -> dict:
    return {
        "name": t.name,
        "description": t.description,
        "permission_level": t.permission_level,
        "input_schema": t.input_schema_json,
        "policy": t.policy_json,
    }


def create_tool(session: Session, company_id: uuid.UUID, data: ToolCreate) -> Tool:
    get_active_company(session, company_id)
    t = Tool(
        company_id=company_id,
        key=data.key,
        name=data.name,
        description=data.description,
        permission_level=data.permission_level,
        input_schema_json=data.input_schema,
        policy_json=data.policy.model_dump(),
    )
    session.add(t)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ConflictError(f"Tool key '{data.key}' already exists", code="duplicate_key") from exc
    append_event(
        session,
        company_id=company_id,
        event_type="tool.created",
        source=SOURCE,
        payload=ToolDefined(tool_id=t.id, key=t.key, version=t.version, definition=_definition(t)),
    )
    return t


def update_tool(session: Session, tool_id: uuid.UUID, data: ToolIn) -> Tool:
    """Replace the definition; bumps version and records it in the event log."""
    t = get_tool(session, tool_id)
    if t.status != "active":
        raise InvalidStateError("Tool is archived")
    new = {
        "name": data.name,
        "description": data.description,
        "permission_level": data.permission_level,
        "input_schema": data.input_schema,
        "policy": data.policy.model_dump(),
    }
    if new == _definition(t):
        return t
    t.name, t.description = data.name, data.description
    t.permission_level = data.permission_level
    t.input_schema_json, t.policy_json = data.input_schema, data.policy.model_dump()
    t.version += 1
    append_event(
        session,
        company_id=t.company_id,
        event_type="tool.updated",
        source=SOURCE,
        payload=ToolDefined(tool_id=t.id, key=t.key, version=t.version, definition=_definition(t)),
    )
    return t


def archive_tool(session: Session, tool_id: uuid.UUID) -> Tool:
    t = get_tool(session, tool_id)
    if t.status != "active":
        raise InvalidStateError("Tool is already archived")
    t.status = "archived"
    append_event(
        session,
        company_id=t.company_id,
        event_type="tool.archived",
        source=SOURCE,
        payload=ToolRef(tool_id=t.id),
    )
    return t


def list_tools(session: Session, company_id: uuid.UUID) -> list[Tool]:
    return list(
        session.scalars(
            select(Tool)
            .where(Tool.company_id == company_id, Tool.status == "active")
            .order_by(Tool.key)
        )
    )


# ----- permissions -----


def effective_ceiling(session: Session, agent: Agent) -> tuple[int, str]:
    """min(company ceiling, every department ceiling up the chain). Returns (level, source)."""
    company = session.get(Company, agent.company_id)
    assert company is not None
    level, source = company.max_tool_level, "company"
    for d in department_chain(session, agent.department_id):
        if d.max_tool_level is not None and d.max_tool_level < level:
            level, source = d.max_tool_level, f"department:{d.name}"
    return level, source


def decide(session: Session, agent: Agent, tool: Tool, action: str = "use") -> AccessDecision:
    ceiling, source = effective_ceiling(session, agent)
    granted = session.get(AgentTool, (agent.id, tool.id)) is not None
    if agent.status != "active" or tool.status != "active":
        result = "deny_inactive"
    elif not granted:
        result = "deny_not_granted"  # default deny
    elif tool.permission_level > ceiling:
        result = "deny_above_ceiling"
    else:
        result = "allow"
    return AccessDecision(
        principal=f"agent:{agent.id}",
        action=action,
        resource=f"tool:{tool.key}",
        tool_id=tool.id,
        tool_key=tool.key,
        tool_level=tool.permission_level,
        ceiling=ceiling,
        ceiling_source=source,
        granted=granted,
        allowed=result == "allow",
        result=result,  # type: ignore[arg-type]
        requires_approval=bool(tool.policy_json.get("requires_approval"))
        or tool.permission_level == 3,
    )


def grant_tool(
    session: Session, agent_id: uuid.UUID, data: GrantTool, granted_by: str = "user"
) -> AgentTool:
    if granted_by.startswith("agent:"):
        raise DomainValidationError("Agents cannot grant tool permissions", code="self_grant")
    agent = get_agent(session, agent_id)
    if agent.status == "archived":
        raise InvalidStateError("Agent is archived")
    tool = get_tool(session, data.tool_id)
    if tool.company_id != agent.company_id:
        raise DomainValidationError("Tool belongs to another company", code="cross_company_link")
    if tool.status != "active":
        raise InvalidStateError("Tool is archived")
    ceiling, source = effective_ceiling(session, agent)
    if tool.permission_level > ceiling:
        raise DomainValidationError(
            f"Tool level L{tool.permission_level} exceeds this agent's ceiling L{ceiling}",
            code="permission_ceiling_exceeded",
            details={
                "tool_level": tool.permission_level,
                "ceiling": ceiling,
                "ceiling_source": source,
            },
        )
    link = session.get(AgentTool, (agent.id, tool.id))
    if link is not None:
        return link
    link = AgentTool(
        agent_id=agent.id,
        tool_id=tool.id,
        configuration_json=data.configuration,
        granted_by=granted_by,
    )
    session.add(link)
    session.flush()
    append_event(
        session,
        company_id=agent.company_id,
        event_type="agent.tool_granted",
        source=SOURCE,
        payload=AgentToolGranted(
            agent_id=agent.id, tool_id=tool.id, permission_level=tool.permission_level
        ),
    )
    return link


def revoke_tool(session: Session, agent_id: uuid.UUID, tool_id: uuid.UUID) -> None:
    agent = get_agent(session, agent_id)
    link = session.get(AgentTool, (agent.id, tool_id))
    if link is None:
        raise NotFoundError("Tool is not granted to this agent")
    session.delete(link)
    append_event(
        session,
        company_id=agent.company_id,
        event_type="agent.tool_revoked",
        source=SOURCE,
        payload=AgentToolRevoked(agent_id=agent.id, tool_id=tool_id),
    )


def agent_tool_access(session: Session, agent_id: uuid.UUID) -> list[AccessDecision]:
    """Decision for every active tool in the company (granted or not)."""
    agent = get_agent(session, agent_id)
    return [decide(session, agent, t) for t in list_tools(session, agent.company_id)]
