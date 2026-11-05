"""Lease broker between the orchestrator and worker processes (ADR-0025).

Live lease state is in memory (single control-plane process); `worker_leases` keeps the record.
Guarantee: a run handed to a worker ends `completed` only when that worker sends
`run.completed` on a live lease. Lost heartbeat, revocation, restart or timeout -> failed.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.api.deps import Container
from orchestra_backend.core.errors import AppError, DomainValidationError
from orchestra_backend.core.time import utcnow
from orchestra_backend.runtime import normalize
from orchestra_backend.runtime.interface import RunRequest, RuntimeEvent, ToolPort
from orchestra_backend.workers import service as wsvc
from orchestra_backend.workers.models import WorkerLease

log = logging.getLogger("orchestra.workers")
T = TypeVar("T")
TERMINAL = {"run.completed", "run.failed", "run.cancelled"}
OPEN = {"pending", "active"}


class LeaseClosed(AppError):
    status_code = 409
    code = "LEASE_CLOSED"


class LeaseNotYours(AppError):
    status_code = 403
    code = "LEASE_NOT_YOURS"


class SeqError(AppError):
    status_code = 409
    code = "SEQ_REPLAY"


class EventRejected(AppError):
    status_code = 422
    code = "EVENT_INVALID"


def _ev(t: str, **data: Any) -> RuntimeEvent:
    return RuntimeEvent(type=t, data=data)


@dataclass
class Live:
    lease_id: uuid.UUID
    run_id: uuid.UUID
    runtime_id: str
    pinned: uuid.UUID | None
    payload: dict[str, Any]
    port: ToolPort | None
    deadline: float  # pending: dispatch deadline; active: lease expiry (loop time)
    queue: asyncio.Queue[RuntimeEvent] = field(default_factory=asyncio.Queue)
    status: str = "pending"
    worker_id: uuid.UUID | None = None
    last_seq: int = 0
    started: bool = False


class WorkerHub:
    def __init__(self, container: Container) -> None:
        self.c = container
        st = container.settings
        self.lease_ttl = st.worker_lease_ttl_s
        self.dispatch_timeout = st.worker_dispatch_timeout_s
        self.poll_max = st.worker_poll_max_s
        self._live: dict[uuid.UUID, Live] = {}
        self._by_run: dict[uuid.UUID, uuid.UUID] = {}
        self._signal = asyncio.Event()
        self._sweeper: asyncio.Task[None] | None = None

    # ----- lifecycle -----

    async def start(self) -> None:
        self._signal = asyncio.Event()

        def orphaned(s: Session) -> int:
            rows = list(s.scalars(select(WorkerLease).where(WorkerLease.status.in_(OPEN))))
            for r in rows:
                r.status, r.error_code, r.finished_at = "lost", "INTERRUPTED", utcnow()
            return len(rows)

        n = await self._tx(orphaned)
        if n:
            log.info("Workers: %d lease(s) from a previous run marked lost", n)
        self._sweeper = asyncio.create_task(self._sweep_forever())

    async def stop(self) -> None:
        if self._sweeper:
            self._sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweeper

    async def _tx(self, fn: Callable[[Session], T]) -> T:
        def work() -> T:
            with self.c.tx() as s:
                return fn(s)

        return await asyncio.to_thread(work)

    def _now(self) -> float:
        return asyncio.get_running_loop().time()

    def _notify(self) -> None:
        self._signal.set()
        self._signal = asyncio.Event()

    # ----- orchestrator side -----

    async def dispatch(
        self, req: RunRequest, runtime_id: str, settings: dict[str, Any], pinned: uuid.UUID | None
    ) -> AsyncIterator[RuntimeEvent]:
        available = await self._tx(lambda s: bool(wsvc.active_workers_for(s, runtime_id, pinned)))
        if not available:
            who = "Worker được chọn" if pinned else f"Chưa có worker nào chạy được '{runtime_id}'"
            yield _ev("run.started")
            yield _ev(
                "run.failed",
                error_code="WORKER_UNAVAILABLE",
                error_summary=f"{who} (chưa ghép nối, đã thu hồi hoặc không hỗ trợ runtime này)",
                retryable=False,
            )
            return

        def create(s: Session) -> uuid.UUID:
            row = WorkerLease(run_id=req.run_id, runtime_id=runtime_id, pinned_worker_id=pinned)
            s.add(row)
            s.flush()
            return row.id

        lease_id = await self._tx(create)
        live = Live(
            lease_id=lease_id,
            run_id=req.run_id,
            runtime_id=runtime_id,
            pinned=pinned,
            port=req.tools,
            deadline=self._now() + self.dispatch_timeout,
            payload={
                "lease_id": str(lease_id),
                "run_id": str(req.run_id),
                "runtime_id": runtime_id,
                "settings": settings,
                "agent": req.agent,
                "task": req.task,
                "context": req.context,
                "attempt": req.attempt,
                "tool_specs": req.tool_specs,
            },
        )
        self._live[lease_id] = live
        self._by_run[req.run_id] = lease_id
        self._notify()
        try:
            while True:
                ev = await live.queue.get()
                yield ev
                if ev.type in TERMINAL:
                    return
        finally:
            self._live.pop(lease_id, None)
            self._by_run.pop(req.run_id, None)
            if live.status in OPEN:  # consumer went away (shutdown)
                await self._close(live, "lost", [], "INTERRUPTED")

    async def _close(
        self, live: Live, status: str, events: list[RuntimeEvent], error_code: str | None
    ) -> None:
        if live.status not in OPEN:
            return
        live.status = status
        if events and not live.started:
            live.queue.put_nowait(_ev("run.started"))
            live.started = True
        for e in events:
            live.queue.put_nowait(e)

        def record(s: Session) -> None:
            row = s.get(WorkerLease, live.lease_id)
            if row is not None:
                row.status, row.error_code, row.finished_at = status, error_code, utcnow()
                row.last_seq = live.last_seq

        await self._tx(record)

    def cancel(self, run_id: uuid.UUID) -> None:
        lease_id = self._by_run.get(run_id)
        live = self._live.get(lease_id) if lease_id else None
        if live is not None:
            asyncio.get_running_loop().create_task(
                self._close(live, "cancelled", [_ev("run.cancelled")], None)
            )

    async def revoke_worker(self, worker_id: uuid.UUID) -> int:
        hit = [lv for lv in self._live.values() if lv.worker_id == worker_id and lv.status in OPEN]
        for lv in hit:
            await self._close(
                lv,
                "revoked",
                [
                    _ev(
                        "run.failed",
                        error_code="WORKER_REVOKED",
                        error_summary="Worker bị thu hồi khi đang chạy; run không tính là xong",
                        retryable=True,
                    )
                ],
                "WORKER_REVOKED",
            )
        return len(hit)

    async def _sweep_forever(self) -> None:
        interval = max(0.05, min(1.0, self.lease_ttl / 3))
        while True:
            await asyncio.sleep(interval)
            try:
                await self.sweep()
            except Exception:  # pragma: no cover - keep sweeping
                log.exception("lease sweep failed")

    async def sweep(self) -> None:
        now = self._now()
        for lv in list(self._live.values()):
            if lv.status == "active" and lv.deadline < now:
                await self._close(
                    lv,
                    "lost",
                    [
                        _ev(
                            "run.failed",
                            error_code="WORKER_LOST",
                            error_summary=(
                                f"Mất liên lạc với worker quá {int(self.lease_ttl)} giây; "
                                "run không được tính là xong"
                            ),
                            retryable=True,
                        )
                    ],
                    "WORKER_LOST",
                )
            elif lv.status == "pending" and lv.deadline < now:
                await self._close(
                    lv,
                    "unavailable",
                    [
                        _ev(
                            "run.failed",
                            error_code="WORKER_UNAVAILABLE",
                            error_summary=(
                                f"Không worker nào nhận việc trong "
                                f"{int(self.dispatch_timeout)} giây. Hãy bật worker (pnpm worker)."
                            ),
                            retryable=False,
                        )
                    ],
                    "WORKER_UNAVAILABLE",
                )

    # ----- worker side -----

    def queued_for(self, runtimes: list[str]) -> int:
        return sum(
            1 for lv in self._live.values() if lv.status == "pending" and lv.runtime_id in runtimes
        )

    async def claim(self, worker_id: uuid.UUID, runtimes: list[str], wait_s: float) -> dict | None:
        deadline = self._now() + max(0.0, min(wait_s, self.poll_max))
        while True:
            for lv in self._live.values():
                if (
                    lv.status == "pending"
                    and lv.runtime_id in runtimes
                    and lv.pinned in (None, worker_id)
                ):
                    lv.status, lv.worker_id = "active", worker_id
                    lv.deadline = self._now() + self.lease_ttl

                    def record(s: Session, lv: Live = lv) -> None:
                        row = s.get(WorkerLease, lv.lease_id)
                        if row is not None:
                            row.status, row.worker_id, row.claimed_at = (
                                "active",
                                worker_id,
                                utcnow(),
                            )

                    await self._tx(record)
                    return {**lv.payload, "lease_ttl_s": self.lease_ttl}
            remaining = deadline - self._now()
            if remaining <= 0:
                return None
            signal = self._signal
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(signal.wait(), remaining)

    def _owned(self, worker_id: uuid.UUID, lease_id: uuid.UUID) -> Live:
        lv = self._live.get(lease_id)
        if lv is None or lv.status != "active":
            raise LeaseClosed("Lease đã đóng (hủy, hết hạn hoặc đã xong)")
        if lv.worker_id != worker_id:
            raise LeaseNotYours("Lease thuộc worker khác")
        return lv

    def heartbeat(self, worker_id: uuid.UUID, lease_id: uuid.UUID) -> float:
        lv = self._owned(worker_id, lease_id)
        lv.deadline = self._now() + self.lease_ttl
        return self.lease_ttl

    async def post_events(
        self, worker_id: uuid.UUID, lease_id: uuid.UUID, seq: int, events: list[dict[str, Any]]
    ) -> None:
        lv = self._owned(worker_id, lease_id)
        if seq <= lv.last_seq:
            raise SeqError(f"Lô sự kiện {seq} đã nhận rồi", details={"last_seq": lv.last_seq})
        if seq != lv.last_seq + 1:
            raise SeqError(
                f"Thiếu lô sự kiện trước {seq}", code="SEQ_GAP", details={"last_seq": lv.last_seq}
            )
        parsed: list[RuntimeEvent] = []
        for i, raw in enumerate(events):
            t = str(raw.get("type", ""))
            data = dict(raw.get("data") or {})
            if t == "run.artifact.produced":
                digest = data.pop("sha256", None)
                content = data.get("content")
                if not isinstance(content, str):
                    raise EventRejected("Artifact thiếu nội dung")
                body = content.encode("utf-8")
                if len(body) > normalize.MAX_ARTIFACT_BYTES:
                    raise EventRejected("Artifact vượt 1 MB", code="ARTIFACT_TOO_LARGE")
                if digest != hashlib.sha256(body).hexdigest():
                    raise EventRejected("Checksum artifact không khớp", code="ARTIFACT_CHECKSUM")
            ev = RuntimeEvent(type=t, data=data)
            try:
                normalize.validate(ev)
            except normalize.RuntimeProtocolError as exc:
                raise EventRejected(f"Sự kiện {i} không hợp lệ: {exc}") from exc
            if t in TERMINAL and i != len(events) - 1:
                raise EventRejected("Sự kiện kết thúc phải nằm cuối lô")
            parsed.append(ev)
        lv.last_seq = seq
        lv.deadline = self._now() + self.lease_ttl
        for ev in parsed:
            if ev.type == "run.started":
                if lv.started:
                    continue
                lv.started = True
            elif not lv.started:
                lv.queue.put_nowait(_ev("run.started"))
                lv.started = True
            lv.queue.put_nowait(ev)
        if parsed and parsed[-1].type in TERMINAL:
            await self._close(lv, "finished", [], parsed[-1].data.get("error_code"))

    async def tool_call(
        self, worker_id: uuid.UUID, lease_id: uuid.UUID, key: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        lv = self._owned(worker_id, lease_id)
        if lv.port is None:
            raise DomainValidationError("Run này không có tool", code="NO_TOOLS")
        res = await lv.port.call(key, params)
        return {
            "ok": res.ok,
            "data": res.data,
            "error_code": res.error_code,
            "error_summary": res.error_summary,
        }

    def live_counts(self) -> dict[uuid.UUID, int]:
        out: dict[uuid.UUID, int] = {}
        for lv in self._live.values():
            if lv.status == "active" and lv.worker_id:
                out[lv.worker_id] = out.get(lv.worker_id, 0) + 1
        return out
