"""Tool Gateway: the single enforcement point for tool use (ADR-0018, SECURITY §5)."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent
from orchestra_backend.approvals import service as approvals
from orchestra_backend.approvals.models import Approval
from orchestra_backend.capabilities.models import Tool
from orchestra_backend.capabilities.service import decide
from orchestra_backend.core.time import utcnow
from orchestra_backend.events.catalog import ToolCall, ToolCallDenied, ToolCallFinished
from orchestra_backend.events.service import append_event
from orchestra_backend.execution import service as ex
from orchestra_backend.orchestrator.tools_builtin import (
    EXECUTORS,
    ToolContext,
    ToolError,
    validate_input,
)
from orchestra_backend.runtime.interface import ToolResult

if TYPE_CHECKING:
    from orchestra_backend.orchestrator.service import Orchestrator

SOURCE = "tool_gateway"


class RunToolPort:
    """ToolPort bound to one run; handed to the runtime in RunRequest.tools."""

    def __init__(self, gateway: ToolGateway, run_id: uuid.UUID, corr: uuid.UUID | None) -> None:
        self._g = gateway
        self._run_id = run_id
        self._corr = corr

    async def call(self, tool_key: str, params: dict[str, Any]) -> ToolResult:
        return await self._g.call(self._run_id, self._corr, tool_key, params)


class ToolGateway:
    def __init__(self, orch: Orchestrator) -> None:
        self.o = orch
        self._waiters: dict[uuid.UUID, asyncio.Future[str]] = {}

    def port(self, run_id: uuid.UUID, corr: uuid.UUID | None) -> RunToolPort:
        return RunToolPort(self, run_id, corr)

    # ----- approval signalling -----

    def approval_closed(self, approval_id: uuid.UUID, status: str) -> None:
        fut = self._waiters.get(approval_id)
        if fut is not None and not fut.done():
            fut.set_result(status)

    async def _wait_decision(self, approval_id: uuid.UUID) -> str:
        fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._waiters[approval_id] = fut
        try:
            # The decision may have landed between creating the approval and registering.
            status = await self.o._tx(lambda s: approvals.get(s, approval_id).status)
            if status != "pending":
                return status
            return await fut
        finally:
            self._waiters.pop(approval_id, None)

    # ----- the call -----

    async def call(
        self, run_id: uuid.UUID, corr: uuid.UUID | None, key: str, params: dict[str, Any]
    ) -> ToolResult:
        call_id = uuid.uuid4()

        def prepare(s: Session) -> tuple[str, Any, uuid.UUID | None]:
            run = ex.get_run(s, run_id)
            agent = s.get(Agent, run.agent_id)
            assert agent is not None
            base: dict[str, Any] = {
                "call_id": call_id,
                "run_id": run.id,
                "agent_id": agent.id,
                "tool_key": key,
            }

            def deny(code: str, reason: str) -> tuple[str, Any, None]:
                append_event(
                    s,
                    company_id=run.company_id,
                    event_type="tool.call_denied",
                    source=SOURCE,
                    run_id=run.id,
                    correlation_id=corr,
                    payload=ToolCallDenied(**base, reason=reason, error_code=code),
                )
                return "done", ToolResult(False, error_code=code, error_summary=reason), None

            tool = s.scalar(
                select(Tool).where(
                    Tool.company_id == run.company_id, Tool.key == key, Tool.status == "active"
                )
            )
            if tool is None:
                return deny("TOOL_NOT_FOUND", f"No active tool '{key}' in this company")
            base.update(tool_id=tool.id, permission_level=tool.permission_level)
            append_event(
                s,
                company_id=run.company_id,
                event_type="tool.call_requested",
                source=SOURCE,
                run_id=run.id,
                correlation_id=corr,
                payload=ToolCall(**base),
            )
            decision = decide(s, agent, tool)
            if not decision.allowed:
                return deny("TOOL_DENIED", decision.result)
            err = validate_input(tool.input_schema_json or {}, params)
            if err:
                return deny("TOOL_INPUT_INVALID", err)
            if key not in EXECUTORS:
                return deny("TOOL_NOT_IMPLEMENTED", f"No executor for '{key}' yet")
            if decision.requires_approval:
                a = approvals.create(
                    s,
                    company_id=run.company_id,
                    run_id=run.id,
                    task_id=run.task_id,
                    agent_id=agent.id,
                    tool_id=tool.id,
                    action_type=f"tool:{key}",
                    request={"tool_key": key, "tool_version": tool.version, "params": params},
                    required_level=tool.permission_level,
                    correlation_id=corr,
                )
                ex.set_run_status(s, run, "waiting_approval", corr, source=SOURCE)
                return "approval", base, a.id
            return "exec", base, None

        kind, base, approval_id = await self.o._tx(prepare)
        if kind == "done":
            return base

        if approval_id is not None:
            status = await self._wait_decision(approval_id)
            if status != "approved":
                code = "APPROVAL_REJECTED" if status == "rejected" else "APPROVAL_" + status.upper()

                def rejected(s: Session) -> None:
                    run = ex.get_run(s, run_id)
                    if run.status == "waiting_approval":
                        ex.set_run_status(s, run, "running", corr, source=SOURCE)
                    append_event(
                        s,
                        company_id=run.company_id,
                        event_type="tool.call_finished",
                        source=SOURCE,
                        run_id=run.id,
                        correlation_id=corr,
                        payload=ToolCallFinished(
                            **base, ok=False, error_code=code, approval_id=approval_id
                        ),
                    )

                await self.o._tx(rejected)
                return ToolResult(False, error_code=code, error_summary=f"Approval {status}")

        return await self._execute(run_id, corr, key, params, base, approval_id)

    async def _execute(
        self,
        run_id: uuid.UUID,
        corr: uuid.UUID | None,
        key: str,
        params: dict[str, Any],
        base: dict[str, Any],
        approval_id: uuid.UUID | None,
    ) -> ToolResult:
        timeout = 30.0

        def work(s: Session) -> dict[str, Any]:
            run = ex.get_run(s, run_id)
            tool = s.get(Tool, base["tool_id"])
            assert tool is not None
            approval: Approval | None = None
            if approval_id is not None:
                approval = approvals.get(s, approval_id)
                # Exactly once: an approval executes only from approved + not yet executed.
                if approval.status != "approved" or approval.execution_status is not None:
                    raise ToolError("APPROVAL_ALREADY_USED", "Approval cannot be executed again")
                if approvals.canonical_checksum(approval.request_json) != approval.checksum:
                    raise ToolError("APPROVAL_TAMPERED", "Approved payload changed")
                params_ = approval.request_json["params"]
            else:
                params_ = params
            if run.status == "waiting_approval":
                ex.set_run_status(s, run, "running", corr, source=SOURCE)
            ctx = ToolContext(
                session=s, settings=self.o.c.settings, run=run, tool=tool, correlation_id=corr
            )
            result = EXECUTORS[key](ctx, params_)
            if approval is not None:
                approval.execution_status = "succeeded"
                approval.result_json = result
                approval.executed_at = utcnow()
            append_event(
                s,
                company_id=run.company_id,
                event_type="tool.call_finished",
                source=SOURCE,
                run_id=run.id,
                correlation_id=corr,
                payload=ToolCallFinished(**base, ok=True, approval_id=approval_id),
            )
            return result

        try:
            timeout = await self.o._tx(
                lambda s: float(
                    (s.get(Tool, base["tool_id"]).policy_json or {}).get("timeout_seconds", 30)  # type: ignore[union-attr]
                )
            )
            data = await asyncio.wait_for(self.o._tx(work), timeout=timeout)
            return ToolResult(True, data=data)
        except ToolError as exc:
            code, summary = exc.code, exc.message
        except TimeoutError:
            # Outcome unknown for side effects: never auto-retry (ADR-0016).
            code, summary = "TOOL_OUTCOME_UNKNOWN", f"Tool exceeded {timeout:.0f}s timeout"
        except Exception as exc:  # executor bug: report, never fake success
            code, summary = "TOOL_FAILED", f"{type(exc).__name__}"

        def failed(s: Session) -> None:
            run = ex.get_run(s, run_id)
            if run.status == "waiting_approval":
                ex.set_run_status(s, run, "running", corr, source=SOURCE)
            if approval_id is not None:
                a = approvals.get(s, approval_id)
                if a.execution_status is None:
                    a.execution_status = "failed"
                    a.result_json = {"error_code": code, "error_summary": summary}
                    a.executed_at = utcnow()
            append_event(
                s,
                company_id=run.company_id,
                event_type="tool.call_finished",
                source=SOURCE,
                run_id=run.id,
                correlation_id=corr,
                payload=ToolCallFinished(
                    **base, ok=False, error_code=code, approval_id=approval_id
                ),
            )

        await self.o._tx(failed)
        return ToolResult(False, error_code=code, error_summary=summary)
