from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.runtime.interface import AgentRuntime


class RuntimeRegistry:
    """Known runtimes. Behaves like a set of ids for older call sites (`in`, `sorted`)."""

    def __init__(self) -> None:
        self._runtimes: dict[str, AgentRuntime] = {}

    def register(self, runtime: AgentRuntime) -> None:
        if runtime.runtime_id in self._runtimes:
            raise ValueError(f"runtime already registered: {runtime.runtime_id}")
        self._runtimes[runtime.runtime_id] = runtime

    def get(self, runtime_id: str) -> AgentRuntime | None:
        return self._runtimes.get(runtime_id)

    def ids(self) -> set[str]:
        return set(self._runtimes)

    def all(self) -> list[AgentRuntime]:
        return [self._runtimes[k] for k in sorted(self._runtimes)]

    def for_provider(self, provider: str) -> AgentRuntime | None:
        return next(
            (r for r in self._runtimes.values() if getattr(r, "provider", None) == provider), None
        )

    def __contains__(self, runtime_id: object) -> bool:
        return runtime_id in self._runtimes

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._runtimes))

    def validate_settings(self, runtime_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        rt = self._runtimes.get(runtime_id)
        validate = getattr(rt, "validate_settings", None)
        if validate is None:
            return settings
        result = validate(settings)
        if not isinstance(result, dict):
            raise DomainValidationError(
                "Runtime settings rejected", code="invalid_runtime_settings"
            )
        return result
