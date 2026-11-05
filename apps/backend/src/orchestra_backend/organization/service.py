"""Departments, reporting lines and org graph (ADR-0010, ADR-0011)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent
from orchestra_backend.companies.service import get_active_company
from orchestra_backend.core.errors import (
    ConflictError,
    DomainValidationError,
    InvalidStateError,
    NotFoundError,
)
from orchestra_backend.events.catalog import DepartmentCreated, DepartmentRef, DepartmentUpdated
from orchestra_backend.events.service import append_event
from orchestra_backend.organization.models import Department, OrgLayout
from orchestra_backend.organization.schemas import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    LayoutUpdate,
    OrgAgentNode,
    OrgGraph,
    Position,
)

SOURCE = "api.organization"


def get_department(session: Session, department_id: uuid.UUID) -> Department:
    d = session.get(Department, department_id)
    if d is None:
        raise NotFoundError("Department not found", details={"department_id": str(department_id)})
    return d


def _usable_department(session: Session, company_id: uuid.UUID, dept_id: uuid.UUID) -> Department:
    d = get_department(session, dept_id)
    if d.company_id != company_id:
        raise DomainValidationError(
            "Department belongs to another company", code="cross_company_link"
        )
    if d.status != "active":
        raise InvalidStateError("Department is archived")
    return d


def department_chain(session: Session, dept_id: uuid.UUID | None) -> list[Department]:
    """Department and its ancestors, nearest first. Guards against corrupt cycles."""
    chain: list[Department] = []
    seen: set[uuid.UUID] = set()
    while dept_id is not None and dept_id not in seen:
        seen.add(dept_id)
        d = session.get(Department, dept_id)
        if d is None:
            break
        chain.append(d)
        dept_id = d.parent_department_id
    return chain


def create_department(
    session: Session, company_id: uuid.UUID, data: DepartmentCreate
) -> Department:
    get_active_company(session, company_id)
    if data.parent_department_id is not None:
        _usable_department(session, company_id, data.parent_department_id)
    d = Department(
        company_id=company_id,
        name=data.name,
        description=data.description,
        parent_department_id=data.parent_department_id,
        max_tool_level=data.max_tool_level,
    )
    session.add(d)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="department.created",
        source=SOURCE,
        payload=DepartmentCreated(
            department_id=d.id, name=d.name, parent_department_id=d.parent_department_id
        ),
    )
    return d


def list_departments(
    session: Session, company_id: uuid.UUID, *, include_archived: bool = False
) -> list[Department]:
    stmt = select(Department).where(Department.company_id == company_id)
    if not include_archived:
        stmt = stmt.where(Department.status == "active")
    return list(session.scalars(stmt.order_by(Department.created_at)))


def update_department(session: Session, dept_id: uuid.UUID, data: DepartmentUpdate) -> Department:
    d = get_department(session, dept_id)
    if d.status != "active":
        raise InvalidStateError("Department is archived")
    fields = data.model_dump(exclude_unset=True)
    for nullable_off in ("name", "description"):
        if fields.get(nullable_off, "") is None:
            fields.pop(nullable_off)
    if "parent_department_id" in fields and fields["parent_department_id"] is not None:
        new_parent = fields["parent_department_id"]
        _usable_department(session, d.company_id, new_parent)
        if any(a.id == d.id for a in department_chain(session, new_parent)):
            raise DomainValidationError(
                "Department cannot be placed under itself", code="org_cycle"
            )
    changes = {k: v for k, v in fields.items() if getattr(d, k) != v}
    if changes:
        for k, v in changes.items():
            setattr(d, k, v)
        append_event(
            session,
            company_id=d.company_id,
            event_type="department.updated",
            source=SOURCE,
            payload=DepartmentUpdated(department_id=d.id, changes=changes),
        )
    return d


def archive_department(session: Session, dept_id: uuid.UUID) -> Department:
    d = get_department(session, dept_id)
    if d.status != "active":
        raise InvalidStateError("Department is already archived")
    children = session.scalar(
        select(Department.id)
        .where(Department.parent_department_id == d.id, Department.status == "active")
        .limit(1)
    )
    members = session.scalar(
        select(Agent.id).where(Agent.department_id == d.id, Agent.status != "archived").limit(1)
    )
    if children is not None or members is not None:
        raise ConflictError(
            "Department still has sub-departments or agents", code="department_not_empty"
        )
    d.status = "archived"
    append_event(
        session,
        company_id=d.company_id,
        event_type="department.archived",
        source=SOURCE,
        payload=DepartmentRef(department_id=d.id),
    )
    return d


# ----- agent placement (validated here, applied by agents.service) -----


def validate_agent_placement(
    session: Session,
    agent: Agent,
    *,
    department_id: uuid.UUID | None = None,
    reports_to_agent_id: uuid.UUID | None = None,
    check_department: bool = False,
    check_manager: bool = False,
) -> None:
    if check_department and department_id is not None:
        _usable_department(session, agent.company_id, department_id)
    if check_manager and reports_to_agent_id is not None:
        if reports_to_agent_id == agent.id:
            raise DomainValidationError("Agent cannot report to itself", code="org_cycle")
        manager = session.get(Agent, reports_to_agent_id)
        if manager is None:
            raise NotFoundError("Manager agent not found")
        if manager.company_id != agent.company_id:
            raise DomainValidationError(
                "Manager must belong to the same company", code="cross_company_link"
            )
        if manager.status == "archived":
            raise InvalidStateError("Manager agent is archived")
        seen: set[uuid.UUID] = set()
        cur: Agent | None = manager
        while cur is not None and cur.id not in seen:
            if cur.id == agent.id:
                raise DomainValidationError("Reporting line would form a cycle", code="org_cycle")
            seen.add(cur.id)
            cur = session.get(Agent, cur.reports_to_agent_id) if cur.reports_to_agent_id else None


# ----- graph & layout -----


def org_graph(session: Session, company_id: uuid.UUID) -> OrgGraph:
    get_active_company(session, company_id)
    depts = list_departments(session, company_id)
    agents = list(
        session.scalars(
            select(Agent)
            .where(Agent.company_id == company_id, Agent.status != "archived")
            .order_by(Agent.created_at)
        )
    )
    layout = {
        row.node_key: Position(x=row.x, y=row.y)
        for row in session.scalars(select(OrgLayout).where(OrgLayout.company_id == company_id))
    }
    return OrgGraph(
        company_id=company_id,
        departments=[DepartmentOut.model_validate(d) for d in depts],
        agents=[
            OrgAgentNode(
                id=a.id,
                name=a.name,
                role=a.role,
                status=a.status,
                department_id=a.department_id,
                reports_to_agent_id=a.reports_to_agent_id,
            )
            for a in agents
        ],
        layout=layout,
    )


def save_layout(session: Session, company_id: uuid.UUID, data: LayoutUpdate) -> None:
    get_active_company(session, company_id)
    keys = list(data.positions)
    if keys:
        session.execute(
            delete(OrgLayout).where(
                OrgLayout.company_id == company_id, OrgLayout.node_key.in_(keys)
            )
        )
    for key, pos in data.positions.items():
        session.add(OrgLayout(company_id=company_id, node_key=key, x=pos.x, y=pos.y))
