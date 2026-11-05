from __future__ import annotations

import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from orchestra_backend.db import migrate
from orchestra_backend.templates_svc.loader import CompanyTemplate


def test_list_templates(client: TestClient) -> None:
    ts = client.get("/api/v1/templates").json()
    assert {"company", "agent"} == {t["kind"] for t in ts}
    assert any(t["id"] == "demo-video-studio" for t in ts)
    preset = client.get("/api/v1/templates/agent/researcher").json()
    assert preset["role"] == "Researcher"


def test_instantiate_demo_template(client: TestClient) -> None:
    r = client.post(
        "/api/v1/templates/company/demo-video-studio/instantiate", json={"name": "Studio 2"}
    )
    assert r.status_code == 201
    c = r.json()
    assert c["name"] == "Studio 2" and c["max_tool_level"] == 2
    g = client.get(f"/api/v1/companies/{c['id']}/org").json()
    assert len(g["departments"]) == 4 and len(g["agents"]) == 8
    names = {d["id"]: d["name"] for d in g["departments"]}
    by_role = {a["role"]: a for a in g["agents"]}
    assert names[by_role["Researcher"]["department_id"]] == "Marketing"
    assert by_role["Researcher"]["reports_to_agent_id"] == by_role["CMO"]["id"]
    tools = client.get(f"/api/v1/companies/{c['id']}/tools").json()
    assert {t["key"] for t in tools} == {
        "kb.search",
        "doc.draft",
        "workspace.write",
        "social.publish",
    }
    skills = client.get(f"/api/v1/agents/{by_role['Researcher']['id']}/skills").json()
    assert skills[0]["skill_name"] == "Nghiên cứu có nguồn"
    access = client.get(f"/api/v1/agents/{by_role['Researcher']['id']}/tool-access").json()
    assert {d["tool_key"] for d in access if d["allowed"]} == {"kb.search"}


def test_unknown_template_404(client: TestClient) -> None:
    r = client.post("/api/v1/templates/company/nope/instantiate", json={})
    assert r.status_code == 404


def test_template_reference_validation() -> None:
    base = {"id": "x", "kind": "company", "title": "X", "company": {"name": "X"}}
    with pytest.raises(ValidationError):
        CompanyTemplate.model_validate(
            {**base, "agents": [{"key": "a", "name": "A", "role": "R", "reports_to": "b"}]}
        )
    with pytest.raises(ValidationError):
        CompanyTemplate.model_validate(
            {
                **base,
                "agents": [
                    {"key": "a", "name": "A", "role": "R", "reports_to": "b"},
                    {"key": "b", "name": "B", "role": "R"},
                ],
            }
        )


def test_upgrade_from_p0_database_with_data(tmp_path) -> None:
    """Dung's existing P0 database must migrate without FK failures."""
    db = tmp_path / "p0.db"
    url = f"sqlite:///{db.as_posix()}"
    migrate.upgrade(url, "0002")
    cid, aid, vid, tid = (uuid.uuid4().hex for _ in range(4))
    con = sqlite3.connect(db)
    now = "2026-11-05 00:00:00"
    con.execute(
        "INSERT INTO companies (id,name,description,status,settings_json,created_at,"
        "updated_at) VALUES (?,?,?,?,?,?,?)",
        (cid, "P0", "", "active", "{}", now, now),
    )
    con.execute(
        "INSERT INTO agents (id,company_id,name,role,description,status,created_at,"
        "updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (aid, cid, "A", "R", "", "active", now, now),
    )
    con.execute(
        "INSERT INTO agent_versions (id,agent_id,version_number,definition_json,"
        "runtime_preference_json,created_by,created_at) VALUES (?,?,?,?,?,?,?)",
        (vid, aid, 1, "{}", "{}", "u", now),
    )
    con.execute(
        "INSERT INTO tasks (id,company_id,assigned_agent_id,created_by,title,"
        "description,status,priority,created_at,updated_at) VALUES "
        "(?,?,?,?,?,?,?,?,?,?)",
        (tid, cid, aid, "u", "t", "", "completed", 0, now, now),
    )
    con.commit()
    con.close()
    migrate.upgrade(url)
    con = sqlite3.connect(db)
    assert con.execute("SELECT max_tool_level FROM companies").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM agents").fetchone()[0] == 1
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    con.close()
