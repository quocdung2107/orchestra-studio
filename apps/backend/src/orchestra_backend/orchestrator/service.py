"""Sequential P0 orchestrator (ADR-0004, ADR-0008).

Runs execute as asyncio tasks inside the backend process. One scenario at a time per
company. Delegation is depth-first: the parent run waits for the child task to finish.
All database work goes through execution.service inside short transactions.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent, AgentVersion
from orchestra_backend.api.deps import Container
from orchestra_backend.companies.service import get_active_company
from orchestra_backend.core.errors import ConflictError, NotFoundError
from orchestra_backend.events.catalog import ScenarioStarted
from orchestra_backend.events.service import append_event
from orchestra_backend.execution import service as ex
from orchestra_backend.execution.models import RUN_TERMINAL, AgentRun, Task
from orchestra_backend.runtime import normalize
from orchestra_backend.runtime.interface import RunRequest
from orchestra_backend.runtime.mock.scenarios import load_all
from orchestra_backend.runtime.registry import RuntimeRegistry

log = logging.getLogger(__name__)
T = TypeVar("T")
MAX_DELEGATION_DEPTH = 8


class Orchestrator:
    def __init__(self, container: Container, registry: RuntimeRegistry) -> None:
        self.c = container
        self.registry = registry
        self._active: dict[uuid.UUID, asyncio.Task[None]] = {}

    async def _tx(self, fn: Callable[[Session], T]) -> T:
        def work() -> T:
            with self.c.tx() as s:
                return fn(s)

        return await asyncio.to_thread(work)

    # ----- commands -----

    def is_busy(self, company_id: uuid.UUID) -> bool:
        t = self._active.get(company_id)
        return t is not None and not t.done()

    async def start_scenario(self, company_id: uuid.UUID, scenario_id: str) -> uuid.UUID:
        scenario = load_all().get(scenario_id)
        if scenario is None:
            raise NotFoundError("Scenario not found", details={"scenario_id": scenario_id})
        if self.is_busy(company_id):
            raise ConflictError(
                "A scenario is already running for this company", code="company_busy"
            )
        correlation_id = uuid.uuid4()

        def create(s: Session) -> uuid.UUID:
            get_active_company(s, company_id)
            task = ex.create_task(
                s,
                company_id=company_id,
                title=scenario.entry.title,
                description=scenario.entry.description,
                required_role=scenario.entry.role,
                created_by="user",
                correlation_id=correlation_id,
            )
            append_event(
                s,
                company_id=company_id,
                event_type="scenario.started",
                source="orchestrator",
                correlation_id=correlation_id,
                payload=ScenarioStarted(scenario_id=scenario_id, root_task_id=task.id),
            )
            return task.id

        root_id = await self._tx(create)
        ctx = {"scenario_id": scenario_id}
        job = asyncio.create_task(self._guarded(root_id, ctx, correlation_id))
        self._active[company_id] = job
        return root_id

    async def wait_idle(self, company_id: uuid.UUID) -> None:
        t = self._active.get(company_id)
        if t is not None:
            await t

    async def shutdown(self) -> None:
        for t in self._active.values():
            t.cancel()
        for t in self._active.values():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t

    async def recover(self) -> None:
        count = await self._tx(ex.fail_interrupted_runs)
        if count:
            log.warning("Marked %d interrupted run(s) as failed", count)

    # ----- execution -----

    async def _guarded(self, task_id: uuid.UUID, ctx: dict, corr: uuid.UUID) -> None:
        try:
            await self._execute_task(task_id, ctx, corr, depth=0)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Orchestrator crashed while executing task %s", task_id)

    async def _execute_task(
        self, task_id: uuid.UUID, ctx: dict, corr: uuid.UUID, depth: int
    ) -> bool:
        def prepare(s: Session) -> tuple[uuid.UUID, RunRequest] | None:
            task = ex.get_task(s, task_id)
            agent = s.get(Agent, task.assigned_agent_id) if task.assigned_agent_id else None
            if agent is None or agent.status != "active":
                ex.set_task_status(s, task, "failed", corr)
                return None
            run = ex.create_run(s, task, agent, input_json=ctx, correlation_id=corr)
            version = s.get(AgentVersion, run.agent_version_id)
            assert version is not None
            req = RunRequest(
                run_id=run.id,
                agent={
                    "id": str(agent.id),
                    "name": agent.name,
                    "role": agent.role,
                    "definition": version.definition_json,
                },
                task={"id": str(task.id), "title": task.title, "description": task.description},
                context=dict(ctx),
            )
            return run.id, req

        prepared = await self._tx(prepare)
        if prepared is None:
            log.info("Task %s failed: no active agent for its role", task_id)
            return False
        run_id, req = prepared

        def fail(code: str, summary: str) -> Callable[[Session], None]:
            def _f(s: Session) -> None:
                ex.finish_run(
                    s,
                    ex.get_run(s, run_id),
                    ok=False,
                    error_code=code,
                    error_summary=summary,
                    correlation_id=corr,
                )

            return _f

        runtime_id = await self._tx(lambda s: ex.get_run(s, run_id).runtime_id)
        runtime = self.registry.get(runtime_id)
        if runtime is None:
            await self._tx(fail("RUNTIME_UNAVAILABLE", f"Runtime '{runtime_id}' not registered"))
            return False

        stream = runtime.execute(req)
        started = False
        try:
            async for raw in stream:
                try:
                    ev = normalize.validate(raw)
                except normalize.RuntimeProtocolError as exc:
                    await self._tx(fail("RUNTIME_PROTOCOL_ERROR", str(exc)))
                    return False

                if raw.type != "run.started" and not started:
                    await self._tx(lambda s: ex.mark_started(s, ex.get_run(s, run_id), corr))
                    started = True

                match ev:
                    case normalize.Started():
                        if not started:
                            await self._tx(
                                lambda s: ex.mark_started(s, ex.get_run(s, run_id), corr)
                            )
                            started = True
                    case normalize.Progress():
                        await self._tx(
                            lambda s, e=ev: ex.record_progress(
                                s, ex.get_run(s, run_id), e.message, e.step, e.total_steps, corr
                            )
                        )
                    case normalize.Message():
                        await self._tx(
                            lambda s, e=ev: ex.record_message(
                                s, ex.get_run(s, run_id), e.text, corr
                            )
                        )
                    case normalize.ArtifactProduced():
                        await self._tx(
                            lambda s, e=ev: ex.store_artifact(
                                s,
                                ex.get_run(s, run_id),
                                name=e.name,
                                mime_type=e.mime_type,
                                content=e.content,
                                artifacts_dir=self.c.settings.artifacts_dir,
                                correlation_id=corr,
                            )
                        )
                    case normalize.DelegationRequested():
                        if depth >= MAX_DELEGATION_DEPTH:
                            await self._tx(
                                fail(
                                    "DELEGATION_TOO_DEEP",
                                    f"Delegation depth exceeds {MAX_DELEGATION_DEPTH}",
                                )
                            )
                            return False
                        child_id = await self._tx(
                            lambda s, e=ev: self._delegate(s, run_id, e, corr)
                        )
                        ok = await self._execute_task(child_id, ctx, corr, depth + 1)
                        if not ok:
                            await self._tx(
                                fail(
                                    "CHILD_TASK_FAILED",
                                    f"Delegated task '{ev.title}' ({ev.to_role}) failed",
                                )
                            )
                            return False
                    case normalize.Completed():
                        await self._tx(
                            lambda s, e=ev: ex.finish_run(
                                s,
                                ex.get_run(s, run_id),
                                ok=True,
                                summary=e.summary,
                                correlation_id=corr,
                            )
                        )
                        return True
                    case normalize.Failed():
                        await self._tx(
                            lambda s, e=ev: ex.finish_run(
                                s,
                                ex.get_run(s, run_id),
                                ok=False,
                                error_code=e.error_code,
                                error_summary=e.error_summary,
                                correlation_id=corr,
                            )
                        )
                        return False
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # runtime crashed: report, never fake success
            await self._tx(fail("RUNTIME_ERROR", f"Runtime raised {type(exc).__name__}"))
            return False
        finally:
            await stream.aclose()  # type: ignore[attr-defined]

        await self._tx(fail("RUNTIME_PROTOCOL_ERROR", "Runtime ended without a terminal event"))
        return False

    def _delegate(
        self, s: Session, run_id: uuid.UUID, ev: normalize.DelegationRequested, corr: uuid.UUID
    ) -> uuid.UUID:
        run: AgentRun = ex.get_run(s, run_id)
        parent: Task = ex.get_task(s, run.task_id)  # type: ignore[arg-type]
        child = ex.create_task(
            s,
            company_id=run.company_id,
            title=ev.title,
            description=ev.description,
            required_role=ev.to_role,
            created_by=f"agent:{run.agent_id}",
            parent_task_id=parent.id,
            correlation_id=corr,
        )
        ex.record_delegation(s, run, child, ev.to_role, corr)
        return child.id


def run_is_terminal(run: AgentRun) -> bool:
    return run.status in RUN_TERMINAL
