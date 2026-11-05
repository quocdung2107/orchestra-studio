"""Synchronous, transactional domain operations for tasks, runs and artifacts.

Every function runs inside the caller's transaction and appends its events there (ADR-0006).
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.agents.models import Agent, AgentVersion
from orchestra_backend.core.errors import DomainValidationError, InvalidStateError, NotFoundError
from orchestra_backend.core.time import utcnow
from orchestra_backend.events.catalog import (
    ArtifactCreated,
    RunCompleted,
    RunDelegated,
    RunFailed,
    RunMessage,
    RunProgress,
    RunQueued,
    RunRef,
    RunRetryScheduled,
    RunStatusChanged,
    TaskAssigned,
    TaskCreated,
    TaskDependencyAdded,
    TaskRef,
    TaskStatusChanged,
)
from orchestra_backend.events.service import append_event
from orchestra_backend.execution.models import (
    RUN_TERMINAL,
    TASK_ACTIVE,
    TASK_TERMINAL,
    AgentRun,
    Artifact,
    Task,
    TaskDependency,
)

SOURCE = "orchestrator"


# ---------- tasks ----------


def find_agent_for_role(session: Session, company_id: uuid.UUID, role: str) -> Agent | None:
    return session.scalar(
        select(Agent)
        .where(Agent.company_id == company_id, Agent.role == role, Agent.status == "active")
        .order_by(Agent.created_at)
        .limit(1)
    )


def create_task(
    session: Session,
    *,
    company_id: uuid.UUID,
    title: str,
    description: str,
    required_role: str | None,
    created_by: str,
    parent_task_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
    assigned_agent_id: uuid.UUID | None = None,
    max_attempts: int = 1,
    context: dict | None = None,
    priority: int = 0,
) -> Task:
    task = Task(
        company_id=company_id,
        title=title,
        description=description,
        required_role=required_role,
        created_by=created_by,
        parent_task_id=parent_task_id,
        max_attempts=max_attempts,
        context_json=dict(context or {}),
        priority=priority,
    )
    session.add(task)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="task.created",
        source=SOURCE,
        payload=TaskCreated(task_id=task.id, title=title, parent_task_id=parent_task_id),
        correlation_id=correlation_id,
    )
    if assigned_agent_id is not None:
        agent = session.get(Agent, assigned_agent_id)
        if agent is None or agent.company_id != company_id:
            raise DomainValidationError("Assigned agent not found in this company")
        if agent.status == "archived":
            raise InvalidStateError("Assigned agent is archived")
    elif required_role:
        agent = find_agent_for_role(session, company_id, required_role)
    else:
        raise DomainValidationError("Task needs an assigned agent or a required role")
    if agent is not None:
        task.assigned_agent_id = agent.id
        append_event(
            session,
            company_id=company_id,
            event_type="task.assigned",
            source=SOURCE,
            payload=TaskAssigned(task_id=task.id, agent_id=agent.id),
            correlation_id=correlation_id,
        )
    return task


def set_task_status(
    session: Session, task: Task, to_status: str, correlation_id: uuid.UUID | None = None
) -> None:
    if task.status == to_status:
        return
    from_status = task.status
    task.status = to_status
    task.completed_at = utcnow() if to_status in TASK_TERMINAL else None
    append_event(
        session,
        company_id=task.company_id,
        event_type="task.status_changed",
        source=SOURCE,
        payload=TaskStatusChanged(task_id=task.id, from_status=from_status, to_status=to_status),
        correlation_id=correlation_id,
    )


def add_dependency(
    session: Session, task: Task, depends_on_id: uuid.UUID, correlation_id: uuid.UUID | None = None
) -> None:
    """finish_to_start dependency between root tasks; rejects cycles (ADR-0015)."""
    if depends_on_id == task.id:
        raise DomainValidationError("A task cannot depend on itself", code="task_cycle")
    dep = get_task(session, depends_on_id)
    if dep.company_id != task.company_id:
        raise DomainValidationError(
            "Dependency belongs to another company", code="cross_company_link"
        )
    if task.parent_task_id is not None or dep.parent_task_id is not None:
        raise DomainValidationError("Dependencies are only between top-level tasks")
    if task.status != "pending":
        raise InvalidStateError("Dependencies can only be added to pending tasks")
    if session.get(TaskDependency, (task.id, dep.id)) is not None:
        return
    # Cycle check: walk what `dep` depends on; reaching `task` means a loop.
    seen: set[uuid.UUID] = set()
    stack = [dep.id]
    while stack:
        cur = stack.pop()
        if cur == task.id:
            raise DomainValidationError("Dependency would create a cycle", code="task_cycle")
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(
            session.scalars(
                select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == cur)
            )
        )
    session.add(TaskDependency(task_id=task.id, depends_on_task_id=dep.id))
    session.flush()
    append_event(
        session,
        company_id=task.company_id,
        event_type="task.dependency_added",
        source="api.tasks",
        payload=TaskDependencyAdded(task_id=task.id, depends_on_task_id=dep.id),
        correlation_id=correlation_id,
    )


def dependencies_of(session: Session, task_id: uuid.UUID) -> list[Task]:
    return list(
        session.scalars(
            select(Task)
            .join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
            .where(TaskDependency.task_id == task_id)
        )
    )


def ready_root_tasks(session: Session, company_id: uuid.UUID) -> list[Task]:
    """Pending top-level tasks whose dependencies all completed (ADR-0015)."""
    pending = session.scalars(
        select(Task)
        .where(
            Task.company_id == company_id,
            Task.status == "pending",
            Task.parent_task_id.is_(None),
        )
        .order_by(Task.priority.desc(), Task.created_at)
    )
    return [
        t for t in pending if all(d.status == "completed" for d in dependencies_of(session, t.id))
    ]


def descendants(session: Session, task: Task) -> list[Task]:
    out: list[Task] = []
    frontier = [task.id]
    while frontier:
        children = list(session.scalars(select(Task).where(Task.parent_task_id.in_(frontier))))
        out.extend(children)
        frontier = [c.id for c in children]
    return out


def request_retry(session: Session, task: Task) -> None:
    if task.parent_task_id is not None:
        raise InvalidStateError("Only top-level tasks can be retried; retry the parent instead")
    if task.status not in {"failed", "cancelled"}:
        raise InvalidStateError("Only failed or cancelled tasks can be retried")
    agent = session.get(Agent, task.assigned_agent_id) if task.assigned_agent_id else None
    if (agent is None or agent.status != "active") and task.required_role:
        agent = find_agent_for_role(session, task.company_id, task.required_role)
        if agent is not None:
            task.assigned_agent_id = agent.id
    append_event(
        session,
        company_id=task.company_id,
        event_type="task.retry_requested",
        source="api.tasks",
        payload=TaskRef(task_id=task.id),
    )
    set_task_status(session, task, "pending")


def get_task(session: Session, task_id: uuid.UUID) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise NotFoundError("Task not found", details={"task_id": str(task_id)})
    return task


def list_tasks(session: Session, company_id: uuid.UUID) -> list[Task]:
    return list(
        session.scalars(select(Task).where(Task.company_id == company_id).order_by(Task.created_at))
    )


# ---------- runs ----------


def create_run(
    session: Session,
    task: Task,
    agent: Agent,
    input_json: dict,
    correlation_id: uuid.UUID | None,
    attempt: int = 1,
) -> AgentRun:
    version = session.get(AgentVersion, agent.current_version_id)
    assert version is not None  # active agents always have a version (agents.service)
    runtime_id = version.runtime_preference_json.get("runtime_id", "mock")
    run = AgentRun(
        company_id=task.company_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        task_id=task.id,
        runtime_id=runtime_id,
        input_json=input_json,
        attempt=attempt,
    )
    session.add(run)
    session.flush()
    append_event(
        session,
        company_id=task.company_id,
        event_type="agent.run.queued",
        source=SOURCE,
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunQueued(run_id=run.id, task_id=task.id, agent_id=agent.id, runtime_id=runtime_id),
    )
    set_task_status(session, task, "in_progress", correlation_id)
    return run


def get_run(session: Session, run_id: uuid.UUID) -> AgentRun:
    run = session.get(AgentRun, run_id)
    if run is None:
        raise NotFoundError("Run not found", details={"run_id": str(run_id)})
    return run


def list_runs(
    session: Session,
    company_id: uuid.UUID,
    *,
    task_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    limit: int = 200,
) -> list[AgentRun]:
    stmt = select(AgentRun).where(AgentRun.company_id == company_id)
    if task_id:
        stmt = stmt.where(AgentRun.task_id == task_id)
    if agent_id:
        stmt = stmt.where(AgentRun.agent_id == agent_id)
    return list(session.scalars(stmt.order_by(AgentRun.created_at.desc()).limit(limit)))


def _source(run: AgentRun) -> str:
    return f"runtime.{run.runtime_id}"


def mark_started(session: Session, run: AgentRun, correlation_id: uuid.UUID | None) -> None:
    run.status = "running"
    run.started_at = utcnow()
    append_event(
        session,
        company_id=run.company_id,
        event_type="agent.run.started",
        source=_source(run),
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunRef(run_id=run.id),
    )


def record_progress(
    session: Session,
    run: AgentRun,
    message: str,
    step: int | None,
    total: int | None,
    correlation_id: uuid.UUID | None,
) -> None:
    append_event(
        session,
        company_id=run.company_id,
        event_type="agent.run.progress",
        source=_source(run),
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunProgress(run_id=run.id, message=message, step=step, total_steps=total),
    )


def record_message(
    session: Session, run: AgentRun, text: str, correlation_id: uuid.UUID | None
) -> None:
    append_event(
        session,
        company_id=run.company_id,
        event_type="agent.run.message",
        source=_source(run),
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunMessage(run_id=run.id, text=text),
    )


def record_delegation(
    session: Session, run: AgentRun, child: Task, to_role: str, correlation_id: uuid.UUID | None
) -> None:
    append_event(
        session,
        company_id=run.company_id,
        event_type="agent.run.delegated",
        source=_source(run),
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunDelegated(run_id=run.id, child_task_id=child.id, to_role=to_role),
    )


def set_run_status(
    session: Session,
    run: AgentRun,
    to_status: str,
    correlation_id: uuid.UUID | None = None,
    source: str = SOURCE,
) -> None:
    """Non-terminal transitions: running <-> paused/waiting_approval, cancel_requested."""
    if run.status == to_status or run.status in RUN_TERMINAL:
        return
    from_status = run.status
    run.status = to_status
    append_event(
        session,
        company_id=run.company_id,
        event_type="agent.run.status_changed",
        source=source,
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunStatusChanged(run_id=run.id, from_status=from_status, to_status=to_status),
    )
    task = session.get(Task, run.task_id) if run.task_id else None
    if task is not None and task.status in TASK_ACTIVE:
        mapped = {"running": "in_progress", "cancel_requested": task.status}.get(
            to_status, to_status
        )
        if mapped in TASK_ACTIVE:
            set_task_status(session, task, mapped, correlation_id)


def cancel_run_record(
    session: Session, run: AgentRun, correlation_id: uuid.UUID | None = None, source: str = SOURCE
) -> None:
    if run.status in RUN_TERMINAL:
        return
    run.status = "cancelled"
    run.finished_at = utcnow()
    run.error_code = "CANCELLED"
    run.error_summary = "Cancelled by user"
    append_event(
        session,
        company_id=run.company_id,
        event_type="agent.run.cancelled",
        source=source,
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunRef(run_id=run.id),
    )
    task = session.get(Task, run.task_id) if run.task_id else None
    if task is not None:
        set_task_status(session, task, "cancelled", correlation_id)


def record_retry_scheduled(
    session: Session, run: AgentRun, delay_ms: int, correlation_id: uuid.UUID | None
) -> None:
    assert run.task_id is not None
    append_event(
        session,
        company_id=run.company_id,
        event_type="agent.run.retry_scheduled",
        source=SOURCE,
        run_id=run.id,
        correlation_id=correlation_id,
        payload=RunRetryScheduled(
            task_id=run.task_id,
            failed_run_id=run.id,
            next_attempt=run.attempt + 1,
            delay_ms=delay_ms,
        ),
    )


def finish_run(
    session: Session,
    run: AgentRun,
    *,
    ok: bool,
    summary: str = "",
    error_code: str = "",
    error_summary: str = "",
    retryable: bool = False,
    correlation_id: uuid.UUID | None = None,
    source: str | None = None,
    final: bool = True,
) -> None:
    """`final=False` keeps the task active because another attempt follows (ADR-0016)."""
    if run.status in RUN_TERMINAL:
        return
    run.finished_at = utcnow()
    task = session.get(Task, run.task_id) if run.task_id else None
    if ok:
        run.status = "completed"
        run.result_summary = summary
        append_event(
            session,
            company_id=run.company_id,
            event_type="agent.run.completed",
            source=source or _source(run),
            run_id=run.id,
            correlation_id=correlation_id,
            payload=RunCompleted(run_id=run.id, summary=summary),
        )
    else:
        run.status = "failed"
        run.error_code = error_code
        run.error_summary = error_summary
        append_event(
            session,
            company_id=run.company_id,
            event_type="agent.run.failed",
            source=source or _source(run),
            run_id=run.id,
            correlation_id=correlation_id,
            payload=RunFailed(
                run_id=run.id,
                error_code=error_code,
                error_summary=error_summary,
                retryable=retryable,
            ),
        )
    if task is not None and final:
        set_task_status(session, task, "completed" if ok else "failed", correlation_id)


# ---------- artifacts ----------


def store_artifact(
    session: Session,
    run: AgentRun,
    *,
    name: str,
    mime_type: str,
    content: str,
    artifacts_dir: Path,
    correlation_id: uuid.UUID | None,
) -> Artifact:
    data = content.encode("utf-8")
    artifact_id = uuid.uuid4()
    rel = Path(str(run.company_id)) / f"{artifact_id}.bin"
    target = artifacts_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    artifact = Artifact(
        id=artifact_id,
        company_id=run.company_id,
        task_id=run.task_id,
        run_id=run.id,
        name=name,
        mime_type=mime_type,
        size_bytes=len(data),
        storage_uri=f"local:{rel.as_posix()}",
        checksum="sha256:" + hashlib.sha256(data).hexdigest(),
    )
    session.add(artifact)
    session.flush()
    append_event(
        session,
        company_id=run.company_id,
        event_type="artifact.created",
        source=_source(run),
        run_id=run.id,
        correlation_id=correlation_id,
        payload=ArtifactCreated(
            artifact_id=artifact.id,
            run_id=run.id,
            task_id=run.task_id,
            name=name,
            mime_type=mime_type,
            size_bytes=len(data),
        ),
    )
    return artifact


def get_artifact(session: Session, artifact_id: uuid.UUID) -> Artifact:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise NotFoundError("Artifact not found", details={"artifact_id": str(artifact_id)})
    return artifact


def read_artifact(artifact: Artifact, artifacts_dir: Path) -> bytes:
    if not artifact.storage_uri.startswith("local:"):
        raise NotFoundError("Artifact content not available locally")
    root = artifacts_dir.resolve()
    path = (root / artifact.storage_uri.removeprefix("local:")).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise NotFoundError("Artifact content missing")
    data = path.read_bytes()
    if "sha256:" + hashlib.sha256(data).hexdigest() != artifact.checksum:
        raise NotFoundError("Artifact content failed integrity check", code="integrity_error")
    return data


def list_artifacts_for_run(session: Session, run_id: uuid.UUID) -> list[Artifact]:
    return list(
        session.scalars(
            select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)
        )
    )


# ---------- recovery ----------


def fail_interrupted_runs(session: Session) -> int:
    """After a restart, runs that were in flight cannot have finished. Report them honestly."""
    runs = list(session.scalars(select(AgentRun).where(AgentRun.status.not_in(RUN_TERMINAL))))
    for run in runs:
        finish_run(
            session,
            run,
            ok=False,
            error_code="INTERRUPTED",
            error_summary="Backend stopped while the run was in progress",
            source="orchestrator.recovery",
        )
    # Tasks left active without a live run (e.g. parents) are failed too.
    for task in session.scalars(select(Task).where(Task.status.in_(TASK_ACTIVE))):
        set_task_status(session, task, "failed")
    return len(runs)
