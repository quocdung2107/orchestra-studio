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


class ArtifactProduced(_Strict):
    name: str = Field(min_length=1, max_length=255, pattern=r"^[\w\-. ]+$")
    mime_type: str = Field(pattern=r"^(text/(plain|markdown)|application/json)$")
    content: str = Field(max_length=MAX_ARTIFACT_BYTES)


class Completed(_Strict):
    summary: str = Field(min_length=1, max_length=4000)


class Failed(_Strict):
    error_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")
    error_summary: str = Field(min_length=1, max_length=2000)


RUNTIME_EVENT_SCHEMAS: dict[str, type[_Strict]] = {
    "run.started": Started,
    "run.progress": Progress,
    "run.message": Message,
    "run.delegation.requested": DelegationRequested,
    "run.artifact.produced": ArtifactProduced,
    "run.completed": Completed,
    "run.failed": Failed,
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
