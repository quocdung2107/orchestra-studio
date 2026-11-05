from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent, AgentVersion
from orchestra_backend.agents.schemas import (
    AgentCreate,
    AgentDefinition,
    AgentDetail,
    AgentOut,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionOut,
    RuntimePreference,
)
from orchestra_backend.companies.service import get_active_company
from orchestra_backend.core.errors import DomainValidationError, InvalidStateError, NotFoundError
from orchestra_backend.events.catalog import (
    AgentCreated,
    AgentRef,
    AgentUpdated,
    AgentVersionCreated,
)
from orchestra_backend.events.service import append_event
from orchestra_backend.organization.service import validate_agent_placement

SOURCE = "api.agents"

# Allowed transitions (validated here, never in the UI).
TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "activate": {"from": {"draft", "inactive"}, "to": {"active"}},
    "deactivate": {"from": {"active"}, "to": {"inactive"}},
    "archive": {"from": {"draft", "active", "inactive"}, "to": {"archived"}},
}


def version_out(v: AgentVersion) -> AgentVersionOut:
    return AgentVersionOut(
        id=v.id,
        agent_id=v.agent_id,
        version_number=v.version_number,
        definition=AgentDefinition.model_validate(v.definition_json),
        runtime=RuntimePreference.model_validate(v.runtime_preference_json),
        created_by=v.created_by,
        created_at=v.created_at,
    )


def detail(session: Session, agent: Agent) -> AgentDetail:
    current = (
        session.get(AgentVersion, agent.current_version_id) if agent.current_version_id else None
    )
    return AgentDetail(
        **AgentOut.model_validate(agent).model_dump(),
        current_version=version_out(current) if current else None,
    )


def get_agent(session: Session, agent_id: uuid.UUID) -> Agent:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise NotFoundError("Agent not found", details={"agent_id": str(agent_id)})
    return agent


def _check_runtime(
    session: Session, company_id: uuid.UUID, runtime: RuntimePreference, known_runtimes: set[str]
) -> None:
    """Runtime must exist; settings must satisfy that runtime; a referenced credential must be
    usable by this company and provider (ADR-0021, ADR-0022)."""
    runtime_id = runtime.runtime_id
    if runtime_id not in known_runtimes:
        raise DomainValidationError(
            f"Unknown runtime: {runtime_id}",
            code="unknown_runtime",
            details={"known": sorted(known_runtimes)},
        )
    validate = getattr(known_runtimes, "validate_settings", None)
    if validate is not None:
        runtime.settings = validate(runtime_id, runtime.settings)
    raw = runtime.settings.get("credential_id")
    if raw:
        from orchestra_backend.credentials import service as creds

        try:
            cred = creds.get(session, uuid.UUID(str(raw)))
        except ValueError as exc:
            raise DomainValidationError("Invalid credential id", code="invalid_credential") from exc
        provider = getattr(
            getattr(known_runtimes, "get", lambda _x: None)(runtime_id), "provider", None
        )
        problem = creds.check_usable(cred, provider or cred.provider, company_id)
        if problem is not None:
            raise DomainValidationError(problem[1], code="credential_not_usable")


def _add_version(
    session: Session,
    agent: Agent,
    definition: AgentDefinition,
    runtime: RuntimePreference,
    created_by: str,
) -> AgentVersion:
    last = session.scalar(
        select(func.max(AgentVersion.version_number)).where(AgentVersion.agent_id == agent.id)
    )
    version = AgentVersion(
        agent_id=agent.id,
        version_number=(last or 0) + 1,
        definition_json=definition.model_dump(mode="json"),
        runtime_preference_json=runtime.model_dump(mode="json"),
        created_by=created_by,
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    append_event(
        session,
        company_id=agent.company_id,
        event_type="agent.version_created",
        payload=AgentVersionCreated(
            agent_id=agent.id, version_id=version.id, version_number=version.version_number
        ),
        source=SOURCE,
    )
    return version


def create_agent(
    session: Session,
    company_id: uuid.UUID,
    data: AgentCreate,
    known_runtimes: set[str],
    created_by: str = "user",
) -> Agent:
    get_active_company(session, company_id)
    _check_runtime(session, company_id, data.runtime, known_runtimes)
    agent = Agent(
        company_id=company_id,
        name=data.name,
        role=data.role,
        description=data.description,
        department_id=data.department_id,
        reports_to_agent_id=data.reports_to_agent_id,
    )
    validate_agent_placement(
        session,
        agent,
        department_id=data.department_id,
        reports_to_agent_id=data.reports_to_agent_id,
        check_department=True,
        check_manager=True,
    )
    session.add(agent)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="agent.created",
        payload=AgentCreated(agent_id=agent.id, name=agent.name, role=agent.role),
        source=SOURCE,
    )
    _add_version(session, agent, data.definition, data.runtime, created_by)
    return agent


def list_agents(
    session: Session, company_id: uuid.UUID, *, include_archived: bool = False
) -> list[Agent]:
    stmt = select(Agent).where(Agent.company_id == company_id).order_by(Agent.created_at)
    if not include_archived:
        stmt = stmt.where(Agent.status != "archived")
    return list(session.scalars(stmt))


def update_agent(session: Session, agent_id: uuid.UUID, data: AgentUpdate) -> Agent:
    agent = get_agent(session, agent_id)
    if agent.status == "archived":
        raise InvalidStateError("Agent is archived")
    fields = data.model_dump(exclude_unset=True)
    for key in ("name", "role", "description"):
        if key in fields:
            if fields[key] is None:
                fields.pop(key)
            else:
                fields[key] = fields[key].strip()
    if any(not fields.get(k, "x") for k in ("name", "role")):
        raise DomainValidationError("name/role must not be blank")
    changes = {k: v for k, v in fields.items() if getattr(agent, k) != v}
    validate_agent_placement(
        session,
        agent,
        department_id=changes.get("department_id"),
        reports_to_agent_id=changes.get("reports_to_agent_id"),
        check_department="department_id" in changes,
        check_manager="reports_to_agent_id" in changes,
    )
    if changes:
        for k, v in changes.items():
            setattr(agent, k, v)
        append_event(
            session,
            company_id=agent.company_id,
            event_type="agent.updated",
            payload=AgentUpdated(agent_id=agent.id, changes=changes),
            source=SOURCE,
        )
    return agent


def create_version(
    session: Session, agent_id: uuid.UUID, data: AgentVersionCreate, known_runtimes: set[str]
) -> AgentVersion:
    agent = get_agent(session, agent_id)
    if agent.status == "archived":
        raise InvalidStateError("Agent is archived")
    _check_runtime(session, agent.company_id, data.runtime, known_runtimes)
    return _add_version(session, agent, data.definition, data.runtime, "user")


def list_versions(session: Session, agent_id: uuid.UUID) -> list[AgentVersion]:
    get_agent(session, agent_id)
    return list(
        session.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
        )
    )


def transition(session: Session, agent_id: uuid.UUID, action: str) -> Agent:
    agent = get_agent(session, agent_id)
    rule = TRANSITIONS[action]
    if agent.status not in rule["from"]:
        raise InvalidStateError(
            f"Cannot {action} agent in status '{agent.status}'",
            details={"status": agent.status, "allowed_from": sorted(rule["from"])},
        )
    if action == "activate" and agent.current_version_id is None:
        raise InvalidStateError("Agent has no version to activate")
    (agent.status,) = rule["to"]
    if action == "archive":
        # Don't leave subordinates pointing at an archived manager.
        for sub in session.scalars(select(Agent).where(Agent.reports_to_agent_id == agent.id)):
            sub.reports_to_agent_id = None
            append_event(
                session,
                company_id=sub.company_id,
                event_type="agent.updated",
                payload=AgentUpdated(agent_id=sub.id, changes={"reports_to_agent_id": None}),
                source=SOURCE,
            )
    event_type = {
        "activate": "agent.activated",
        "deactivate": "agent.deactivated",
        "archive": "agent.archived",
    }[action]
    append_event(
        session,
        company_id=agent.company_id,
        event_type=event_type,
        payload=AgentRef(agent_id=agent.id),
        source=SOURCE,
    )
    return agent
