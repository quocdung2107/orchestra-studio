from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AgentStatus = Literal["draft", "active", "inactive", "archived"]

_SECRET_HINTS = ("key", "secret", "token", "password", "credential")


class AgentDefinition(BaseModel):
    """Provider-neutral definition (ADR-0004 minimal schema). Extended in P1."""

    model_config = ConfigDict(extra="forbid")

    instructions: str = Field(default="", max_length=20000)
    goals: list[str] = Field(default_factory=list, max_length=50)
    skills: list[str] = Field(default_factory=list, max_length=50)
    tools: list[str] = Field(default_factory=list, max_length=50)


class RuntimePreference(BaseModel):
    """Which runtime to use plus non-secret settings. Secrets use credential refs (P4)."""

    model_config = ConfigDict(extra="forbid")

    runtime_id: str = Field(default="mock", min_length=1, max_length=50)
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("settings")
    @classmethod
    def _no_secrets(cls, v: dict[str, Any]) -> dict[str, Any]:
        bad = [k for k in v if any(h in k.lower() for h in _SECRET_HINTS)]
        if bad:
            raise ValueError(
                f"secret-like keys not allowed in runtime settings: {bad}; "
                "use a credential reference"
            )
        return v


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    reports_to_agent_id: uuid.UUID | None = None
    definition: AgentDefinition = Field(default_factory=AgentDefinition)
    runtime: RuntimePreference = Field(default_factory=RuntimePreference)

    @field_validator("name", "role")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class AgentVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: AgentDefinition
    runtime: RuntimePreference


class AgentVersionOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    version_number: int
    definition: AgentDefinition
    runtime: RuntimePreference
    created_by: str
    created_at: datetime


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    reports_to_agent_id: uuid.UUID | None
    name: str
    role: str
    description: str
    status: AgentStatus
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AgentDetail(AgentOut):
    current_version: AgentVersionOut | None
