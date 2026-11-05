from __future__ import annotations

from fastapi.testclient import TestClient


def _dept(client: TestClient, cid: str, name: str, **kw) -> dict:
    r = client.post(f"/api/v1/companies/{cid}/departments", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _agent(client: TestClient, cid: str, name: str, **kw) -> dict:
    r = client.post(f"/api/v1/companies/{cid}/agents", json={"name": name, "role": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_department_tree_and_cycle_rejected(client: TestClient, company: dict) -> None:
    cid = company["id"]
    a = _dept(client, cid, "A")
    b = _dept(client, cid, "B", parent_department_id=a["id"])
    c = _dept(client, cid, "C", parent_department_id=b["id"])
    r = client.patch(f"/api/v1/departments/{a['id']}", json={"parent_department_id": c["id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "org_cycle"
    r = client.patch(f"/api/v1/departments/{a['id']}", json={"parent_department_id": a["id"]})
    assert r.json()["error"]["code"] == "org_cycle"
    # explicit null moves to top level
    r = client.patch(f"/api/v1/departments/{c['id']}", json={"parent_department_id": None})
    assert r.status_code == 200 and r.json()["parent_department_id"] is None


def test_cross_company_department_rejected(client: TestClient, company: dict) -> None:
    other = client.post("/api/v1/companies", json={"name": "Other"}).json()
    d = _dept(client, other["id"], "X")
    r = client.post(
        f"/api/v1/companies/{company['id']}/departments",
        json={"name": "Y", "parent_department_id": d["id"]},
    )
    assert r.json()["error"]["code"] == "cross_company_link"
    r = client.post(
        f"/api/v1/companies/{company['id']}/agents",
        json={"name": "n", "role": "r", "department_id": d["id"]},
    )
    assert r.json()["error"]["code"] == "cross_company_link"


def test_archive_department_rules(client: TestClient, company: dict) -> None:
    cid = company["id"]
    d = _dept(client, cid, "Ops")
    a = _agent(client, cid, "Ann", department_id=d["id"])
    r = client.post(f"/api/v1/departments/{d['id']}/archive")
    assert r.status_code == 409 and r.json()["error"]["code"] == "department_not_empty"
    client.patch(f"/api/v1/agents/{a['id']}", json={"department_id": None})
    assert client.post(f"/api/v1/departments/{d['id']}/archive").json()["status"] == "archived"
    r = client.patch(f"/api/v1/agents/{a['id']}", json={"department_id": d["id"]})
    assert r.status_code == 409


def test_reporting_cycle_rejected(client: TestClient, company: dict) -> None:
    cid = company["id"]
    boss = _agent(client, cid, "Boss")
    mid = _agent(client, cid, "Mid", reports_to_agent_id=boss["id"])
    low = _agent(client, cid, "Low", reports_to_agent_id=mid["id"])
    r = client.patch(f"/api/v1/agents/{boss['id']}", json={"reports_to_agent_id": low["id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "org_cycle"
    r = client.patch(f"/api/v1/agents/{boss['id']}", json={"reports_to_agent_id": boss["id"]})
    assert r.json()["error"]["code"] == "org_cycle"
    r = client.patch(f"/api/v1/agents/{low['id']}", json={"reports_to_agent_id": boss["id"]})
    assert r.status_code == 200 and r.json()["reports_to_agent_id"] == boss["id"]


def test_archiving_manager_detaches_reports(client: TestClient, company: dict) -> None:
    cid = company["id"]
    boss = _agent(client, cid, "Boss")
    sub = _agent(client, cid, "Sub", reports_to_agent_id=boss["id"])
    client.post(f"/api/v1/agents/{boss['id']}/archive")
    assert client.get(f"/api/v1/agents/{sub['id']}").json()["reports_to_agent_id"] is None


def test_org_graph_and_layout(client: TestClient, company: dict) -> None:
    cid = company["id"]
    d = _dept(client, cid, "Ops")
    a = _agent(client, cid, "Ann", department_id=d["id"])
    key = f"agent:{a['id']}"
    r = client.put(
        f"/api/v1/companies/{cid}/org/layout", json={"positions": {key: {"x": 10, "y": 20}}}
    )
    assert r.status_code == 204
    client.put(f"/api/v1/companies/{cid}/org/layout", json={"positions": {key: {"x": 30, "y": 40}}})
    g = client.get(f"/api/v1/companies/{cid}/org").json()
    assert g["departments"][0]["name"] == "Ops"
    assert g["agents"][0]["department_id"] == d["id"]
    assert g["layout"][key] == {"x": 30, "y": 40}
    bad = client.put(
        f"/api/v1/companies/{cid}/org/layout", json={"positions": {"evil:1": {"x": 0, "y": 0}}}
    )
    assert bad.status_code == 422


def test_department_events(client: TestClient, company: dict) -> None:
    d = _dept(client, company["id"], "Ops")
    client.patch(f"/api/v1/departments/{d['id']}", json={"name": "Operations"})
    types = [
        e["event_type"]
        for e in client.get(f"/api/v1/companies/{company['id']}/events").json()["items"]
    ]
    assert types[-2:] == ["department.created", "department.updated"]
