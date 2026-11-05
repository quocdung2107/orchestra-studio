from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LEVEL_NAMES = {0: "read", 1: "draft", 2: "execute", 3: "external"}


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ----- skills -----


class SkillVersionIn(_In):
    instructions: str = Field(default="", max_length=20000)
    input_hints: list[str] = Field(default_factory=list, max_length=50)


class SkillCreate(_In):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    version: SkillVersionIn = Field(default_factory=SkillVersionIn)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class SkillVersionOut(BaseModel):
    id: uuid.UUID
    skill_id: uuid.UUID
    version_number: int
    instructions: str
    input_hints: list[str]
    created_by: str
    created_at: datetime


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    description: str
    status: Literal["active", "archived"]
    latest_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SkillDetail(SkillOut):
    latest_version: SkillVersionOut | None
    latest_version_number: int | None


class AttachSkill(_In):
    skill_id: uuid.UUID
    skill_version_id: uuid.UUID | None = Field(
        default=None, description="Defaults to the skill's latest version"
    )


class AgentSkillOut(BaseModel):
    skill_id: uuid.UUID
    skill_name: str
    skill_version_id: uuid.UUID
    version_number: int
    latest_version_number: int
    attached_at: datetime


# ----- tools -----


class ToolPolicy(_In):
    """SECURITY.md §5. Declared now, enforced by the Tool Gateway in P2."""

    allowed_paths: list[str] = Field(default_factory=list, max_length=50)
    allowed_domains: list[str] = Field(default_factory=list, max_length=50)
    network: Literal["none", "allowlist", "any"] = "none"
    timeout_seconds: int = Field(default=30, ge=1, le=3600)
    max_output_bytes: int = Field(default=1_000_000, ge=1, le=100_000_000)
    requires_approval: bool = False
    idempotent: bool = False


class ToolIn(_In):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    permission_level: int = Field(ge=0, le=3)
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    policy: ToolPolicy = Field(default_factory=ToolPolicy)

    @model_validator(mode="after")
    def _l3_needs_approval(self) -> ToolIn:
        if self.permission_level == 3 and not self.policy.requires_approval:
            raise ValueError("L3 (external action) tools must require approval")
        if self.policy.network == "allowlist" and not self.policy.allowed_domains:
            raise ValueError("network=allowlist needs allowed_domains")
        return self

    @field_validator("input_schema")
    @classmethod
    def _schema_object(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("type") != "object":
            raise ValueError("input_schema must be a JSON Schema with type 'object'")
        return v


class ToolCreate(ToolIn):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_.-]*$")


class ToolOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    key: str
    name: str
    description: str
    version: int
    permission_level: int
    permission_name: str
    input_schema: dict[str, Any]
    policy: ToolPolicy
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime


class GrantTool(_In):
    tool_id: uuid.UUID
    configuration: dict[str, Any] = Field(default_factory=dict)


class AccessDecision(BaseModel):
    """Permission decision record (SECURITY.md §4)."""

    principal: str
    action: str
    resource: str
    tool_id: uuid.UUID
    tool_key: str
    tool_level: int
    ceiling: int
    ceiling_source: str
    granted: bool
    allowed: bool
    result: Literal["allow", "deny_not_granted", "deny_above_ceiling", "deny_inactive"]
    requires_approval: bool
