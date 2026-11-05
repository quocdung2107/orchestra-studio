"""In-process orchestrator (ADR-0008, ADR-0015..0018).

- A scheduler per company runs ready root tasks, at most `max_parallel_runs` at once.
- Delegated child tasks run inside their parent run (sequentially, or in parallel groups).
- Retries create new runs; pause/resume/cancel go to runtimes that declare support.
- All database work happens in short transactions in worker threads.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Callable
from typing import Literal, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent, AgentVersion
from orchestra_backend.api.deps import Container
from orchestra_backend.approvals import service as approvals
from orchestra_backend.capabilities import service as caps
from orchestra_backend.companies.models import Company
from orchestra_backend.companies.service import get_active_company
from orchestra_backend.core.errors import AppError, InvalidStateError, NotFoundError
from orchestra_backend.core.redact import redact
from orchestra_backend.credentials import service as creds
from orchestra_backend.credentials.store import SecretStore
from orchestra_backend.events.catalog import ScenarioStarted, TaskRef
from orchestra_backend.events.service import append_event
from orchestra_backend.execution import service as ex
from orchestra_backend.execution.models import RUN_TERMINAL, TASK_TERMINAL, AgentRun, Task
from orchestra_backend.knowledge import service as kn
from orchestra_backend.knowledge.schemas import LessonCreate
from orchestra_backend.metrics import service as metrics
from orchestra_backend.metrics.pricing import load as load_prices
from orchestra_backend.orchestrator.gateway import ToolGateway
from orchestra_backend.orchestrator.tools_builtin import EXECUTORS
from orchestra_backend.runtime import normalize
from orchestra_backend.runtime.interface import RunRequest
from orchestra_backend.runtime.mock.scenarios import load_all
from orchestra_backend.runtime.registry import RuntimeRegistry

log = logging.getLogger(__name__)
T = TypeVar("T")
Outcome = Literal["completed", "failed", "cancelled"]
MAX_DELEGATION_DEPTH = 8


class NotSupportedError(AppError):
    status_code = 409
    code = "not_supported"


class Orchestrator:
    def __init__(
        self,
        container: Container,
        registry: RuntimeRegistry,
        secrets: SecretStore | None = None,
    ) -> None:
        self.c = container
        self.registry = registry
        self.secrets = secrets
        self.gateway = ToolGateway(self)
        self._loops: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._wake: dict[uuid.UUID, asyncio.Event] = {}
        self._roots: dict[uuid.UUID, dict[uuid.UUID, asyncio.Task[None]]] = {}
        self._cancel: set[uuid.UUID] = set()  # run ids with a pending cancel request
        self._paused: set[uuid.UUID] = set()

    async def _tx(self, fn: Callable[[Session], T]) -> T:
        def work() -> T:
            with self.c.tx() as s:
                return fn(s)

        return await asyncio.to_thread(work)

    # ================= scheduling (ADR-0015) =================

    def kick(self, company_id: uuid.UUID) -> None:
        self._wake.setdefault(company_id, asyncio.Event()).set()
        loop = self._loops.get(company_id)
        if loop is None or loop.done():
            self._loops[company_id] = asyncio.create_task(self._loop(company_id))

    async def _loop(self, cid: uuid.UUID) -> None:
        running = self._roots.setdefault(cid, {})
        wake = self._wake.setdefault(cid, asyncio.Event())
        while True:
            wake.clear()

            def ready(s: Session) -> tuple[int, list[uuid.UUID]]:
                company = s.get(Company, cid)
                limit = company.max_parallel_runs if company else 1
                return limit, [t.id for t in ex.ready_root_tasks(s, cid)]

            try:
                limit, ready_ids = await self._tx(ready)
            except Exception:
                log.exception("Scheduler query failed for company %s", cid)
                return
            for tid in ready_ids:
                if len(running) >= max(1, limit):
                    break
                if tid not in running:
                    running[tid] = asyncio.create_task(self._run_root(tid))
            if not running:
                if wake.is_set():
                    continue
                return
            waker = asyncio.create_task(wake.wait())
            await asyncio.wait([*running.values(), waker], return_when=asyncio.FIRST_COMPLETED)
            waker.cancel()
            for tid in [t for t, job in running.items() if job.done()]:
                running.pop(tid)

    async def _run_root(self, task_id: uuid.UUID) -> None:
        try:
            await self._execute_task(task_id, depth=0)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Orchestrator crashed while executing task %s", task_id)

    async def wait_idle(self, company_id: uuid.UUID) -> None:
        while True:
            loop = self._loops.get(company_id)
            if loop is None or loop.done():
                return
            await loop

    def is_busy(self, company_id: uuid.UUID) -> bool:
        loop = self._loops.get(company_id)
        return loop is not None and not loop.done()

    # ================= commands =================

    async def start_scenario(self, company_id: uuid.UUID, scenario_id: str) -> uuid.UUID:
        scenario = load_all().get(scenario_id)
        if scenario is None:
            raise NotFoundError("Scenario not found", details={"scenario_id": scenario_id})
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
                max_attempts=scenario.entry.max_attempts,
                context={"scenario_id": scenario_id},
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
        self.kick(company_id)
        return root_id

    async def retry_task(self, task_id: uuid.UUID) -> None:
        def go(s: Session) -> uuid.UUID:
            task = ex.get_task(s, task_id)
            ex.request_retry(s, task)
            return task.company_id

        self.kick(await self._tx(go))

    def _runtime_for(self, runtime_id: str, capability: str):  # type: ignore[no-untyped-def]
        rt = self.registry.get(runtime_id)
        if rt is None or not getattr(rt.capabilities, capability):
            raise NotSupportedError(
                f"Runtime '{runtime_id}' does not support this action",
                details={"capability": capability},
            )
        return rt

    async def cancel_task(self, task_id: uuid.UUID) -> None:
        """Cancel a task and everything below it (ADR-0017)."""

        def go(s: Session) -> list[tuple[uuid.UUID, str, list[uuid.UUID]]]:
            task = ex.get_task(s, task_id)
            if task.status in TASK_TERMINAL:
                raise InvalidStateError(f"Task is already {task.status}")
            tree = [task, *ex.descendants(s, task)]
            live: list[AgentRun] = []
            for t in tree:
                live += list(
                    s.scalars(
                        select(AgentRun).where(
                            AgentRun.task_id == t.id, AgentRun.status.not_in(RUN_TERMINAL)
                        )
                    )
                )
            for r in live:  # check every runtime before changing anything
                self._runtime_for(r.runtime_id, "supports_cancel")
            append_event(
                s,
                company_id=task.company_id,
                event_type="task.cancel_requested",
                source="api.tasks",
                payload=TaskRef(task_id=task.id),
            )
            out = []
            for r in live:
                ex.set_run_status(s, r, "cancel_requested", source="api.tasks")
                closed = []
                for a in approvals.pending_for_run(s, r.id):
                    approvals.close(s, a, "cancelled", source="api.tasks")
                    closed.append(a.id)
                out.append((r.id, r.runtime_id, closed))
            live_tasks = {r.task_id for r in live}
            for t in tree:
                # Pending tasks, or active ones between attempts (retry backoff): cancel now.
                if t.status not in TASK_TERMINAL and t.id not in live_tasks:
                    ex.set_task_status(s, t, "cancelled")
            return out

        for run_id, runtime_id, closed in await self._tx(go):
            self._cancel.add(run_id)
            self._paused.discard(run_id)
            self.registry.get(runtime_id).cancel(run_id)  # type: ignore[union-attr]
            for aid in closed:
                self.gateway.approval_closed(aid, "cancelled")

    async def pause_run(self, run_id: uuid.UUID) -> None:
        def go(s: Session) -> str:
            run = ex.get_run(s, run_id)
            self._runtime_for(run.runtime_id, "supports_pause")
            if run.status != "running":
                raise InvalidStateError(f"Only running runs can be paused (run is {run.status})")
            ex.set_run_status(s, run, "paused", source="api.runs")
            return run.runtime_id

        runtime_id = await self._tx(go)
        self._paused.add(run_id)
        self.registry.get(runtime_id).pause(run_id)  # type: ignore[union-attr]

    async def resume_run(self, run_id: uuid.UUID) -> None:
        def go(s: Session) -> str:
            run = ex.get_run(s, run_id)
            self._runtime_for(run.runtime_id, "supports_resume")
            if run.status != "paused":
                raise InvalidStateError(f"Only paused runs can be resumed (run is {run.status})")
            ex.set_run_status(s, run, "running", source="api.runs")
            return run.runtime_id

        runtime_id = await self._tx(go)
        self._paused.discard(run_id)
        self.registry.get(runtime_id).resume(run_id)  # type: ignore[union-attr]

    async def shutdown(self) -> None:
        jobs = [*self._loops.values()] + [j for d in self._roots.values() for j in d.values()]
        for t in jobs:
            t.cancel()
        for t in jobs:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t

    async def recover(self) -> None:
        def go(s: Session) -> tuple[int, int, list[uuid.UUID]]:
            n = ex.fail_interrupted_runs(s)
            expired = approvals.expire_all_pending(s)
            companies = list(
                s.scalars(
                    select(Task.company_id)
                    .where(Task.status == "pending", Task.parent_task_id.is_(None))
                    .distinct()
                )
            )
            return n, expired, companies

        count, expired, companies = await self._tx(go)
        if count or expired:
            log.warning(
                "Recovery: %d interrupted run(s) failed, %d approval(s) expired", count, expired
            )
        for cid in companies:
            self.kick(cid)

    # ================= execution =================

    async def _execute_task(self, task_id: uuid.UUID, depth: int) -> Outcome:
        attempt = 0
        while True:
            attempt += 1

            def prepare(s: Session, attempt: int = attempt) -> tuple | Outcome:
                task = ex.get_task(s, task_id)
                if task.status == "cancelled":
                    return "cancelled"
                agent = s.get(Agent, task.assigned_agent_id) if task.assigned_agent_id else None
                if agent is None or agent.status != "active":
                    ex.set_task_status(s, task, "failed")
                    return "failed"
                ctx = dict(task.context_json or {})
                run = ex.create_run(
                    s, task, agent, input_json=ctx, correlation_id=None, attempt=attempt
                )
                version = s.get(AgentVersion, run.agent_version_id)
                assert version is not None
                settings = dict(version.runtime_preference_json.get("settings") or {})
                handle, preflight = self._credential_for(s, run.runtime_id, settings, task)
                req = RunRequest(
                    run_id=run.id,
                    agent={
                        "id": str(agent.id),
                        "name": agent.name,
                        "role": agent.role,
                        "definition": version.definition_json,
                    },
                    task={"id": str(task.id), "title": task.title, "description": task.description},
                    context=ctx,
                    attempt=attempt,
                    tools=self.gateway.port(run.id, None),
                    settings=settings,
                    tool_specs=self._tool_specs(s, agent),
                    credential=handle,
                )
                return run.id, req, task.max_attempts, ctx, preflight

            prepared = await self._tx(prepare)
            if isinstance(prepared, str):
                return prepared  # type: ignore[return-value]
            run_id, req, max_attempts, ctx, preflight = prepared
            if preflight is not None:
                code, msg = preflight
                await self._tx(
                    lambda s, r=run_id, c=code, m=msg: ex.finish_run(
                        s,
                        ex.get_run(s, r),
                        ok=False,
                        error_code=c,
                        error_summary=m,
                        source="orchestrator",
                    )
                )
                return "failed"
            outcome, retry = await self._run_once(
                run_id, req, ctx, depth, can_retry=attempt < max_attempts
            )
            if not retry:
                return outcome
            delay_ms = self.c.settings.retry_backoff_ms * (2 ** (attempt - 1))
            await self._tx(
                lambda s, r=run_id, d=delay_ms: ex.record_retry_scheduled(
                    s, ex.get_run(s, r), d, None
                )
            )
            await asyncio.sleep(delay_ms / 1000)

    async def _run_once(
        self, run_id: uuid.UUID, req: RunRequest, ctx: dict, depth: int, can_retry: bool
    ) -> tuple[Outcome, bool]:
        """Consume one runtime stream. Returns (outcome, should_retry)."""

        def fail(code: str, summary: str) -> Callable[[Session], None]:
            def _f(s: Session) -> None:
                ex.finish_run(
                    s,
                    ex.get_run(s, run_id),
                    ok=False,
                    error_code=code,
                    error_summary=summary,
                    source="orchestrator",
                )

            return _f

        def cancelled(s: Session) -> None:
            ex.cancel_run_record(s, ex.get_run(s, run_id), source="orchestrator")

        runtime_id = await self._tx(lambda s: ex.get_run(s, run_id).runtime_id)
        runtime = self.registry.get(runtime_id)
        if runtime is None:
            await self._tx(fail("RUNTIME_UNAVAILABLE", f"Runtime '{runtime_id}' not registered"))
            return "failed", False

        stream = runtime.execute(req)
        started = False
        try:
            async for raw in stream:
                # Forward control requests that arrived before the runtime was listening.
                if run_id in self._cancel and hasattr(runtime, "cancel"):
                    runtime.cancel(run_id)
                elif run_id in self._paused and hasattr(runtime, "pause"):
                    runtime.pause(run_id)
                try:
                    ev = normalize.validate(raw)
                except normalize.RuntimeProtocolError as exc:
                    await self._tx(fail("RUNTIME_PROTOCOL_ERROR", str(exc)))
                    return "failed", False

                if not started:
                    await self._tx(
                        lambda s: (
                            ex.mark_started(s, ex.get_run(s, run_id), None)
                            if ex.get_run(s, run_id).status == "queued"
                            else None
                        )
                    )
                    started = True

                match ev:
                    case normalize.Started():
                        pass
                    case normalize.Progress():
                        await self._tx(
                            lambda s, e=ev: ex.record_progress(
                                s, ex.get_run(s, run_id), e.message, e.step, e.total_steps, None
                            )
                        )
                    case normalize.Message():
                        await self._tx(
                            lambda s, e=ev: ex.record_message(
                                s, ex.get_run(s, run_id), e.text, None
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
                                correlation_id=None,
                            )
                        )
                    case normalize.Usage():
                        await self._tx(
                            lambda s, e=ev: metrics.record_usage(
                                s, ex.get_run(s, run_id), e, load_prices()
                            )
                        )
                    case normalize.LessonProposed():
                        await self._tx(lambda s, e=ev: self._lesson(s, run_id, e))
                    case normalize.RoleChangeProposed():
                        await self._tx(lambda s, e=ev: self._role_change(s, run_id, e))
                    case normalize.DelegationRequested() | normalize.ParallelDelegation():
                        if depth >= MAX_DELEGATION_DEPTH:
                            await self._tx(
                                fail(
                                    "DELEGATION_TOO_DEEP",
                                    f"Delegation depth exceeds {MAX_DELEGATION_DEPTH}",
                                )
                            )
                            return "failed", False
                        reqs = ev.tasks if isinstance(ev, normalize.ParallelDelegation) else [ev]
                        child_ids = await self._tx(
                            lambda s, r=reqs: [self._delegate(s, run_id, d, ctx) for d in r]
                        )
                        outcomes = await asyncio.gather(
                            *(self._execute_task(cid, depth + 1) for cid in child_ids)
                        )
                        if run_id in self._cancel:
                            await self._tx(cancelled)
                            return "cancelled", False
                        bad = [
                            (o, d) for o, d in zip(outcomes, reqs, strict=True) if o != "completed"
                        ]
                        if bad:
                            o, d = bad[0]
                            code = (
                                "CHILD_TASK_CANCELLED" if o == "cancelled" else "CHILD_TASK_FAILED"
                            )
                            verb = "was cancelled" if o == "cancelled" else "failed"
                            await self._tx(
                                fail(code, f"Delegated task '{d.title}' ({d.to_role}) {verb}")
                            )
                            return "failed", False
                    case normalize.Completed():
                        if run_id in self._cancel:
                            await self._tx(cancelled)
                            return "cancelled", False
                        await self._tx(
                            lambda s, e=ev: ex.finish_run(
                                s, ex.get_run(s, run_id), ok=True, summary=e.summary
                            )
                        )
                        return "completed", False
                    case normalize.Cancelled():
                        await self._tx(cancelled)
                        return "cancelled", False
                    case normalize.Failed():
                        if run_id in self._cancel:
                            await self._tx(cancelled)
                            return "cancelled", False
                        retry = ev.retryable and can_retry
                        await self._tx(
                            lambda s, e=ev, r=retry: ex.finish_run(
                                s,
                                ex.get_run(s, run_id),
                                ok=False,
                                error_code=e.error_code,
                                error_summary=e.error_summary,
                                retryable=e.retryable,
                                final=not r,
                            )
                        )
                        return "failed", retry
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # runtime crashed: report, never fake success
            log.error("Runtime error in run %s: %s", run_id, redact(repr(exc)))
            await self._tx(fail("RUNTIME_ERROR", f"Runtime raised {type(exc).__name__}"))
            return "failed", False
        finally:
            self._cancel.discard(run_id)
            self._paused.discard(run_id)
            await stream.aclose()  # type: ignore[attr-defined]

        await self._tx(fail("RUNTIME_PROTOCOL_ERROR", "Runtime ended without a terminal event"))
        return "failed", False

    def _credential_for(
        self, s: Session, runtime_id: str, settings: dict, task: Task
    ) -> tuple[object | None, tuple[str, str] | None]:
        """Resolve the agent's credential reference (ADR-0021). Never reads the secret here."""
        rt = self.registry.get(runtime_id)
        provider = getattr(rt, "provider", None)
        if rt is None or not getattr(rt, "requires_credential", False) or provider is None:
            return None, None
        raw = settings.get("credential_id")
        if not raw:
            return None, ("CREDENTIAL_MISSING", f"Agent chưa được gán credential cho {provider}")
        try:
            c = creds.get(s, uuid.UUID(str(raw)))
        except (ValueError, NotFoundError):
            return None, ("CREDENTIAL_MISSING", "Credential của agent không còn tồn tại")
        problem = creds.check_usable(c, provider, task.company_id)
        if problem is not None:
            return None, problem
        if self.secrets is None:
            return None, ("CREDENTIAL_MISSING", "Kho secret chưa được cấu hình")
        return creds.handle(c, self.secrets), None

    def _tool_specs(self, s: Session, agent: Agent) -> list[dict]:
        """Tools this agent may actually use right now (granted, under ceiling, implemented)."""
        specs = []
        for t in caps.list_tools(s, agent.company_id):
            if t.key not in EXECUTORS or not caps.decide(s, agent, t).allowed:
                continue
            specs.append(
                {
                    "key": t.key,
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema_json or {},
                }
            )
        return specs

    def _delegate(
        self, s: Session, run_id: uuid.UUID, ev: normalize.DelegationRequested, ctx: dict
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
            max_attempts=ev.max_attempts,
            context=ctx,
        )
        ex.record_delegation(s, run, child, ev.to_role, None)
        return child.id

    def _lesson(self, s: Session, run_id: uuid.UUID, ev: normalize.LessonProposed) -> None:
        run = ex.get_run(s, run_id)
        kn.propose_lesson(
            s,
            run.company_id,
            LessonCreate(title=ev.title, lesson=ev.lesson, source_task_id=run.task_id),
            proposed_by=f"agent:{run.agent_id}",
            source_run_id=run.id,
        )

    def _role_change(self, s: Session, run_id: uuid.UUID, ev: normalize.RoleChangeProposed) -> None:
        run = ex.get_run(s, run_id)
        try:
            with s.begin_nested():
                data = kn.resolve_runtime_role_change(
                    s, run, ev.target_role, ev.changes.model_dump(exclude_none=True)
                )
                data.rationale = ev.rationale
                kn.propose_role_change(
                    s,
                    run.company_id,
                    data,
                    proposed_by=f"agent:{run.agent_id}",
                    source_run_id=run.id,
                )
        except AppError as exc:
            ex.record_message(s, run, f"Đề xuất đổi vai trò không hợp lệ: {exc}", None)


def run_is_terminal(run: AgentRun) -> bool:
    return run.status in RUN_TERMINAL
