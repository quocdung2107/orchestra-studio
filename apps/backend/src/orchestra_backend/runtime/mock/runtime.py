"""L0 Mock runtime: deterministic, no model/API calls (RUNTIME.md §5).

Supports cancel/pause/resume by checking a per-run control between steps (ADR-0017).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from orchestra_backend.runtime.interface import RunRequest, RuntimeCapabilities, RuntimeEvent
from orchestra_backend.runtime.mock.scenarios import default_script, load_all


@dataclass
class _Control:
    cancelled: bool = False
    running: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self.running.set()


class MockRuntime:
    runtime_id = "mock"
    display_name = "Mock (L0, không gọi AI)"
    capabilities = RuntimeCapabilities(
        supports_streaming=True,
        supports_cancel=True,
        supports_pause=True,
        supports_resume=True,
        supports_tool_calls=True,
    )

    def __init__(self, step_delay_ms: int = 0) -> None:
        self.step_delay = step_delay_ms / 1000
        self._controls: dict[uuid.UUID, _Control] = {}

    # ----- control (ADR-0017) -----

    def cancel(self, run_id: uuid.UUID) -> None:
        c = self._controls.get(run_id)
        if c is not None:
            c.cancelled = True
            c.running.set()  # a paused run must wake up to observe cancellation

    def pause(self, run_id: uuid.UUID) -> None:
        c = self._controls.get(run_id)
        if c is not None:
            c.running.clear()

    def resume(self, run_id: uuid.UUID) -> None:
        c = self._controls.get(run_id)
        if c is not None:
            c.running.set()

    async def _checkpoint(self, c: _Control) -> bool:
        """Return False when the run must stop because it was cancelled."""
        await c.running.wait()
        return not c.cancelled

    # ----- execution -----

    async def execute(self, request: RunRequest) -> AsyncIterator[RuntimeEvent]:
        control = _Control()
        self._controls[request.run_id] = control
        try:
            async for ev in self._run(request, control):
                yield ev
        finally:
            self._controls.pop(request.run_id, None)

    async def _run(self, request: RunRequest, control: _Control) -> AsyncIterator[RuntimeEvent]:
        scenario_id = request.context.get("scenario_id")
        role = request.agent["role"]
        if scenario_id is None:
            script = default_script(role)
        else:
            scenario = load_all().get(scenario_id)
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
            script = scenario.script_for(role)

        steps = script.steps
        total = len(steps)
        yield RuntimeEvent("run.started")
        for i, step in enumerate(steps, start=1):
            await asyncio.sleep(self.step_delay)
            if not await self._checkpoint(control):
                yield RuntimeEvent("run.cancelled")
                return
            if step.progress is not None:
                yield RuntimeEvent(
                    "run.progress", {"message": step.progress, "step": i, "total_steps": total}
                )
            elif step.message is not None:
                yield RuntimeEvent("run.message", {"text": step.message})
            elif step.delegate is not None:
                yield RuntimeEvent("run.delegation.requested", _delegation(step.delegate))
            elif step.parallel is not None:
                yield RuntimeEvent(
                    "run.delegation.parallel_requested",
                    {"tasks": [_delegation(d) for d in step.parallel]},
                )
            elif step.artifact is not None:
                yield RuntimeEvent("run.artifact.produced", step.artifact.model_dump())
            elif step.lesson is not None:
                yield RuntimeEvent("run.lesson.proposed", step.lesson.model_dump())
            elif step.propose_role_change is not None:
                yield RuntimeEvent(
                    "run.role_change.proposed", step.propose_role_change.model_dump()
                )
            elif step.tool is not None:
                if request.tools is None:
                    result_ok, code, summary = False, "TOOLS_UNAVAILABLE", "No tool port"
                else:
                    res = await request.tools.call(step.tool.key, step.tool.params)
                    result_ok, code, summary = res.ok, res.error_code, res.error_summary
                if not await self._checkpoint(control):
                    yield RuntimeEvent("run.cancelled")
                    return
                if result_ok:
                    yield RuntimeEvent("run.message", {"text": f"Tool {step.tool.key}: thành công"})
                elif step.tool.on_error == "continue":
                    yield RuntimeEvent(
                        "run.message", {"text": f"Tool {step.tool.key} không chạy: {code}"}
                    )
                else:
                    yield RuntimeEvent(
                        "run.failed",
                        {
                            "error_code": code or "TOOL_FAILED",
                            "error_summary": summary or f"Tool {step.tool.key} failed",
                        },
                    )
                    return
            elif step.complete is not None:
                yield RuntimeEvent("run.completed", {"summary": step.complete})
                return
            elif step.fail is not None:
                f = step.fail
                if f.until_attempt is not None and request.attempt >= f.until_attempt:
                    yield RuntimeEvent(
                        "run.message", {"text": f"Lần thử {request.attempt}: lỗi tạm thời đã hết"}
                    )
                    continue
                yield RuntimeEvent(
                    "run.failed",
                    {"error_code": f.code, "error_summary": f.message, "retryable": f.retryable},
                )
                return

    async def health_check(self) -> dict[str, Any]:
        return {"status": "ok", "scenarios": sorted(load_all())}


def _delegation(d: Any) -> dict[str, Any]:
    return {
        "to_role": d.role,
        "title": d.title,
        "description": d.description,
        "max_attempts": d.max_attempts,
    }
