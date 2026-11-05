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
class RunRequest:
    run_id: uuid.UUID
    agent: dict[str, Any]  # name, role, definition (provider-neutral)
    task: dict[str, Any]  # id, title, description
    context: dict[str, Any] = field(default_factory=dict)


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
