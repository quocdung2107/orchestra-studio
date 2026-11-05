"""YAML templates (ADR-0014). Validated on load; invalid files are reported, not half-applied."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from orchestra_backend.capabilities.schemas import ToolPolicy

log = logging.getLogger(__name__)


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TDepartment(_S):
    key: str
    name: str
    description: str = ""
    parent: str | None = None
    max_tool_level: int | None = Field(default=None, ge=0, le=3)


class TSkill(_S):
    name: str
    description: str = ""
    instructions: str = ""
    input_hints: list[str] = Field(default_factory=list)


class TTool(_S):
    key: str
    name: str
    description: str = ""
    permission_level: int = Field(ge=0, le=3)
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    policy: ToolPolicy = Field(default_factory=ToolPolicy)


class TAgent(_S):
    key: str
    name: str
    role: str
    description: str = ""
    department: str | None = None
    reports_to: str | None = None
    instructions: str = ""
    runtime: str = "mock"
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    activate: bool = True


class TCompanyInfo(_S):
    name: str
    description: str = ""
    max_tool_level: int = Field(default=1, ge=0, le=3)


class CompanyTemplate(_S):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: Literal["company"]
    title: str
    description: str = ""
    company: TCompanyInfo
    departments: list[TDepartment] = Field(default_factory=list)
    skills: list[TSkill] = Field(default_factory=list)
    tools: list[TTool] = Field(default_factory=list)
    agents: list[TAgent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _refs(self) -> CompanyTemplate:
        dkeys = {d.key for d in self.departments}
        akeys = {a.key for a in self.agents}
        skills = {s.name for s in self.skills}
        tools = {t.key for t in self.tools}
        for d in self.departments:
            if d.parent and d.parent not in dkeys:
                raise ValueError(f"department {d.key}: unknown parent {d.parent}")
        for a in self.agents:
            if a.department and a.department not in dkeys:
                raise ValueError(f"agent {a.key}: unknown department {a.department}")
            if a.reports_to and a.reports_to not in akeys:
                raise ValueError(f"agent {a.key}: unknown manager {a.reports_to}")
            for s in a.skills:
                if s not in skills:
                    raise ValueError(f"agent {a.key}: unknown skill {s}")
            for t in a.tools:
                if t not in tools:
                    raise ValueError(f"agent {a.key}: unknown tool {t}")
        if len(akeys) != len(self.agents) or len(dkeys) != len(self.departments):
            raise ValueError("duplicate keys")
        seen: set[str] = set()
        for d in self.departments:
            if d.parent and d.parent not in seen:
                raise ValueError(f"department {d.key}: list parent {d.parent} before it")
            seen.add(d.key)
        seen = set()
        for a in self.agents:
            if a.reports_to and a.reports_to not in seen:
                raise ValueError(f"agent {a.key}: list manager {a.reports_to} before it")
            seen.add(a.key)
        return self


class AgentTemplate(_S):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: Literal["agent"]
    title: str
    description: str = ""
    name: str
    role: str
    instructions: str = ""
    runtime: str = "mock"


def _load_dir(path: Path, model: type[BaseModel]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not path.is_dir():
        return out
    for f in sorted(path.glob("*.yaml")):
        try:
            t = model.model_validate(yaml.safe_load(f.read_text(encoding="utf-8")))
        except (ValidationError, yaml.YAMLError) as exc:
            log.error("Invalid template %s: %s", f.name, exc)
            continue
        out[t.id] = t  # type: ignore[attr-defined]
    return out


def load_company_templates(root: Path) -> dict[str, CompanyTemplate]:
    return _load_dir(root / "company", CompanyTemplate)


def load_agent_templates(root: Path) -> dict[str, AgentTemplate]:
    return _load_dir(root / "agent", AgentTemplate)
