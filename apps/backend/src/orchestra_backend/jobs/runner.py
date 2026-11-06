"""Durable job runner: SQLite `jobs` table + one asyncio loop (ADR-0029)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Protocol

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from orchestra_backend.api.deps import Container
from orchestra_backend.core.errors import AppError, InvalidStateError, NotFoundError
from orchestra_backend.core.time import utcnow
from orchestra_backend.events.service import append_event
from orchestra_backend.jobs.engines import EngineManager, EngineUnavailable
from orchestra_backend.jobs.models import JOB_TERMINAL, Job
from orchestra_backend.jobs.scheduler import ResourceReq, ResourceScheduler

log = logging.getLogger(__name__)

MAX_DEFERRALS = 120  # x DEFER_S seconds of waiting for memory before giving up
DEFER_S = 5.0


class JobError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class JobCancelled(Exception):
    pass


@dataclass
class JobContext:
    job_id: uuid.UUID
    company_id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    attempt: int
    container: Container
    engine_url: str | None = None
    _cancel: Callable[[], bool] = field(default=lambda: False)
    _progress: Callable[[float, str], None] = field(default=lambda p, n: None)

    def progress(self, pct: float, note: str = "") -> None:
        self._progress(pct, note)

    def check_cancelled(self) -> None:
        if self._cancel():
            raise JobCancelled()


class JobHandler(Protocol):
    kind: str

    def resources(self, job: Job, container: Container) -> ResourceReq: ...

    def run(self, ctx: JobContext) -> dict[str, Any]: ...


def _event(s: Session, job: Job) -> None:
    append_event(
        s,
        company_id=job.company_id,
        event_type="job.status_changed",
        payload={
            "job_id": str(job.id),
            "kind": job.kind,
            "status": job.status,
            "subject_id": str(job.subject_id) if job.subject_id else None,
            "error_code": job.error_code,
        },
        source="jobs",
    )


def enqueue(
    s: Session,
    *,
    company_id: uuid.UUID,
    kind: str,
    payload: dict[str, Any],
    subject_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    priority: int = 0,
    max_attempts: int = 2,
) -> Job:
    """Insert a job; with an idempotency key an existing job is returned instead."""
    if idempotency_key:
        existing = s.scalar(
            select(Job).where(Job.company_id == company_id, Job.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
    job = Job(
        company_id=company_id,
        kind=kind,
        payload_json=payload,
        subject_id=subject_id,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
    )
    try:
        with s.begin_nested():
            s.add(job)
            s.flush()
    except IntegrityError:
        existing = s.scalar(
            select(Job).where(Job.company_id == company_id, Job.idempotency_key == idempotency_key)
        )
        assert existing is not None
        return existing
    _event(s, job)
    return job


def retry_job(s: Session, job: Job) -> Job:
    if job.status not in ("failed", "cancelled"):
        raise InvalidStateError(
            "Chỉ chạy lại được job đã lỗi hoặc đã hủy", code="job_not_retryable"
        )
    job.status = "queued"
    job.attempts = 0
    job.deferrals = 0
    job.error = None
    job.error_code = None
    job.cancel_requested = False
    job.next_run_at = utcnow()
    _event(s, job)
    return job


def cancel_job(s: Session, job: Job) -> Job:
    if job.status in JOB_TERMINAL:
        return job
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = utcnow()
        _event(s, job)
    else:
        job.cancel_requested = True
    return job


def get_job(s: Session, job_id: uuid.UUID) -> Job:
    job = s.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found", code="job_not_found")
    return job


class JobRunner:
    def __init__(
        self,
        container: Container,
        scheduler: ResourceScheduler,
        engines: EngineManager,
        *,
        lease_s: float = 120.0,
        poll_s: float = 1.0,
        retry_backoff_s: float = 2.0,
    ):
        self.c = container
        self.scheduler = scheduler
        self.engines = engines
        self.lease_s = lease_s
        self.poll_s = poll_s
        self.retry_backoff_s = retry_backoff_s
        self.handlers: dict[str, JobHandler] = {}
        self._tasks: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._loop_task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._stopping = False
        self.after_finish: list[Callable[[Session, Job], None]] = []

    def register(self, handler: JobHandler) -> None:
        self.handlers[handler.kind] = handler

    # -- lifecycle --------------------------------------------------------------
    def recover(self) -> int:
        """Put jobs left `running` by a previous process back in the queue."""
        with self.c.tx() as s:
            rows = list(s.scalars(select(Job).where(Job.status == "running")))
            for job in rows:
                job.status = "queued"
                job.lease_until = None
                job.next_run_at = utcnow()
                job.progress_note = "Tiếp tục sau khi khởi động lại"
                _event(s, job)
            return len(rows)

    async def start(self) -> None:
        self.recover()
        self._stopping = False
        self._loop_task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        for t in list(self._tasks.values()):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self.engines.shutdown()

    def wake(self) -> None:
        try:
            self._wake.set()
        except RuntimeError:
            pass

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self.tick()
            except Exception:
                log.exception("job runner tick failed")
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.poll_s)
            except TimeoutError:
                pass

    async def drain(self, timeout: float = 60.0) -> None:
        """Run until nothing is runnable now (tests, CLI)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            started = await self.tick()
            if self._tasks:
                await asyncio.wait(list(self._tasks.values()), return_when=asyncio.FIRST_COMPLETED)
                continue
            if started == 0 and not self._has_runnable():
                return
            await asyncio.sleep(0.01)
        raise TimeoutError("jobs still running")

    def _has_runnable(self) -> bool:
        with self.c.tx() as s:
            return (
                s.scalar(
                    select(Job.id)
                    .where(Job.status == "queued", Job.next_run_at <= utcnow())
                    .where(Job.kind.in_(list(self.handlers)))
                    .limit(1)
                )
                is not None
            )

    # -- scheduling -------------------------------------------------------------
    async def tick(self) -> int:
        self.engines.reap_expired()
        now = utcnow()
        with self.c.tx() as s:
            cands = list(
                s.scalars(
                    select(Job)
                    .where(Job.status == "queued", Job.next_run_at <= now)
                    .where(Job.kind.in_(list(self.handlers)))
                    .order_by(Job.priority.desc(), Job.created_at)
                    .limit(50)
                )
            )
        # Prefer jobs whose engine is already loaded: batch work per engine (ADR-0029).
        cands.sort(key=lambda j: (-j.priority, not (j.engine and self.engines.is_warm(j.engine))))
        started = 0
        for job in cands:
            if job.id in self._tasks:
                continue
            handler = self.handlers[job.kind]
            try:
                req = handler.resources(job, self.c)
            except Exception as exc:  # bad payload: fail fast
                self._finish(job.id, "failed", error=("bad_job", str(exc)))
                continue
            decision, lease = self.scheduler.try_acquire(req)
            if decision == "busy":
                continue
            if decision == "insufficient":
                self._defer(job.id)
                continue
            assert lease is not None
            if not self._claim(job.id, req):
                self.scheduler.release(lease)
                continue
            self._tasks[job.id] = asyncio.create_task(self._execute(job.id, handler, req, lease))
            started += 1
        return started

    def _claim(self, job_id: uuid.UUID, req: ResourceReq) -> bool:
        with self.c.tx() as s:
            res = s.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "queued")
                .values(
                    status="running",
                    attempts=Job.attempts + 1,
                    started_at=utcnow(),
                    lease_until=utcnow() + timedelta(seconds=self.lease_s),
                    engine=req.engine,
                    progress=0.0,
                )
            )
            if res.rowcount != 1:
                return False
            job = s.get(Job, job_id)
            assert job is not None
            s.refresh(job)
            _event(s, job)
            return True

    def _defer(self, job_id: uuid.UUID) -> None:
        with self.c.tx() as s:
            job = s.get(Job, job_id)
            if job is None or job.status != "queued":
                return
            job.deferrals += 1
            job.progress_note = f"Chờ tài nguyên: {self.scheduler.last_reason}"[:300]
            if job.deferrals > MAX_DEFERRALS:
                job.status = "failed"
                job.error_code = "insufficient_resources"
                job.error = self.scheduler.last_reason or "Không đủ RAM/VRAM"
                job.finished_at = utcnow()
                _event(s, job)
                for cb in self.after_finish:
                    cb(s, job)
            else:
                job.next_run_at = utcnow() + timedelta(seconds=DEFER_S)

    # -- execution --------------------------------------------------------------
    async def _execute(
        self, job_id: uuid.UUID, handler: JobHandler, req: ResourceReq, lease: Any
    ) -> None:
        heartbeat = asyncio.create_task(self._heartbeat(job_id))
        try:
            with self.c.tx() as s:
                job = s.get(Job, job_id)
                assert job is not None
                ctx = JobContext(
                    job_id=job.id,
                    company_id=job.company_id,
                    kind=job.kind,
                    payload=dict(job.payload_json),
                    attempt=job.attempts,
                    container=self.c,
                    _cancel=lambda: self._cancel_requested(job_id),
                    _progress=lambda p, n: self._set_progress(job_id, p, n),
                )
            result = await asyncio.to_thread(self._run_handler, handler, ctx, req)
            self._finish(job_id, "succeeded", result=result)
        except JobCancelled:
            self._finish(job_id, "cancelled")
        except asyncio.CancelledError:
            # Shutdown: leave it `running`; recover() requeues it on next start.
            raise
        except JobError as exc:
            self._fail_or_retry(job_id, exc.code, exc.message, exc.retryable)
        except EngineUnavailable as exc:
            self._fail_or_retry(job_id, exc.code, exc.message, False)
        except AppError as exc:
            self._fail_or_retry(job_id, exc.code, exc.message, False)
        except Exception as exc:
            log.exception("job %s crashed", job_id)
            self._fail_or_retry(job_id, "internal_error", f"{type(exc).__name__}: {exc}", True)
        finally:
            heartbeat.cancel()
            self.scheduler.release(lease)
            self._tasks.pop(job_id, None)
            self.wake()

    def _run_handler(
        self, handler: JobHandler, ctx: JobContext, req: ResourceReq
    ) -> dict[str, Any]:
        if req.engine:
            ctx.engine_url = self.engines.acquire(req.engine)
            try:
                return handler.run(ctx)
            finally:
                self.engines.release(req.engine)
        return handler.run(ctx)

    async def _heartbeat(self, job_id: uuid.UUID) -> None:
        while True:
            await asyncio.sleep(max(self.lease_s / 3, 0.05))
            with self.c.tx() as s:
                s.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status == "running")
                    .values(lease_until=utcnow() + timedelta(seconds=self.lease_s))
                )

    def _cancel_requested(self, job_id: uuid.UUID) -> bool:
        with self.c.tx() as s:
            return bool(s.scalar(select(Job.cancel_requested).where(Job.id == job_id)))

    def _set_progress(self, job_id: uuid.UUID, pct: float, note: str) -> None:
        with self.c.tx() as s:
            s.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(progress=max(0.0, min(1.0, pct)), progress_note=note[:300])
            )

    def _fail_or_retry(self, job_id: uuid.UUID, code: str, message: str, retryable: bool) -> None:
        with self.c.tx() as s:
            job = s.get(Job, job_id)
            assert job is not None
            if retryable and job.attempts < job.max_attempts:
                job.status = "queued"
                job.lease_until = None
                job.error_code = code
                job.error = message[:2000]
                job.next_run_at = utcnow() + timedelta(
                    seconds=self.retry_backoff_s * (2 ** (job.attempts - 1))
                )
                _event(s, job)
                return
        self._finish(job_id, "failed", error=(code, message))

    def _finish(
        self,
        job_id: uuid.UUID,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: tuple[str, str] | None = None,
    ) -> None:
        with self.c.tx() as s:
            job = s.get(Job, job_id)
            assert job is not None
            job.status = status
            job.finished_at = utcnow()
            job.lease_until = None
            if status == "succeeded":
                job.progress = 1.0
                job.result_json = result or {}
                job.error_code = None
                job.error = None
            if error:
                job.error_code, msg = error
                job.error = msg[:2000]
            _event(s, job)
            for cb in self.after_finish:
                cb(s, job)
