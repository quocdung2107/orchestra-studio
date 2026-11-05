"""Validate untrusted runtime output and map `run.*` to persisted `agent.run.*` (ADR-0007)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from orchestra_backend.runtime.interface import RuntimeEvent

MAX_ARTIFACT_BYTES = 1_000_000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Started(_Strict):
    pass


class Progress(_Strict):
    message: str = Field(min_length=1, max_length=2000)
    step: int | None = Field(default=None, ge=0)
    total_steps: int | None = Field(default=None, ge=0)


class Message(_Strict):
    text: str = Field(min_length=1, max_length=4000)


class DelegationRequested(_Strict):
    to_role: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    max_attempts: int = Field(default=1, ge=1, le=5)


class ArtifactProduced(_Strict):
    name: str = Field(min_length=1, max_length=255, pattern=r"^[\w\-. ]+$")
    mime_type: str = Field(pattern=r"^(text/(plain|markdown)|application/json)$")
    content: str = Field(max_length=MAX_ARTIFACT_BYTES)


class Completed(_Strict):
    summary: str = Field(min_length=1, max_length=4000)


class Failed(_Strict):
    error_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")
    error_summary: str = Field(min_length=1, max_length=2000)
    retryable: bool = False


class Cancelled(_Strict):
    pass


class ParallelDelegation(_Strict):
    tasks: list[DelegationRequested] = Field(min_length=1, max_length=10)


class LessonProposed(_Strict):
    title: str = Field(min_length=1, max_length=300)
    lesson: str = Field(min_length=1, max_length=4000)


class RoleChanges(_Strict):
    role: str | None = Field(default=None, min_length=1, max_length=100)
    department: str | None = Field(default=None, min_length=1, max_length=200)
    reports_to_role: str | None = Field(default=None, min_length=1, max_length=100)
    instructions: str | None = Field(default=None, min_length=1, max_length=8000)


class RoleChangeProposed(_Strict):
    target_role: str = Field(min_length=1, max_length=100)
    changes: RoleChanges
    rationale: str = Field(min_length=1, max_length=2000)


RUNTIME_EVENT_SCHEMAS: dict[str, type[_Strict]] = {
    "run.started": Started,
    "run.progress": Progress,
    "run.message": Message,
    "run.delegation.requested": DelegationRequested,
    "run.artifact.produced": ArtifactProduced,
    "run.completed": Completed,
    "run.failed": Failed,
    "run.cancelled": Cancelled,
    "run.delegation.parallel_requested": ParallelDelegation,
    "run.lesson.proposed": LessonProposed,
    "run.role_change.proposed": RoleChangeProposed,
}

# Internal name -> persisted name. Delegation and artifacts get domain handling.
PERSISTED_NAME = {
    "run.started": "agent.run.started",
    "run.progress": "agent.run.progress",
    "run.message": "agent.run.message",
    "run.delegation.requested": "agent.run.delegated",
    "run.artifact.produced": "artifact.created",
    "run.completed": "agent.run.completed",
    "run.failed": "agent.run.failed",
    "run.cancelled": "agent.run.cancelled",
    "run.delegation.parallel_requested": "agent.run.delegated",
    "run.lesson.proposed": "lesson.proposed",
    "run.role_change.proposed": "role_change.proposed",
}


class RuntimeProtocolError(Exception):
    """Runtime sent something outside the contract."""


def validate(event: RuntimeEvent) -> BaseModel:
    schema = RUNTIME_EVENT_SCHEMAS.get(event.type)
    if schema is None:
        raise RuntimeProtocolError(f"unknown runtime event type: {event.type!r}")
    try:
        return schema.model_validate(event.data)
    except ValidationError as exc:
        raise RuntimeProtocolError(f"invalid {event.type} payload") from exc
