"""L0 Mock runtime: deterministic, no model/API calls (RUNTIME.md §5)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from orchestra_backend.runtime.interface import RunRequest, RuntimeCapabilities, RuntimeEvent
from orchestra_backend.runtime.mock.scenarios import load_all


class MockRuntime:
    runtime_id = "mock"
    display_name = "Mock (L0, không gọi AI)"
    capabilities = RuntimeCapabilities(supports_streaming=True)

    def __init__(self, step_delay_ms: int = 0) -> None:
        self.step_delay = step_delay_ms / 1000

    async def _tick(self) -> None:
        await asyncio.sleep(self.step_delay)

    async def execute(self, request: RunRequest) -> AsyncIterator[RuntimeEvent]:
        scenario_id = request.context.get("scenario_id")
        scenario = load_all().get(scenario_id) if scenario_id else None
        if scenario is None:
            yield RuntimeEvent("run.started")
            yield RuntimeEvent(
                "run.failed",
                {
                    "error_code": "SCENARIO_NOT_FOUND",
                    "error_summary": f"Mock scenario not found: {scenario_id}",
                },
            )
            return

        steps = scenario.script_for(request.agent["role"]).steps
        total = len(steps)
        yield RuntimeEvent("run.started")
        for i, step in enumerate(steps, start=1):
            await self._tick()
            if step.progress is not None:
                yield RuntimeEvent(
                    "run.progress", {"message": step.progress, "step": i, "total_steps": total}
                )
            elif step.message is not None:
                yield RuntimeEvent("run.message", {"text": step.message})
            elif step.delegate is not None:
                yield RuntimeEvent(
                    "run.delegation.requested",
                    {
                        "to_role": step.delegate.role,
                        "title": step.delegate.title,
                        "description": step.delegate.description,
                    },
                )
            elif step.artifact is not None:
                yield RuntimeEvent("run.artifact.produced", step.artifact.model_dump())
            elif step.complete is not None:
                yield RuntimeEvent("run.completed", {"summary": step.complete})
                return
            elif step.fail is not None:
                yield RuntimeEvent(
                    "run.failed", {"error_code": step.fail.code, "error_summary": step.fail.message}
                )
                return

    async def health_check(self) -> dict[str, Any]:
        return {"status": "ok", "scenarios": sorted(load_all())}
