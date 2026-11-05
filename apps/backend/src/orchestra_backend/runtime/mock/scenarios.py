"""Deterministic mock scenarios loaded from YAML (ADR-0005)."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Delegate(_Strict):
    role: str
    title: str
    description: str = ""


class ArtifactSpec(_Strict):
    name: str
    mime_type: Literal["text/markdown", "text/plain", "application/json"] = "text/markdown"
    content: str


class FailSpec(_Strict):
    code: str
    message: str


class Step(_Strict):
    """Exactly one action per step."""

    progress: str | None = None
    message: str | None = None
    delegate: Delegate | None = None
    artifact: ArtifactSpec | None = None
    complete: str | None = None
    fail: FailSpec | None = None

    @model_validator(mode="after")
    def _one_action(self) -> Step:
        set_fields = [k for k, v in self.__dict__.items() if v is not None]
        if len(set_fields) != 1:
            raise ValueError(f"step must have exactly one action, got {set_fields}")
        return self


class RoleScript(_Strict):
    steps: list[Step] = Field(min_length=1)

    @model_validator(mode="after")
    def _terminal_last(self) -> RoleScript:
        last = self.steps[-1]
        if last.complete is None and last.fail is None:
            raise ValueError("last step must be 'complete' or 'fail'")
        return self


class Entry(_Strict):
    role: str
    title: str
    description: str = ""


class Scenario(_Strict):
    id: str
    name: str
    description: str = ""
    entry: Entry
    roles: dict[str, RoleScript]

    def script_for(self, role: str) -> RoleScript:
        script = self.roles.get(role)
        if script is not None:
            return script
        return RoleScript(
            steps=[Step(progress=f"{role} đang xử lý"), Step(complete=f"{role} đã hoàn thành")]
        )


def _load(path: Path) -> Scenario:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Scenario.model_validate(data)


@cache
def load_all() -> dict[str, Scenario]:
    scenarios = [_load(p) for p in sorted(SCENARIO_DIR.glob("*.yaml"))]
    return {s.id: s for s in scenarios}
