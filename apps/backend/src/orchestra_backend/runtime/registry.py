from __future__ import annotations

from orchestra_backend.runtime.interface import AgentRuntime


class RuntimeRegistry:
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
