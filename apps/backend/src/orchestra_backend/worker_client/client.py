"""The `orchestra-worker` process (ADR-0025).

Connects *out* to the control plane, takes one lease at a time, runs it with a local runtime
(mock or ollama), streams events with sequence numbers, proxies tool calls, and heartbeats.
Holds no control-plane secrets; its own secret lives in the OS store.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import platform
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2

from orchestra_backend import __version__
from orchestra_backend.core.config import LOOPBACK_HOST, Settings
from orchestra_backend.credentials.store import make_store
from orchestra_backend.runtime.interface import RunRequest, RuntimeEvent, ToolResult
from orchestra_backend.runtime.llm.ollama_rt import OllamaRuntime
from orchestra_backend.runtime.mock.runtime import MockRuntime

log = logging.getLogger("orchestra.worker")
TERMINAL = {"run.completed", "run.failed", "run.cancelled"}


class WorkerError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message = status, code, message


class NotPaired(Exception):
    pass


@dataclass
class Identity:
    server_url: str
    worker_id: uuid.UUID
    name: str


def identity_file(settings: Settings) -> Path:
    return settings.data_dir / "worker" / "worker.json"


def secret_ref(worker_id: uuid.UUID) -> str:
    return f"worker:{worker_id}"


def default_server(settings: Settings) -> str:
    return f"http://{LOOPBACK_HOST}:{settings.port}"


def load_identity(settings: Settings) -> Identity:
    p = identity_file(settings)
    if not p.is_file():
        raise NotPaired(
            "Worker chưa ghép nối. Tạo mã ở mục Workers rồi chạy: pnpm worker pair <MÃ>"
        )
    d = json.loads(p.read_text(encoding="utf-8"))
    return Identity(d["server_url"], uuid.UUID(d["worker_id"]), d.get("name", ""))


class ControlPlane:
    """HTTP client for /api/v1/worker/*. Refreshes its access token before it expires."""

    def __init__(
        self,
        server_url: str,
        *,
        worker_id: uuid.UUID | None = None,
        secret: str | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        kw: dict[str, Any] = {"base_url": server_url.rstrip("/") + "/api/v1/worker", "timeout": 30}
        if transport is not None:
            kw["transport"] = transport
        self.http = httpx2.AsyncClient(**kw)
        self.worker_id, self.secret = worker_id, secret
        self._token: str | None = None
        self._token_until = 0.0

    async def close(self) -> None:
        await self.http.aclose()

    @staticmethod
    def _raise(r: httpx2.Response) -> None:
        if r.status_code < 400:
            return
        try:
            err = r.json().get("error") or {}
        except ValueError:
            err = {}
        raise WorkerError(r.status_code, err.get("code", "http_error"), err.get("message", r.text))

    async def enroll(self, code: str, runtimes: list[str]) -> dict[str, Any]:
        r = await self.http.post(
            "/enroll",
            json={
                "code": code,
                "hostname": socket.gethostname(),
                "platform": f"{platform.system()} {platform.release()}",
                "version": __version__,
                "runtimes": runtimes,
            },
        )
        self._raise(r)
        return r.json()

    async def _auth(self) -> dict[str, str]:
        loop = asyncio.get_running_loop()
        if self._token is None or loop.time() > self._token_until:
            r = await self.http.post(
                "/token", json={"worker_id": str(self.worker_id), "worker_secret": self.secret}
            )
            self._raise(r)
            d = r.json()
            self._token = d["access_token"]
            self._token_until = loop.time() + max(1.0, d["expires_in"] * 0.8)
        return {"Authorization": f"Bearer {self._token}"}

    async def call(self, method: str, path: str, **kw: Any) -> httpx2.Response:
        for attempt in (1, 2):
            r = await self.http.request(method, path, headers=await self._auth(), **kw)
            if r.status_code == 401 and attempt == 1:
                self._token = None  # expired early or server restarted: re-authenticate once
                continue
            self._raise(r)
            return r
        raise AssertionError("unreachable")


class RemoteTools:
    """ToolPort that proxies to the control plane's Tool Gateway."""

    def __init__(self, cp: ControlPlane, lease_id: str) -> None:
        self.cp, self.lease_id = cp, lease_id

    async def call(self, tool_key: str, params: dict[str, Any]) -> ToolResult:
        try:
            r = await self.cp.call(
                "POST",
                f"/leases/{self.lease_id}/tool-calls",
                json={"key": tool_key, "params": params},
                timeout=None,  # an L3 tool may wait for a human approval
            )
        except (WorkerError, httpx2.HTTPError) as exc:
            return ToolResult(
                ok=False, error_code="TOOL_PROXY_FAILED", error_summary=str(exc)[:500]
            )
        d = r.json()
        return ToolResult(
            ok=bool(d.get("ok")),
            data=d.get("data") or {},
            error_code=d.get("error_code"),
            error_summary=d.get("error_summary"),
        )


def _wire(ev: RuntimeEvent) -> dict[str, Any]:
    data = dict(ev.data)
    if ev.type == "run.artifact.produced":
        data["sha256"] = hashlib.sha256(str(data.get("content", "")).encode("utf-8")).hexdigest()
    return {"type": ev.type, "data": data}


class Worker:
    def __init__(self, cp: ControlPlane, runtimes: dict[str, Any], poll_wait_s: float = 20) -> None:
        self.cp = cp
        self.runtimes = runtimes
        self.poll_wait_s = poll_wait_s
        self.stopping = asyncio.Event()

    async def run_forever(self, max_leases: int | None = None) -> None:
        done, backoff = 0, 1.0
        while not self.stopping.is_set():
            try:
                r = await self.cp.call(
                    "GET",
                    "/lease",
                    params={"wait": self.poll_wait_s},
                    timeout=self.poll_wait_s + 15,
                )
                backoff = 1.0
            except WorkerError as exc:
                if exc.code == "WORKER_REVOKED":
                    log.error("Worker đã bị thu hồi; dừng.")
                    return
                raise
            except httpx2.HTTPError as exc:
                log.warning(
                    "Không kết nối được control plane (%s); thử lại sau %.0fs",
                    type(exc).__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15)
                continue
            if r.status_code == 204:
                continue
            await self.run_lease(r.json())
            done += 1
            if max_leases is not None and done >= max_leases:
                return

    async def run_lease(self, lease: dict[str, Any]) -> None:
        lease_id = lease["lease_id"]
        ttl = float(lease.get("lease_ttl_s", 30))
        runtime = self.runtimes.get(lease["runtime_id"])
        run_id = uuid.UUID(lease["run_id"])
        log.info("Nhận lease %s (run %s, %s)", lease_id, run_id, lease["runtime_id"])
        seq = 0
        closed = asyncio.Event()

        async def send(events: list[dict[str, Any]]) -> None:
            nonlocal seq
            seq += 1
            deadline = asyncio.get_running_loop().time() + ttl * 2
            while True:
                try:
                    await self.cp.call(
                        "POST", f"/leases/{lease_id}/events", json={"seq": seq, "events": events}
                    )
                    return
                except WorkerError as exc:
                    if exc.code == "SEQ_REPLAY":
                        return  # an earlier try reached the server
                    if exc.code in ("LEASE_CLOSED", "LEASE_NOT_YOURS", "WORKER_REVOKED"):
                        closed.set()
                        return
                    raise
                except httpx2.HTTPError:
                    if asyncio.get_running_loop().time() > deadline:
                        closed.set()  # the server will have expired the lease by now
                        return
                    await asyncio.sleep(1)

        async def heartbeat() -> None:
            while not closed.is_set():
                await asyncio.sleep(max(0.05, ttl / 3))
                try:
                    await self.cp.call("POST", f"/leases/{lease_id}/heartbeat")
                except WorkerError:
                    closed.set()
                except httpx2.HTTPError:
                    pass  # keep trying; the server decides when the lease is lost

        if runtime is None:
            await send(
                [
                    {"type": "run.started", "data": {}},
                    {
                        "type": "run.failed",
                        "data": {
                            "error_code": "RUNTIME_UNAVAILABLE",
                            "error_summary": f"Worker không có runtime '{lease['runtime_id']}'",
                            "retryable": False,
                        },
                    },
                ]
            )
            return

        req = RunRequest(
            run_id=run_id,
            agent=lease["agent"],
            task=lease["task"],
            context=lease.get("context") or {},
            attempt=int(lease.get("attempt", 1)),
            tools=RemoteTools(self.cp, lease_id),
            settings=lease.get("settings") or {},
            tool_specs=lease.get("tool_specs") or [],
        )
        hb = asyncio.create_task(heartbeat())
        stream = runtime.execute(req)
        try:
            async for ev in stream:
                if closed.is_set() or self.stopping.is_set():
                    break
                await send([_wire(ev)])
                if ev.type in TERMINAL:
                    break
            if self.stopping.is_set() and not closed.is_set():
                await send(
                    [
                        {
                            "type": "run.failed",
                            "data": {
                                "error_code": "WORKER_STOPPED",
                                "error_summary": "Worker bị tắt giữa chừng",
                                "retryable": True,
                            },
                        }
                    ]
                )
        finally:
            closed.set()
            if hasattr(runtime, "cancel"):
                runtime.cancel(run_id)
            with contextlib.suppress(Exception):
                await stream.aclose()  # type: ignore[attr-defined]
            hb.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb


def local_runtimes(settings: Settings) -> dict[str, Any]:
    return {
        "mock": MockRuntime(step_delay_ms=settings.mock_step_delay_ms),
        "ollama": OllamaRuntime(
            base_url=settings.ollama_url, max_concurrency=1, timeout_s=settings.model_timeout_s
        ),
    }


async def pair(
    settings: Settings,
    code: str,
    server_url: str | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> Identity:
    url = server_url or default_server(settings)
    cp = ControlPlane(url, transport=transport)
    try:
        d = await cp.enroll(code, list(local_runtimes(settings)))
    finally:
        await cp.close()
    ident = Identity(url, uuid.UUID(d["worker_id"]), d["name"])
    make_store(settings.secret_store).set(secret_ref(ident.worker_id), d["worker_secret"])
    p = identity_file(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"server_url": url, "worker_id": str(ident.worker_id), "name": ident.name}),
        encoding="utf-8",
    )
    return ident


def connect(settings: Settings, transport: httpx2.AsyncBaseTransport | None = None) -> ControlPlane:
    ident = load_identity(settings)
    secret = make_store(settings.secret_store).get(secret_ref(ident.worker_id))
    if not secret:
        raise NotPaired(
            "Không tìm thấy secret của worker trong kho. Ghép nối lại: pnpm worker pair <MÃ>"
        )
    return ControlPlane(
        ident.server_url, worker_id=ident.worker_id, secret=secret, transport=transport
    )
