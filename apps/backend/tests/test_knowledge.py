"""P3: knowledge with provenance, search, summaries, lessons, role-change proposals."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_orchestration_p2 import (
    API,
    agents_by_role,
    pending_approval,
    seed,
    start,
    task,
    wait_for,
)


def test_notes_search_without_diacritics_and_versioning(client: TestClient, company: dict) -> None:
    cid = company["id"]
    r = client.post(
        f"{API}/companies/{cid}/knowledge",
        json={"title": "Nghiên cứu khán giả", "content": "Nhóm 25–35 tuổi xem video ngắn."},
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["source_type"] == "manual" and item["version"] == 1

    res = client.get(f"{API}/companies/{cid}/knowledge/search", params={"q": "khan gia"}).json()
    assert res["engine"] in {"fts5", "like"}
    if res["engine"] == "fts5":
        assert [h["id"] for h in res["hits"]] == [item["id"]]

    upd = client.patch(f"{API}/knowledge/{item['id']}", json={"content": "Nhóm 18–24 tuổi."}).json()
    assert upd["version"] == 2
    hits = client.get(f"{API}/companies/{cid}/knowledge/search", params={"q": "18"}).json()["hits"]
    assert hits and hits[0]["id"] == item["id"]

    client.post(f"{API}/knowledge/{item['id']}/archive")
    hits = client.get(f"{API}/companies/{cid}/knowledge/search", params={"q": "nhom"}).json()[
        "hits"
    ]
    assert hits == []
    # Summaries/lessons cannot be typed in by hand: they need a source.
    bad = client.post(
        f"{API}/companies/{cid}/knowledge", json={"title": "x", "content": "y", "kind": "lesson"}
    )
    assert bad.status_code == 422


def test_search_is_company_scoped_and_query_safe(client: TestClient) -> None:
    a = client.post(f"{API}/companies", json={"name": "A"}).json()["id"]
    b = client.post(f"{API}/companies", json={"name": "B"}).json()["id"]
    client.post(f"{API}/companies/{a}/knowledge", json={"title": "secret", "content": "alpha"})
    assert (
        client.get(f"{API}/companies/{b}/knowledge/search", params={"q": "alpha"}).json()["hits"]
        == []
    )
    weird = client.get(f"{API}/companies/{a}/knowledge/search", params={"q": '"); DROP --*'})
    assert weird.status_code == 200


def test_artifact_import_summary_and_kb_tool(client: TestClient) -> None:
    cid = seed(client)
    root = start(client, cid)
    a = pending_approval(client, cid)
    client.post(
        f"{API}/approvals/{a['id']}/decide", json={"decision": "approve", "checksum": a["checksum"]}
    )
    wait_for(lambda: task(client, root)["status"] == "completed")

    art = next(
        x
        for r in client.get(f"{API}/companies/{cid}/runs").json()
        for x in client.get(f"{API}/runs/{r['id']}").json()["artifacts"]
        if x["name"] == "audience-research.md"
    )
    k = client.post(f"{API}/artifacts/{art['id']}/to-knowledge", json={}).json()
    assert k["source_type"] == "artifact" and k["source_id"] == art["id"]
    assert "25–35" in k["content"]

    s = client.post(f"{API}/tasks/{root}/summarize")
    assert s.status_code == 201, s.text
    s = s.json()
    assert s["kind"] == "summary" and s["source_id"] == root
    assert "không dùng AI" in s["content"] and "Duyệt kịch bản" in s["content"]
    assert "2 lần chạy" in s["content"]  # the retried Reviewer task

    # The Researcher's kb.search tool (L0) goes through the gateway and is recorded.
    events = client.get(f"{API}/companies/{cid}/events", params={"limit": 1000}).json()["items"]
    assert any(
        e["event_type"] == "tool.call_finished"
        and e["payload"]["tool_key"] == "kb.search"
        and e["payload"]["ok"]
        for e in events
    )
    # ...and the imported document is now findable by that same query.
    hits = client.get(f"{API}/companies/{cid}/knowledge/search", params={"q": "khán giả"}).json()
    assert k["id"] in [h["id"] for h in hits["hits"]]


def test_summary_requires_finished_task(client: TestClient) -> None:
    cid = seed(client)
    root = start(client, cid)
    pending_approval(client, cid)
    assert client.post(f"{API}/tasks/{root}/summarize").status_code == 409


def test_lesson_review_flow(client: TestClient, company: dict) -> None:
    cid = company["id"]
    lesson = client.post(
        f"{API}/companies/{cid}/lessons",
        json={"title": "Chốt sớm", "lesson": "Chốt thông điệp trước."},
    ).json()
    assert lesson["review_status"] == "proposed"
    assert client.get(f"{API}/companies/{cid}/knowledge").json() == []
    r = client.post(f"{API}/lessons/{lesson['id']}/review", json={"decision": "approve"}).json()
    assert r["review_status"] == "approved" and r["knowledge_item_id"]
    item = client.get(f"{API}/knowledge/{r['knowledge_item_id']}").json()
    assert item["kind"] == "lesson" and item["source_type"] == "lesson"
    assert item["source_id"] == lesson["id"]
    again = client.post(f"{API}/lessons/{lesson['id']}/review", json={"decision": "reject"})
    assert again.status_code == 409

    other = client.post(f"{API}/companies/{cid}/lessons", json={"title": "x", "lesson": "y"}).json()
    rej = client.post(
        f"{API}/lessons/{other['id']}/review", json={"decision": "reject", "note": "không đúng"}
    ).json()
    assert rej["review_status"] == "rejected" and rej["knowledge_item_id"] is None


def test_role_proposal_validation_and_instructions(client: TestClient) -> None:
    cid = seed(client)
    roles = agents_by_role(client, cid)
    # CEO reporting to its own report would be a cycle: approval fails, proposal stays open.
    p = client.post(
        f"{API}/companies/{cid}/role-proposals",
        json={
            "agent_id": roles["CEO"]["id"],
            "changes": {"reports_to_agent_id": roles["CMO"]["id"]},
            "rationale": "thử",
        },
    ).json()
    r = client.post(f"{API}/role-proposals/{p['id']}/review", json={"decision": "approve"})
    assert r.status_code == 422
    assert client.get(f"{API}/companies/{cid}/role-proposals").json()[0]["status"] == "proposed"

    q = client.post(
        f"{API}/companies/{cid}/role-proposals",
        json={
            "agent_id": roles["Reviewer"]["id"],
            "changes": {"instructions": "Duyệt theo checklist 5 điểm."},
        },
    ).json()
    client.post(f"{API}/role-proposals/{q['id']}/review", json={"decision": "approve"})
    agent = client.get(f"{API}/agents/{roles['Reviewer']['id']}").json()
    assert agent["current_version"]["version_number"] == 2
    assert agent["current_version"]["definition"]["instructions"] == "Duyệt theo checklist 5 điểm."

    empty = client.post(
        f"{API}/companies/{cid}/role-proposals",
        json={"agent_id": roles["CEO"]["id"], "changes": {}},
    )
    assert empty.status_code == 422


def test_search_handles_vietnamese_d(client: TestClient, company: dict) -> None:
    cid = company["id"]
    client.post(
        f"{API}/companies/{cid}/knowledge",
        json={"title": "Chốt thông điệp", "content": "Đối tượng là nhân viên văn phòng."},
    )
    for q in ("thong diep", "thông điệp", "doi tuong", "ĐỐI"):
        hits = client.get(f"{API}/companies/{cid}/knowledge/search", params={"q": q}).json()["hits"]
        assert len(hits) == 1, q
    assert "Đối tượng" in hits[0]["snippet"]


def test_like_fallback_matches_fts_behaviour(container, company: dict) -> None:
    import uuid as _uuid

    from orchestra_backend.knowledge import service as kn
    from orchestra_backend.knowledge.schemas import KnowledgeCreate

    cid = _uuid.UUID(company["id"])
    with container.tx() as s:
        kn.create_note(s, cid, KnowledgeCreate(title="Thông điệp", content="Đối tượng 25 tuổi"))
    original = kn.fts_available
    kn.fts_available = lambda s: False  # type: ignore[assignment]
    try:
        with container.tx() as s:
            res = kn.search(s, cid, "doi tuong")
    finally:
        kn.fts_available = original  # type: ignore[assignment]
    assert res.engine == "like" and len(res.hits) == 1
