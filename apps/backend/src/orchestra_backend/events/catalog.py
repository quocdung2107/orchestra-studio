"""Versioned payload schemas for every persisted event type (EVENTS.md §3).

Only names in CATALOG may be persisted. Payloads reject unknown fields.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompanyCreated(Payload):
    name: str


class CompanyUpdated(Payload):
    changes: dict[str, Any]


class CompanyArchived(Payload):
    pass


class AgentRef(Payload):
    agent_id: uuid.UUID


class AgentCreated(AgentRef):
    name: str
    role: str


class AgentUpdated(AgentRef):
    changes: dict[str, Any]


class AgentVersionCreated(AgentRef):
    version_id: uuid.UUID
    version_number: int


class DepartmentCreated(Payload):
    department_id: uuid.UUID
    name: str
    parent_department_id: uuid.UUID | None = None


class DepartmentUpdated(Payload):
    department_id: uuid.UUID
    changes: dict[str, Any]


class DepartmentRef(Payload):
    department_id: uuid.UUID


class SkillCreated(Payload):
    skill_id: uuid.UUID
    name: str


class SkillVersionCreated(Payload):
    skill_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int


class SkillRef(Payload):
    skill_id: uuid.UUID


class AgentSkillAttached(Payload):
    agent_id: uuid.UUID
    skill_id: uuid.UUID
    skill_version_id: uuid.UUID
    version_number: int


class AgentSkillDetached(Payload):
    agent_id: uuid.UUID
    skill_id: uuid.UUID


class ToolDefined(Payload):
    """Full tool definition at a version (the event log is the tool's version history)."""

    tool_id: uuid.UUID
    key: str
    version: int
    definition: dict[str, Any]


class ToolRef(Payload):
    tool_id: uuid.UUID


class AgentToolGranted(Payload):
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    permission_level: int


class AgentToolRevoked(Payload):
    agent_id: uuid.UUID
    tool_id: uuid.UUID


class TemplateInstantiated(Payload):
    template_id: str
    template_kind: str


class TaskCreated(Payload):
    task_id: uuid.UUID
    title: str
    parent_task_id: uuid.UUID | None = None


class TaskAssigned(Payload):
    task_id: uuid.UUID
    agent_id: uuid.UUID


class TaskStatusChanged(Payload):
    task_id: uuid.UUID
    from_status: str
    to_status: str


class RunQueued(Payload):
    run_id: uuid.UUID
    task_id: uuid.UUID
    agent_id: uuid.UUID
    runtime_id: str


class RunRef(Payload):
    run_id: uuid.UUID


class RunProgress(RunRef):
    message: str = Field(max_length=2000)
    step: int | None = None
    total_steps: int | None = None


class RunMessage(RunRef):
    text: str = Field(max_length=4000)


class RunDelegated(RunRef):
    child_task_id: uuid.UUID
    to_role: str


class RunCompleted(RunRef):
    summary: str = Field(max_length=4000)


class RunFailed(RunRef):
    error_code: str
    error_summary: str = Field(max_length=2000)


class ArtifactCreated(Payload):
    artifact_id: uuid.UUID
    run_id: uuid.UUID | None
    task_id: uuid.UUID | None
    name: str
    mime_type: str
    size_bytes: int


class ScenarioStarted(Payload):
    scenario_id: str
    root_task_id: uuid.UUID


CATALOG: dict[str, type[Payload]] = {
    "company.created": CompanyCreated,
    "company.updated": CompanyUpdated,
    "company.archived": CompanyArchived,
    "agent.created": AgentCreated,
    "agent.updated": AgentUpdated,
    "agent.version_created": AgentVersionCreated,
    "agent.activated": AgentRef,
    "agent.deactivated": AgentRef,
    "agent.archived": AgentRef,
    "department.created": DepartmentCreated,
    "department.updated": DepartmentUpdated,
    "department.archived": DepartmentRef,
    "skill.created": SkillCreated,
    "skill.version_created": SkillVersionCreated,
    "skill.archived": SkillRef,
    "agent.skill_attached": AgentSkillAttached,
    "agent.skill_detached": AgentSkillDetached,
    "tool.created": ToolDefined,
    "tool.updated": ToolDefined,
    "tool.archived": ToolRef,
    "agent.tool_granted": AgentToolGranted,
    "agent.tool_revoked": AgentToolRevoked,
    "template.instantiated": TemplateInstantiated,
    "task.created": TaskCreated,
    "task.assigned": TaskAssigned,
    "task.status_changed": TaskStatusChanged,
    "agent.run.queued": RunQueued,
    "agent.run.started": RunRef,
    "agent.run.progress": RunProgress,
    "agent.run.message": RunMessage,
    "agent.run.delegated": RunDelegated,
    "agent.run.completed": RunCompleted,
    "agent.run.failed": RunFailed,
    "artifact.created": ArtifactCreated,
    "scenario.started": ScenarioStarted,
}

SCHEMA_VERSION = 1
