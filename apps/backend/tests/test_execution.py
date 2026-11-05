from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from orchestra_backend.runtime.mock.scenarios import load_all


def _seed(client: TestClient) -> str:
    r = client.post("/api/v1/demo/seed")
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _run_scenario(client: TestClient, cid: str, scenario: str) -> dict:
    r = client.post(f"/api/v1/companies/{cid}/scenarios/{scenario}/start")
    assert r.status_code == 202, r.text
    root = r.json()["root_task_id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        task = client.get(f"/api/v1/tasks/{root}").json()
        if task["status"] in {"completed", "failed"}:
            return task
        time.sleep(0.02)
    pytest.fail("scenario did not finish")


def _types(client: TestClient, cid: str) -> list[str]:
    return [
        e["event_type"]
        for e in client.get(f"/api/v1/companies/{cid}/events", params={"limit": 1000}).json()[
            "items"
        ]
    ]


def test_scenarios_are_valid() -> None:
    assert {"demo-video-studio", "demo-video-studio-failure"} <= set(load_all())


def test_runtimes_listed_with_capabilities(client: TestClient) -> None:
    rts = {r["runtime_id"]: r for r in client.get("/api/v1/runtimes").json()}
    assert set(rts) == {"mock", "ollama", "anthropic", "openai"}
    assert rts["mock"]["capabilities"]["supports_pause"] is True
    assert rts["anthropic"]["capabilities"]["supports_pause"] is False
    assert rts["anthropic"]["capabilities"]["supports_cancel"] is True
    assert rts["anthropic"]["requires_credential"] is True
    assert rts["ollama"]["requires_credential"] is False


def test_seed_creates_active_org(client: TestClient) -> None:
    cid = _seed(client)
    agents = client.get(f"/api/v1/companies/{cid}/agents").json()
    assert len(agents) == 8
    assert {a["status"] for a in agents} == {"active"}


def test_happy_path_delegation_and_artifacts(client: TestClient) -> None:
    cid = _seed(client)
    root = _run_scenario(client, cid, "demo-video-studio")
    assert root["status"] == "completed"

    tasks = client.get(f"/api/v1/companies/{cid}/tasks").json()
    assert len(tasks) == 8  # one task per role: CEO delegates 3, CMO 2, Producer 2
    assert all(t["status"] == "completed" for t in tasks)
    assert sum(1 for t in tasks if t["parent_task_id"] is None) == 1

    runs = client.get(f"/api/v1/companies/{cid}/runs").json()
    assert len(runs) == 8 and all(r["status"] == "completed" for r in runs)

    script_run = next(
        r
        for r in runs
        if client.get(f"/api/v1/runs/{r['id']}").json()["agent_role"] == "Scriptwriter"
    )
    detail = client.get(f"/api/v1/runs/{script_run['id']}").json()
    assert detail["artifacts"][0]["name"] == "script.md"
    art = detail["artifacts"][0]
    content = client.get(f"/api/v1/artifacts/{art['id']}/content")
    assert content.status_code == 200 and "Kịch bản 60 giây" in content.text
    assert art["checksum"].startswith("sha256:")

    types = _types(client, cid)
    assert types.count("agent.run.completed") == 8
    assert types.count("artifact.created") == 4
    assert types.count("agent.run.delegated") == 7
    assert "scenario.started" in types


def test_failure_propagates_and_is_observable(client: TestClient) -> None:
    cid = _seed(client)
    root = _run_scenario(client, cid, "demo-video-studio-failure")
    assert root["status"] == "failed"
    runs = {
        client.get(f"/api/v1/runs/{r['id']}").json()["agent_role"]: r
        for r in client.get(f"/api/v1/companies/{cid}/runs").json()
    }
    assert runs["Reviewer"]["error_code"] == "QUALITY_CHECK_FAILED"
    assert runs["Producer"]["error_code"] == "CHILD_TASK_FAILED"
    assert runs["CEO"]["error_code"] == "CHILD_TASK_FAILED"
    assert "Secretary" not in runs  # CEO stopped before delegating further


def test_repeat_run_same_logical_sequence(client: TestClient) -> None:
    a = _seed(client)
    b = _seed(client)
    _run_scenario(client, a, "demo-video-studio")
    _run_scenario(client, b, "demo-video-studio")
    assert _types(client, a) == _types(client, b)


def test_missing_agent_fails_task(client: TestClient) -> None:
    cid = _seed(client)
    reviewer = next(
        a for a in client.get(f"/api/v1/companies/{cid}/agents").json() if a["role"] == "Reviewer"
    )
    client.post(f"/api/v1/agents/{reviewer['id']}/deactivate")
    root = _run_scenario(client, cid, "demo-video-studio")
    assert root["status"] == "failed"
    reviewer_task = next(
        t
        for t in client.get(f"/api/v1/companies/{cid}/tasks").json()
        if t["required_role"] == "Reviewer"
    )
    assert reviewer_task["status"] == "failed" and reviewer_task["assigned_agent_id"] is None


def test_unknown_scenario_404(client: TestClient, company: dict) -> None:
    r = client.post(f"/api/v1/companies/{company['id']}/scenarios/nope/start")
    assert r.status_code == 404


def test_sse_stream_replays_and_resumes(client: TestClient) -> None:
    cid = _seed(client)
    _run_scenario(client, cid, "demo-video-studio")
    r = client.get(f"/api/v1/companies/{cid}/events/stream", params={"until_idle": True})
    assert r.headers["content-type"].startswith("text/event-stream")
    ids = [int(line[4:]) for line in r.text.splitlines() if line.startswith("id: ")]
    assert ids == sorted(ids) and ids[0] == 1
    r2 = client.get(
        f"/api/v1/companies/{cid}/events/stream",
        params={"until_idle": True},
        headers={"Last-Event-ID": str(ids[-5])},
    )
    ids2 = [int(line[4:]) for line in r2.text.splitlines() if line.startswith("id: ")]
    assert ids2 == ids[-4:]


def test_interrupted_runs_failed_on_restart(settings, client: TestClient, container) -> None:
    import uuid as _uuid

    from orchestra_backend.app import create_app
    from orchestra_backend.execution import service as ex
    from tests.conftest import BASE_URL, TOKEN

    cid = _uuid.UUID(_seed(client))
    with container.tx() as s:
        task = ex.create_task(
            s, company_id=cid, title="t", description="", required_role="CEO", created_by="test"
        )
        from orchestra_backend.agents.models import Agent

        ex.create_run(s, task, s.get(Agent, task.assigned_agent_id), {}, None)
    with TestClient(
        create_app(settings), base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}
    ) as c2:
        runs = c2.get(f"/api/v1/companies/{cid}/runs").json()
        assert runs[0]["status"] == "failed" and runs[0]["error_code"] == "INTERRUPTED"
