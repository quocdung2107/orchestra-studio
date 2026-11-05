from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        raise ValueError("must not be blank")
    return v


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    parent_department_id: uuid.UUID | None = None
    max_tool_level: int | None = Field(default=None, ge=0, le=3)

    _n = field_validator("name")(_strip)


class DepartmentUpdate(BaseModel):
    """Fields left out are unchanged; an explicit null clears parent/max_tool_level."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    parent_department_id: uuid.UUID | None = None
    max_tool_level: int | None = Field(default=None, ge=0, le=3)

    _n = field_validator("name")(_strip)


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    parent_department_id: uuid.UUID | None
    name: str
    description: str
    status: Literal["active", "archived"]
    max_tool_level: int | None
    created_at: datetime
    updated_at: datetime


class OrgAgentNode(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    status: str
    department_id: uuid.UUID | None
    reports_to_agent_id: uuid.UUID | None


class Position(BaseModel):
    x: float
    y: float


class OrgGraph(BaseModel):
    company_id: uuid.UUID
    departments: list[DepartmentOut]
    agents: list[OrgAgentNode]
    layout: dict[str, Position]


class LayoutUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positions: dict[str, Position] = Field(max_length=2000)

    @field_validator("positions")
    @classmethod
    def _keys(cls, v: dict[str, Position]) -> dict[str, Position]:
        for k in v:
            kind, _, ident = k.partition(":")
            if kind not in {"agent", "dept"}:
                raise ValueError(f"invalid node key: {k}")
            uuid.UUID(ident)
        return v
