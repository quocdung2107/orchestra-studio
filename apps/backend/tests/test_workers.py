"""P5 workers (ADR-0025): identity, leases, heartbeat, revocation, replay, checksums."""

from __future__ import annotations

import asyncio
import hashlib
import socket
import threading
import time
from collections.abc import Iterator

import httpx2
import pytest
import uvicorn
from fastapi.testclient import TestClient

from orchestra_backend.app import create_app
from orchestra_backend.core.config import Settings
from orchestra_backend.credentials.store import MemorySecretStore
from orchestra_backend.worker_client import client as wc
from tests.conftest import BASE_URL, TOKEN
from tests.test_orchestration_p2 import agents_by_role, seed, task, wait_for
from tests.test_p4 import finished, runs_of, set_runtime, start_task

API = "/api/v1"
W = f"{API}/worker"


@pytest.fixture
def wsettings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"worker_lease_ttl_s": 0.6, "worker_dispatch_timeout_s": 5.0, "worker_poll_max_s": 5}
    )


@pytest.fixture
def wclient(wsettings: Settings) -> Iterator[TestClient]:
    app = create_app(wsettings)
    with TestClient(app, base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}) as c:
        yield c


def pair(c: TestClient, name: str = "Máy phụ") -> dict:
    code = c.post(f"{API}/workers/pairing-codes", json={"name": name}).json()["code"]
    r = c.post(
        f"{W}/enroll",
        json={"code": code, "runtimes": ["mock", "ollama"]},
        headers={"X-Orchestra-Token": ""},
    )
    assert r.status_code == 201, r.text
    return r.json()


def token(c: TestClient, w: dict) -> dict[str, str]:
    r = c.post(
        f"{W}/token", json={"worker_id": w["worker_id"], "worker_secret": w["worker_secret"]}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Orchestra-Token": ""}


def on_worker(c: TestClient, role: str = "Scriptwriter", **extra: object) -> tuple[str, dict]:
    cid = seed(c)
    agent = agents_by_role(c, cid)[role]
    r = set_runtime(c, agent, "worker", {"runtime": "mock", **extra})
    assert r.status_code == 201, r.text
    return cid, agent


def claim(c: TestClient, h: dict[str, str]) -> dict:
    r = c.get(f"{W}/lease", params={"wait": 3}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def post(c: TestClient, h: dict, lease: dict, seq: int, *events: dict) -> object:
    return c.post(
        f"{W}/leases/{lease['lease_id']}/events",
        json={"seq": seq, "events": list(events)},
        headers=h,
    )


def ev(t: str, **data: object) -> dict:
    return {"type": t, "data": data}


def artifact(content: str, digest: str | None = None) -> dict:
    d = digest or hashlib.sha256(content.encode()).hexdigest()
    return ev(
        "run.artifact.produced", name="kb.md", mime_type="text/markdown", content=content, sha256=d
    )


# ---------------------------------------------------------------- identity


def test_pairing_code_is_single_use_and_secret_never_listed(wclient: TestClient) -> None:
    code = wclient.post(f"{API}/workers/pairing-codes", json={"name": "A"}).json()["code"]
    body = {"code": code.lower().replace("-", ""), "runtimes": ["mock", "anthropic"]}
    first = wclient.post(f"{W}/enroll", json=body)
    assert first.status_code == 201
    again = wclient.post(f"{W}/enroll", json=body)
    assert again.status_code == 401 and again.json()["error"]["code"] == "PAIRING_INVALID"
    workers = wclient.get(f"{API}/workers").json()
    assert workers[0]["runtimes"] == ["mock"]  # cloud runtimes never run on a worker (no secrets)
    assert first.json()["worker_secret"] not in str(workers)


def test_auth_boundaries(wclient: TestClient) -> None:
    w = pair(wclient)
    h = token(wclient, w)
    bad = wclient.post(f"{W}/token", json={"worker_id": w["worker_id"], "worker_secret": "nope"})
    assert bad.status_code == 401
    # UI token does not open worker endpoints; worker token does not open UI endpoints.
    assert wclient.get(f"{W}/lease", params={"wait": 0}).status_code == 401
    assert wclient.get(f"{API}/workers", headers={"X-Orchestra-Token": "", **h}).status_code == 401
    assert wclient.get(f"{W}/lease", params={"wait": 0}, headers=h).status_code == 204


def test_access_token_expires(settings: Settings) -> None:
    s = settings.model_copy(update={"worker_token_ttl_s": 0.2})
    with TestClient(create_app(s), base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}) as c:
        h = token(c, pair(c))
        time.sleep(0.3)
        r = c.get(f"{W}/lease", params={"wait": 0}, headers=h)
        assert r.status_code == 401 and r.json()["error"]["code"] == "WORKER_TOKEN_INVALID"


# ---------------------------------------------------------------- leases


def test_lease_protocol_happy_path_with_replay_gap_checksum_and_tools(wclient: TestClient) -> None:
    h = token(wclient, pair(wclient))
    cid, agent = on_worker(wclient)
    tid = start_task(wclient, cid, agent)
    lease = claim(wclient, h)
    assert lease["runtime_id"] == "mock" and lease["task"]["id"] == tid
    assert runs_of(wclient, tid)[0]["status"] == "queued"

    assert post(wclient, h, lease, 1, ev("run.started")).status_code == 200
    replay = post(wclient, h, lease, 1, ev("run.progress", message="lặp"))
    assert replay.status_code == 409 and replay.json()["error"]["code"] == "SEQ_REPLAY"
    gap = post(wclient, h, lease, 3, ev("run.progress", message="nhảy"))
    assert gap.status_code == 409 and gap.json()["error"]["code"] == "SEQ_GAP"
    bad = post(wclient, h, lease, 2, artifact("nội dung", digest="0" * 64))
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "ARTIFACT_CHECKSUM"
    early = post(
        wclient, h, lease, 2, ev("run.completed", summary="x"), ev("run.progress", message="y")
    )
    assert early.status_code == 422

    tool = wclient.post(
        f"{W}/leases/{lease['lease_id']}/tool-calls",
        json={"key": "kb.search", "params": {"q": "trà"}},
        headers=h,
    )
    assert tool.status_code == 200 and "ok" in tool.json()
    assert wclient.post(f"{W}/leases/{lease['lease_id']}/heartbeat", headers=h).status_code == 200

    assert (
        post(
            wclient, h, lease, 2, artifact("Kịch bản trà sen"), ev("run.completed", summary="Xong")
        ).status_code
        == 200
    )
    assert finished(wclient, tid)["status"] == "completed"
    run_id = runs_of(wclient, tid)[0]["id"]
    arts = wclient.get(f"{API}/runs/{run_id}").json()["artifacts"]
    assert [a["name"] for a in arts] == ["kb.md"]
    closed = post(wclient, h, lease, 3, ev("run.progress", message="muộn"))
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "LEASE_CLOSED"


def test_lost_heartbeat_fails_run_and_never_completes(wclient: TestClient) -> None:
    h = token(wclient, pair(wclient))
    cid, agent = on_worker(wclient)
    tid = start_task(wclient, cid, agent)
    lease = claim(wclient, h)
    assert post(wclient, h, lease, 1, ev("run.started")).status_code == 200
    t = finished(wclient, tid)  # nothing more from the worker; lease ttl 0.6 s
    assert t["status"] == "failed"
    run = runs_of(wclient, tid)[0]
    assert run["error_code"] == "WORKER_LOST"
    late = post(wclient, h, lease, 2, ev("run.completed", summary="quá muộn"))
    assert late.status_code == 409
    assert task(wclient, tid)["status"] == "failed"


def test_revoking_worker_mid_run_fails_run_and_blocks_worker(wclient: TestClient) -> None:
    w = pair(wclient)
    h = token(wclient, w)
    cid, agent = on_worker(wclient)
    tid = start_task(wclient, cid, agent)
    lease = claim(wclient, h)
    post(wclient, h, lease, 1, ev("run.started"))
    r = wclient.post(f"{API}/workers/{w['worker_id']}/revoke")
    assert r.status_code == 200 and r.json()["status"] == "revoked"
    assert finished(wclient, tid)["status"] == "failed"
    assert runs_of(wclient, tid)[0]["error_code"] == "WORKER_REVOKED"
    assert wclient.post(f"{W}/leases/{lease['lease_id']}/heartbeat", headers=h).status_code == 401
    again = wclient.post(
        f"{W}/token", json={"worker_id": w["worker_id"], "worker_secret": w["worker_secret"]}
    )
    assert again.status_code == 403 and again.json()["error"]["code"] == "WORKER_REVOKED"


def test_cancel_closes_lease(wclient: TestClient) -> None:
    h = token(wclient, pair(wclient))
    cid, agent = on_worker(wclient)
    tid = start_task(wclient, cid, agent)
    lease = claim(wclient, h)
    post(wclient, h, lease, 1, ev("run.started"))
    assert wclient.post(f"{API}/tasks/{tid}/cancel").status_code in (200, 202)
    assert finished(wclient, tid)["status"] == "cancelled"
    hb = wclient.post(f"{W}/leases/{lease['lease_id']}/heartbeat", headers=h)
    assert hb.status_code == 409 and hb.json()["error"]["code"] == "LEASE_CLOSED"


def test_no_worker_fails_fast_and_pin_is_respected(wclient: TestClient) -> None:
    cid, agent = on_worker(wclient)
    tid = start_task(wclient, cid, agent)
    assert finished(wclient, tid)["status"] == "failed"
    assert runs_of(wclient, tid)[0]["error_code"] == "WORKER_UNAVAILABLE"

    a, b = pair(wclient, "A"), pair(wclient, "B")
    ha = token(wclient, a)
    hb = token(wclient, b)
    set_runtime(wclient, agent, "worker", {"runtime": "mock", "worker_id": b["worker_id"]})
    tid2 = start_task(wclient, cid, agent)
    wait_for(lambda: runs_of(wclient, tid2))
    assert wclient.get(f"{W}/lease", params={"wait": 0.3}, headers=ha).status_code == 204
    assert claim(wclient, hb)["task"]["id"] == tid2


def test_worker_settings_validated(wclient: TestClient) -> None:
    cid = seed(wclient)
    agent = agents_by_role(wclient, cid)["Scriptwriter"]
    assert set_runtime(wclient, agent, "worker", {"runtime": "anthropic"}).status_code == 422
    assert (
        set_runtime(wclient, agent, "worker", {"runtime": "ollama", "settings": {}}).status_code
        == 422
    )
    ok = set_runtime(
        wclient, agent, "worker", {"runtime": "ollama", "settings": {"model": "qwen3:4b"}}
    )
    assert ok.status_code == 201, ok.text


# ---------------------------------------------------------------- real process loop


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server(settings: Settings) -> Iterator[Settings]:
    s = settings.model_copy(update={"port": _free_port(), "mock_step_delay_ms": 10})
    server = uvicorn.Server(
        uvicorn.Config(create_app(s), host="127.0.0.1", port=s.port, log_level="warning")
    )
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    wait_for(lambda: server.started)
    yield s
    server.should_exit = True
    th.join(5)


def test_worker_process_runs_task_end_to_end(
    live_server: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = live_server
    store = MemorySecretStore()  # stands in for the OS keyring shared by pair and run
    monkeypatch.setattr(wc, "make_store", lambda _kind: store)
    base = f"http://127.0.0.1:{s.port}"
    with httpx2.Client(base_url=base, headers={"X-Orchestra-Token": TOKEN}, timeout=10) as ui:
        cid, agent = on_worker(ui)
        code = ui.post(f"{API}/workers/pairing-codes", json={"name": "Máy này"}).json()["code"]
        asyncio.run(wc.pair(s, code, base))
        tid = start_task(ui, cid, agent)

        async def go() -> None:
            cp = wc.connect(s)
            try:
                await wc.Worker(cp, wc.local_runtimes(s), poll_wait_s=2).run_forever(max_leases=1)
            finally:
                await cp.close()

        asyncio.run(go())
        t = finished(ui, tid)
        assert t["status"] == "completed", runs_of(ui, tid)
        workers = ui.get(f"{API}/workers").json()
        assert workers[0]["online"] is True and workers[0]["name"] == "Máy này"
