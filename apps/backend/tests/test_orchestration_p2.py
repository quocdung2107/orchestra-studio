"""P2: dependencies, parallel limits, retries, run control, tool gateway, approvals."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestra_backend.app import create_app
from orchestra_backend.core.config import Settings
from orchestra_backend.orchestrator.tools_builtin import (
    ToolError,
    safe_workspace_path,
    validate_input,
)
from tests.conftest import BASE_URL, TOKEN

API = "/api/v1"


def wait_for(fn: Callable[[], object], timeout: float = 10) -> object:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(0.02)
    pytest.fail("condition not reached")


def seed(client: TestClient) -> str:
    return client.post(f"{API}/demo/seed").json()["id"]


def agents_by_role(client: TestClient, cid: str) -> dict[str, dict]:
    return {a["role"]: a for a in client.get(f"{API}/companies/{cid}/agents").json()}


def tasks(client: TestClient, cid: str) -> list[dict]:
    return client.get(f"{API}/companies/{cid}/tasks").json()


def task(client: TestClient, tid: str) -> dict:
    return client.get(f"{API}/tasks/{tid}").json()


def pending_approval(client: TestClient, cid: str) -> dict:
    return wait_for(  # type: ignore[return-value]
        lambda: next(
            iter(
                client.get(f"{API}/companies/{cid}/approvals", params={"status": "pending"}).json()
            ),
            None,
        )
    )


def runs_by_role(client: TestClient, cid: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in client.get(f"{API}/companies/{cid}/runs").json():
        role = client.get(f"{API}/runs/{r['id']}").json()["agent_role"]
        out.setdefault(role, []).append(r)
    return out


def start(client: TestClient, cid: str, scenario: str = "demo-video-studio-p2") -> str:
    r = client.post(f"{API}/companies/{cid}/scenarios/{scenario}/start")
    assert r.status_code == 202, r.text
    return r.json()["root_task_id"]


# ---------------- full P2 scenario ----------------


def test_p2_scenario_parallel_retry_tools_and_approval(client: TestClient, settings) -> None:
    cid = seed(client)
    root = start(client, cid)
    a = pending_approval(client, cid)
    assert a["action_type"] == "tool:social.publish" and a["required_level"] == 3
    assert a["request_json"]["params"]["channel"] == "example.social"
    producer_task = next(t for t in tasks(client, cid) if t["required_role"] == "Producer")
    assert producer_task["status"] == "waiting_approval"

    # Wrong checksum is refused: the decision must bind to the shown payload.
    bad = client.post(
        f"{API}/approvals/{a['id']}/decide",
        json={"decision": "approve", "checksum": "sha256:x" * 2},
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "checksum_mismatch"
    ok = client.post(
        f"{API}/approvals/{a['id']}/decide",
        json={"decision": "approve", "checksum": a["checksum"], "note": "ok"},
    )
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    again = client.post(
        f"{API}/approvals/{a['id']}/decide", json={"decision": "reject", "checksum": a["checksum"]}
    )
    assert again.status_code == 409

    wait_for(lambda: task(client, root)["status"] == "completed")
    done = client.get(f"{API}/approvals/{a['id']}").json()
    assert done["execution_status"] == "succeeded" and done["result_json"]["simulated"] is True

    runs = runs_by_role(client, cid)
    reviewer = sorted(runs["Reviewer"], key=lambda r: r["attempt"])
    assert [(r["attempt"], r["status"]) for r in reviewer] == [(1, "failed"), (2, "completed")]
    assert reviewer[0]["error_code"] == "REVIEW_TOOL_TIMEOUT"

    ws = Path(settings.workspaces_dir) / cid / root / "workspace" / "script.md"
    assert ws.read_text(encoding="utf-8").startswith("# Kịch bản 60 giây")

    types = [
        e["event_type"]
        for e in client.get(f"{API}/companies/{cid}/events", params={"limit": 1000}).json()["items"]
    ]
    for t in (
        "tool.call_requested",
        "tool.call_finished",
        "approval.requested",
        "approval.decided",
        "agent.run.retry_scheduled",
        "lesson.proposed",
        "role_change.proposed",
    ):
        assert t in types, t

    # P3 hand-off: lesson and role-change proposal wait for a human.
    lessons = client.get(f"{API}/companies/{cid}/lessons").json()
    assert lessons[0]["review_status"] == "proposed" and lessons[0]["proposed_by"].startswith(
        "agent:"
    )
    props = client.get(f"{API}/companies/{cid}/role-proposals").json()
    assert props[0]["status"] == "proposed"
    roles = agents_by_role(client, cid)
    r = client.post(f"{API}/role-proposals/{props[0]['id']}/review", json={"decision": "approve"})
    assert r.status_code == 200, r.text
    reviewer_agent = client.get(f"{API}/agents/{roles['Reviewer']['id']}").json()
    assert reviewer_agent["reports_to_agent_id"] == roles["CMO"]["id"]


def test_rejected_approval_fails_up_the_chain(client: TestClient) -> None:
    cid = seed(client)
    root = start(client, cid)
    a = pending_approval(client, cid)
    client.post(
        f"{API}/approvals/{a['id']}/decide", json={"decision": "reject", "checksum": a["checksum"]}
    )
    wait_for(lambda: task(client, root)["status"] == "failed")
    runs = runs_by_role(client, cid)
    assert runs["Producer"][0]["error_code"] == "APPROVAL_REJECTED"
    assert runs["CEO"][0]["error_code"] == "CHILD_TASK_FAILED"
    assert client.get(f"{API}/approvals/{a['id']}").json()["execution_status"] is None


def test_cancel_while_waiting_for_approval(client: TestClient) -> None:
    cid = seed(client)
    root = start(client, cid)
    a = pending_approval(client, cid)
    r = client.post(f"{API}/tasks/{root}/cancel")
    assert r.status_code == 200, r.text
    wait_for(lambda: task(client, root)["status"] == "cancelled")
    assert client.get(f"{API}/approvals/{a['id']}").json()["status"] == "cancelled"
    producer = next(t for t in tasks(client, cid) if t["required_role"] == "Producer")
    assert producer["status"] == "cancelled"
    assert all(t["status"] in {"completed", "cancelled"} for t in tasks(client, cid))
    # Cancelled root can be retried.
    assert client.post(f"{API}/tasks/{root}/cancel").status_code == 409
    retry = client.post(f"{API}/tasks/{root}/retry")
    assert retry.status_code == 200
    pending_approval(client, cid)


# ---------------- user tasks, dependencies, scheduling ----------------


def test_dependencies_run_in_order_and_reject_cycles(client: TestClient) -> None:
    cid = seed(client)
    roles = agents_by_role(client, cid)
    a = client.post(
        f"{API}/companies/{cid}/tasks",
        json={"title": "A", "assigned_agent_id": roles["Researcher"]["id"]},
    ).json()
    b = client.post(
        f"{API}/companies/{cid}/tasks",
        json={"title": "B", "required_role": "Strategist", "depends_on": [a["id"]]},
    )
    assert b.status_code == 201, b.text
    b = b.json()
    assert b["depends_on"] == [a["id"]]
    wait_for(lambda: task(client, b["id"])["status"] == "completed")
    ta, tb = task(client, a["id"]), task(client, b["id"])
    assert ta["completed_at"] <= tb["completed_at"]
    c = client.post(
        f"{API}/companies/{cid}/tasks",
        json={"title": "C", "required_role": "CEO", "depends_on": [b["id"]]},
    ).json()
    cyc = client.post(f"{API}/tasks/{c['id']}/dependencies", json={"depends_on_task_id": c["id"]})
    assert cyc.status_code == 422


def test_failed_dependency_blocks_until_retry(client: TestClient) -> None:
    cid = seed(client)
    roles = agents_by_role(client, cid)
    client.post(f"{API}/agents/{roles['Reviewer']['id']}/deactivate")
    a = client.post(
        f"{API}/companies/{cid}/tasks", json={"title": "A", "required_role": "Reviewer"}
    ).json()
    assert a["assigned_agent_id"] is None
    wait_for(lambda: task(client, a["id"])["status"] == "failed")
    b = client.post(
        f"{API}/companies/{cid}/tasks",
        json={"title": "B", "required_role": "CEO", "depends_on": [a["id"]]},
    ).json()
    time.sleep(0.2)
    b = task(client, b["id"])
    assert b["status"] == "pending" and b["blocked_by"] == [a["id"]]
    client.post(f"{API}/agents/{roles['Reviewer']['id']}/activate")
    assert client.post(f"{API}/tasks/{a['id']}/retry").status_code == 200
    wait_for(lambda: task(client, b["id"])["status"] == "completed")


def test_parallel_limit_respected(client: TestClient) -> None:
    cid = seed(client)
    client.patch(f"{API}/companies/{cid}", json={"max_parallel_runs": 1})
    ids = [
        client.post(
            f"{API}/companies/{cid}/tasks", json={"title": f"T{i}", "required_role": "Strategist"}
        ).json()["id"]
        for i in range(3)
    ]
    wait_for(lambda: all(task(client, i)["status"] == "completed" for i in ids))
    events = client.get(f"{API}/companies/{cid}/events", params={"limit": 1000}).json()["items"]
    active, peak = 0, 0
    for e in events:
        if e["event_type"] == "agent.run.started":
            active += 1
            peak = max(peak, active)
        elif e["event_type"] in {"agent.run.completed", "agent.run.failed"}:
            active -= 1
    assert peak == 1


def test_create_task_validation(client: TestClient, company: dict) -> None:
    r = client.post(f"{API}/companies/{company['id']}/tasks", json={"title": "x"})
    assert r.status_code == 422


# ---------------- pause / resume ----------------


@pytest.fixture
def slow_client(tmp_path: Path):
    s = Settings(
        data_dir=tmp_path / "slow",
        token=TOKEN,
        port=8765,
        mock_step_delay_ms=150,
        retry_backoff_ms=0,
    )
    with TestClient(create_app(s), base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}) as c:
        yield c


def test_pause_and_resume(slow_client: TestClient) -> None:
    c = slow_client
    cid = seed(c)
    t = c.post(f"{API}/companies/{cid}/tasks", json={"title": "P", "required_role": "CEO"}).json()
    run = wait_for(
        lambda: next(
            (r for r in c.get(f"{API}/companies/{cid}/runs").json() if r["status"] == "running"),
            None,
        )
    )
    assert c.post(f"{API}/runs/{run['id']}/pause").status_code == 200  # type: ignore[index]
    assert task(c, t["id"])["status"] == "paused"
    time.sleep(0.5)
    assert c.get(f"{API}/runs/{run['id']}").json()["status"] == "paused"  # type: ignore[index]
    assert task(c, t["id"])["status"] == "paused"
    assert c.post(f"{API}/runs/{run['id']}/pause").status_code == 409  # type: ignore[index]
    assert c.post(f"{API}/runs/{run['id']}/resume").status_code == 200  # type: ignore[index]
    wait_for(lambda: task(c, t["id"])["status"] == "completed")


# ---------------- gateway policy ----------------


def test_tool_not_granted_is_denied(client: TestClient) -> None:
    cid = seed(client)
    roles = agents_by_role(client, cid)
    tools = {t["key"]: t for t in client.get(f"{API}/companies/{cid}/tools").json()}
    # Producer loses its grant: the publish call is denied before any approval is created.
    client.delete(f"{API}/agents/{roles['Producer']['id']}/tools/{tools['social.publish']['id']}")
    root = start(client, cid)
    wait_for(lambda: task(client, root)["status"] == "failed")
    assert runs_by_role(client, cid)["Producer"][0]["error_code"] == "TOOL_DENIED"
    assert client.get(f"{API}/companies/{cid}/approvals").json() == []


def test_workspace_path_rules(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    assert (
        safe_workspace_path(root, "workspace/a.md", ["workspace/"])
        == (root / "workspace" / "a.md").resolve()
    )
    for bad in [
        "../x",
        "workspace/../../x",
        "/etc/passwd",
        "C:/x",
        "workspace\\x",
        "other/a.md",
        "",
    ]:
        with pytest.raises(ToolError):
            safe_workspace_path(root, bad, ["workspace/"])


def test_validate_input_subset() -> None:
    schema = {
        "type": "object",
        "properties": {"q": {"type": "string", "maxLength": 3}, "n": {"type": "integer"}},
        "required": ["q"],
    }
    assert validate_input(schema, {"q": "ab"}) is None
    assert validate_input(schema, {}) is not None
    assert validate_input(schema, {"q": "abcd"}) is not None
    assert validate_input(schema, {"q": "a", "n": True}) is not None


def test_restart_expires_pending_approvals(settings, client: TestClient) -> None:
    cid = seed(client)
    root = start(client, cid)
    a = pending_approval(client, cid)
    client.__exit__(None, None, None)  # stop the app (lifespan shutdown)
    with TestClient(
        create_app(settings), base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}
    ) as c2:
        assert c2.get(f"{API}/approvals/{a['id']}").json()["status"] == "expired"
        assert c2.get(f"{API}/tasks/{root}").json()["status"] == "failed"
