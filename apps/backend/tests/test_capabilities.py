from __future__ import annotations

from fastapi.testclient import TestClient


def _agent(client: TestClient, cid: str, **kw) -> dict:
    r = client.post(f"/api/v1/companies/{cid}/agents", json={"name": "A", "role": "R", **kw})
    assert r.status_code == 201, r.text
    client.post(f"/api/v1/agents/{r.json()['id']}/activate")
    return r.json()


def _tool(client: TestClient, cid: str, key: str, level: int, **policy) -> dict:
    body = {"key": key, "name": key, "permission_level": level, "policy": policy}
    r = client.post(f"/api/v1/companies/{cid}/tools", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_skill_versions_pinned(client: TestClient, company: dict) -> None:
    cid = company["id"]
    r = client.post(
        f"/api/v1/companies/{cid}/skills",
        json={"name": "Research", "version": {"instructions": "v1"}},
    )
    skill = r.json()
    assert skill["latest_version_number"] == 1
    a = _agent(client, cid)
    out = client.post(f"/api/v1/agents/{a['id']}/skills", json={"skill_id": skill["id"]}).json()
    assert out[0]["version_number"] == 1
    client.post(f"/api/v1/skills/{skill['id']}/versions", json={"instructions": "v2"})
    out = client.get(f"/api/v1/agents/{a['id']}/skills").json()
    assert out[0]["version_number"] == 1 and out[0]["latest_version_number"] == 2
    vers = client.get(f"/api/v1/skills/{skill['id']}/versions").json()
    upgraded = client.post(
        f"/api/v1/agents/{a['id']}/skills",
        json={"skill_id": skill["id"], "skill_version_id": vers[0]["id"]},
    )
    assert upgraded.json()[0]["version_number"] == 2
    assert client.post(f"/api/v1/skills/{skill['id']}/archive").status_code == 409
    client.delete(f"/api/v1/agents/{a['id']}/skills/{skill['id']}")
    assert client.post(f"/api/v1/skills/{skill['id']}/archive").status_code == 200


def test_duplicate_skill_name(client: TestClient, company: dict) -> None:
    cid = company["id"]
    client.post(f"/api/v1/companies/{cid}/skills", json={"name": "X"})
    assert client.post(f"/api/v1/companies/{cid}/skills", json={"name": "X"}).status_code == 409


def test_l3_tool_must_require_approval(client: TestClient, company: dict) -> None:
    r = client.post(
        f"/api/v1/companies/{company['id']}/tools",
        json={"key": "send", "name": "Send", "permission_level": 3},
    )
    assert r.status_code == 422


def test_tool_update_bumps_version_and_logs_definition(client: TestClient, company: dict) -> None:
    t = _tool(client, company["id"], "kb.search", 0)
    body = {"name": "Search", "permission_level": 0, "policy": {"timeout_seconds": 5}}
    r = client.put(f"/api/v1/tools/{t['id']}", json=body)
    assert r.json()["version"] == 2
    assert client.put(f"/api/v1/tools/{t['id']}", json=body).json()["version"] == 2  # no-op
    evs = client.get(f"/api/v1/companies/{company['id']}/events").json()["items"]
    upd = [e for e in evs if e["event_type"] == "tool.updated"]
    assert len(upd) == 1 and upd[0]["payload"]["definition"]["policy"]["timeout_seconds"] == 5


def test_default_deny_and_ceiling(client: TestClient, company: dict) -> None:
    cid = company["id"]  # company ceiling defaults to L1
    a = _agent(client, cid)
    read = _tool(client, cid, "read", 0)
    exe = _tool(client, cid, "exec", 2)
    access = {d["tool_key"]: d for d in client.get(f"/api/v1/agents/{a['id']}/tool-access").json()}
    assert access["read"]["result"] == "deny_not_granted"  # default deny
    r = client.post(f"/api/v1/agents/{a['id']}/tools", json={"tool_id": exe["id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "permission_ceiling_exceeded"
    r = client.post(f"/api/v1/agents/{a['id']}/tools", json={"tool_id": read["id"]})
    decision = next(d for d in r.json() if d["tool_key"] == "read")
    assert decision["allowed"] and decision["principal"] == f"agent:{a['id']}"
    assert decision["resource"] == "tool:read"


def test_department_ceiling_cannot_exceed_and_blocks_after_lowering(
    client: TestClient, company: dict
) -> None:
    cid = company["id"]
    client.patch(f"/api/v1/companies/{cid}", json={"max_tool_level": 2})
    d = client.post(f"/api/v1/companies/{cid}/departments", json={"name": "Ops"}).json()
    a = _agent(client, cid, department_id=d["id"])
    exe = _tool(client, cid, "exec", 2)
    assert client.post(f"/api/v1/agents/{a['id']}/tools", json={"tool_id": exe["id"]}).is_success
    client.patch(f"/api/v1/departments/{d['id']}", json={"max_tool_level": 0})
    dec = next(
        x
        for x in client.get(f"/api/v1/agents/{a['id']}/tool-access").json()
        if x["tool_key"] == "exec"
    )
    assert dec["granted"] and not dec["allowed"]
    assert dec["result"] == "deny_above_ceiling" and dec["ceiling_source"] == "department:Ops"


def test_cross_company_tool_rejected(client: TestClient, company: dict) -> None:
    other = client.post("/api/v1/companies", json={"name": "O"}).json()
    t = _tool(client, other["id"], "read", 0)
    a = _agent(client, company["id"])
    r = client.post(f"/api/v1/agents/{a['id']}/tools", json={"tool_id": t["id"]})
    assert r.json()["error"]["code"] == "cross_company_link"


def test_agents_cannot_self_grant(container, company: dict, client: TestClient) -> None:
    import uuid

    import pytest

    from orchestra_backend.capabilities import service
    from orchestra_backend.capabilities.schemas import GrantTool
    from orchestra_backend.core.errors import DomainValidationError

    a = _agent(client, company["id"])
    t = _tool(client, company["id"], "read", 0)
    with pytest.raises(DomainValidationError), container.tx() as s:
        service.grant_tool(
            s,
            uuid.UUID(a["id"]),
            GrantTool(tool_id=uuid.UUID(t["id"])),
            granted_by=f"agent:{a['id']}",
        )
