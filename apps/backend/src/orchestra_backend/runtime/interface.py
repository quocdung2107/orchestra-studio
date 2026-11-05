"""Runtime adapter contract (RUNTIME.md §3, ADR-0008).

Adapters emit *internal* `run.*` events. They never touch the database;
the runtime manager validates and normalizes them into `agent.run.*` events (ADR-0007).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class RuntimeCapabilities:
    supports_streaming: bool = False
    supports_cancel: bool = False
    supports_pause: bool = False
    supports_resume: bool = False
    supports_tool_calls: bool = False
    supports_structured_output: bool = False
    supports_checkpointing: bool = False

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_summary: str | None = None


class ToolPort(Protocol):
    """The only way a runtime can use a tool (ADR-0018). Policy is enforced behind it."""

    async def call(self, tool_key: str, params: dict[str, Any]) -> ToolResult: ...


@dataclass(frozen=True)
class RunRequest:
    run_id: uuid.UUID
    agent: dict[str, Any]  # name, role, definition (provider-neutral)
    task: dict[str, Any]  # id, title, description
    context: dict[str, Any] = field(default_factory=dict)
    attempt: int = 1
    tools: ToolPort | None = None


@dataclass(frozen=True)
class RuntimeEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class AgentRuntime(Protocol):
    runtime_id: str
    display_name: str
    capabilities: RuntimeCapabilities

    def execute(self, request: RunRequest) -> AsyncIterator[RuntimeEvent]: ...

    async def health_check(self) -> dict[str, Any]: ...


class ControllableRuntime(Protocol):
    """Implemented only when the matching capability flag is true (ADR-0017)."""

    def cancel(self, run_id: uuid.UUID) -> None: ...

    def pause(self, run_id: uuid.UUID) -> None: ...

    def resume(self, run_id: uuid.UUID) -> None: ...
