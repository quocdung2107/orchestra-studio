from __future__ import annotations

from fastapi.testclient import TestClient


def _create(client: TestClient, cid: str, **kw) -> dict:
    body = {"name": "Ana", "role": "Researcher", **kw}
    r = client.post(f"/api/v1/companies/{cid}/agents", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_agent_has_version_and_events(client: TestClient, company: dict) -> None:
    a = _create(client, company["id"], definition={"instructions": "Find facts"})
    assert a["status"] == "draft"
    assert a["current_version"]["version_number"] == 1
    assert a["current_version"]["runtime"]["runtime_id"] == "mock"
    types = [
        e["event_type"]
        for e in client.get(f"/api/v1/companies/{company['id']}/events").json()["items"]
    ]
    assert types[-2:] == ["agent.created", "agent.version_created"]


def test_version_history_preserved(client: TestClient, company: dict) -> None:
    a = _create(client, company["id"])
    r = client.post(
        f"/api/v1/agents/{a['id']}/versions",
        json={"definition": {"instructions": "v2"}, "runtime": {"runtime_id": "mock"}},
    )
    assert r.status_code == 201
    assert r.json()["current_version"]["version_number"] == 2
    versions = client.get(f"/api/v1/agents/{a['id']}/versions").json()
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[1]["definition"]["instructions"] == ""


def test_lifecycle_transitions(client: TestClient, company: dict) -> None:
    a = _create(client, company["id"])
    aid = a["id"]
    assert client.post(f"/api/v1/agents/{aid}/deactivate").status_code == 409
    assert client.post(f"/api/v1/agents/{aid}/activate").json()["status"] == "active"
    assert client.post(f"/api/v1/agents/{aid}/activate").status_code == 409
    assert client.post(f"/api/v1/agents/{aid}/deactivate").json()["status"] == "inactive"
    assert client.post(f"/api/v1/agents/{aid}/archive").json()["status"] == "archived"
    assert client.post(f"/api/v1/agents/{aid}/activate").status_code == 409
    assert client.get(f"/api/v1/companies/{company['id']}/agents").json() == []


def test_unknown_runtime_rejected(client: TestClient, company: dict) -> None:
    r = client.post(
        f"/api/v1/companies/{company['id']}/agents",
        json={"name": "x", "role": "y", "runtime": {"runtime_id": "gpt-x"}},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unknown_runtime"


def test_secret_like_runtime_settings_rejected(client: TestClient, company: dict) -> None:
    r = client.post(
        f"/api/v1/companies/{company['id']}/agents",
        json={
            "name": "x",
            "role": "y",
            "runtime": {"runtime_id": "mock", "settings": {"api_key": "sk-123"}},
        },
    )
    assert r.status_code == 422
    assert "sk-123" not in r.text


def test_update_agent(client: TestClient, company: dict) -> None:
    a = _create(client, company["id"])
    r = client.patch(f"/api/v1/agents/{a['id']}", json={"role": "Strategist"})
    assert r.json()["role"] == "Strategist"


def test_agent_in_unknown_company(client: TestClient) -> None:
    r = client.post(
        "/api/v1/companies/00000000-0000-0000-0000-000000000000/agents",
        json={"name": "x", "role": "y"},
    )
    assert r.status_code == 404
