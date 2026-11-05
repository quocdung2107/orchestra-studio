"""P4: credentials, model runtimes end to end, usage/cost metrics, KPIs, local resources."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.fake_providers import SECRET, FakeServer
from tests.test_orchestration_p2 import agents_by_role, seed, task, wait_for

API = "/api/v1"


def registry(client: TestClient):  # type: ignore[no-untyped-def]
    return client.app.state.container.extras["registry"]  # type: ignore[attr-defined]


def install_fake(client: TestClient, provider: str, script: list[tuple]) -> FakeServer:
    server = FakeServer(provider, script)
    rt = registry(client).get(provider)
    rt.transport = server.transport()
    if hasattr(rt, "max_retries"):
        rt.max_retries = 0
    if provider == "ollama":
        rt.base_url = "http://ollama.test"
    return server


def add_credential(client: TestClient, provider: str = "anthropic", **kw: object) -> dict:
    body = {"provider": provider, "label": f"{provider} chính", "secret": SECRET[provider], **kw}
    r = client.post(f"{API}/credentials", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def set_runtime(client: TestClient, agent: dict, runtime_id: str, settings: dict) -> object:
    detail = client.get(f"{API}/agents/{agent['id']}").json()
    return client.post(
        f"{API}/agents/{agent['id']}/versions",
        json={
            "definition": detail["current_version"]["definition"],
            "runtime": {"runtime_id": runtime_id, "settings": settings},
        },
    )


def start_task(client: TestClient, cid: str, agent: dict, title: str = "Viết kịch bản trà") -> str:
    r = client.post(
        f"{API}/companies/{cid}/tasks",
        json={"title": title, "description": "Video 30 giây", "assigned_agent_id": agent["id"]},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def finished(client: TestClient, tid: str) -> dict:
    return wait_for(  # type: ignore[return-value]
        lambda: (t := task(client, tid))["status"] in {"completed", "failed", "cancelled"} and t
    )


def runs_of(client: TestClient, tid: str) -> list[dict]:
    cid = task(client, tid)["company_id"]
    return client.get(f"{API}/companies/{cid}/runs", params={"task_id": tid}).json()


def events_of(client: TestClient, cid: str) -> list[dict]:
    return client.get(f"{API}/companies/{cid}/events", params={"limit": 1000}).json()["items"]


# ---------------------------------------------------------------- credentials


def test_credential_lifecycle_never_returns_secret(client: TestClient) -> None:
    info = client.get(f"{API}/secret-store").json()
    assert info["kind"] == "memory" and info["secure"] is False

    cred = add_credential(client)
    assert SECRET["anthropic"] not in json.dumps(cred)
    assert cred["store"] == "memory" and cred["status"] == "active"

    listed = client.get(f"{API}/credentials").json()
    assert [c["id"] for c in listed] == [cred["id"]]
    assert SECRET["anthropic"] not in json.dumps(listed)

    rotated = client.post(
        f"{API}/credentials/{cred['id']}/rotate", json={"secret": "sk-ant-new-ROTATED-99999999"}
    ).json()
    assert rotated["rotated_at"] is not None

    revoked = client.post(f"{API}/credentials/{cred['id']}/revoke").json()
    assert revoked["status"] == "revoked"
    store = client.app.state.container.extras["secrets"]  # type: ignore[attr-defined]
    assert store.get(cred["id"]) is None  # secret removed from the store
    r = client.post(
        f"{API}/credentials/{cred['id']}/rotate", json={"secret": "sk-ant-again-1234567890"}
    )
    assert r.status_code == 409


def test_credential_needs_exactly_one_source(client: TestClient) -> None:
    both = {"provider": "openai", "label": "x", "secret": "sk-12345678", "env_var": "OPENAI_KEY"}
    assert client.post(f"{API}/credentials", json=both).status_code == 422
    neither = {"provider": "openai", "label": "x"}
    assert client.post(f"{API}/credentials", json=neither).status_code == 422
    env = client.post(
        f"{API}/credentials", json={"provider": "openai", "label": "env", "env_var": "MY_OPENAI"}
    ).json()
    assert env["store"] == "env" and env["env_var"] == "MY_OPENAI"


def test_company_scoped_credential_emits_events_without_secret(client: TestClient) -> None:
    cid = seed(client)
    add_credential(client, company_id=cid)
    events = events_of(client, cid)
    created = [e for e in events if e["event_type"] == "credential.created"]
    assert len(created) == 1
    assert SECRET["anthropic"] not in json.dumps(events)


def test_verify_credential_calls_provider(client: TestClient) -> None:
    install_fake(client, "anthropic", [])
    cred = add_credential(client)
    res = client.post(f"{API}/credentials/{cred['id']}/verify").json()
    assert res["ok"] is True
    again = client.get(f"{API}/credentials").json()[0]
    assert again["last_verify_ok"] is True


def test_env_credential_missing_variable_fails_verify(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ORCH_TEST_MISSING", raising=False)
    cred = client.post(
        f"{API}/credentials",
        json={"provider": "anthropic", "label": "env", "env_var": "ORCH_TEST_MISSING"},
    ).json()
    res = client.post(f"{API}/credentials/{cred['id']}/verify").json()
    assert res["ok"] is False


# ---------------------------------------------------------------- agent settings


def test_agent_runtime_settings_are_validated(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    # Missing credential -> 422; secret-like key -> 422; unknown credential -> 404/422.
    assert set_runtime(client, writer, "anthropic", {}).status_code == 422
    assert set_runtime(client, writer, "anthropic", {"api_key": "x"}).status_code == 422
    cred = add_credential(client)
    ok = set_runtime(client, writer, "anthropic", {"credential_id": cred["id"]})
    assert ok.status_code == 201, ok.text
    saved = ok.json()["current_version"]["runtime"]["settings"]
    assert saved["model"] == "claude-opus-5-5" and saved["effort"] == "medium"
    # Wrong provider
    oa = add_credential(client, "openai")
    bad = set_runtime(client, writer, "anthropic", {"credential_id": oa["id"]})
    assert bad.status_code == 422
    # Revoked
    client.post(f"{API}/credentials/{cred['id']}/revoke")
    assert (
        set_runtime(client, writer, "anthropic", {"credential_id": cred["id"]}).status_code == 422
    )


# ---------------------------------------------------------------- end to end


def test_claude_run_end_to_end_records_usage_cost_and_kpis(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    server = install_fake(
        client,
        "anthropic",
        [
            ("tool", "doc__draft", {"title": "Dàn ý", "body": "Cảnh 1"}),
            ("text", "Kịch bản trà 30 giây.\n\nCảnh 1: ấm trà."),
        ],
    )
    cred = add_credential(client)
    assert (
        set_runtime(client, writer, "anthropic", {"credential_id": cred["id"]}).status_code == 201
    )

    tid = start_task(client, cid, writer)
    t = finished(client, tid)
    assert t["status"] == "completed", runs_of(client, tid)
    run = runs_of(client, tid)[0]
    assert run["runtime_id"] == "anthropic"
    assert run["result_summary"].startswith("Kịch bản trà")

    # The tool went through the gateway (doc.draft makes an artifact) + the final answer artifact.
    arts = client.get(f"{API}/runs/{run['id']}").json()["artifacts"]
    assert len(arts) == 2
    assert "Viết kịch bản trà.md" in {a["name"] for a in arts}
    assert "doc__draft" in json.dumps(server.requests[0])

    # Usage + cost with labels.
    events = events_of(client, cid)
    usage = [e for e in events if e["event_type"] == "agent.run.usage_recorded"]
    assert len(usage) == 2
    assert usage[0]["payload"]["token_source"] == "provider_reported"
    assert usage[0]["payload"]["cost_source"] == "price_table_estimate"
    assert usage[0]["payload"]["price_as_of"] == "2026-10-06"
    assert SECRET["anthropic"] not in json.dumps(events)

    k = client.get(f"{API}/companies/{cid}/kpis").json()
    assert k["totals"]["completed"] == 1
    assert k["totals"]["tokens_input"] == 22 and k["totals"]["tokens_output"] == 14
    # 22 * $4/M + 14 * $20/M
    assert k["totals"]["cost_usd"] == pytest.approx((22 * 4 + 14 * 20) / 1e6)
    assert k["totals"]["priced_runs"] == 1 and k["totals"]["unpriced_runs"] == 0
    assert k["sources"]["cost"]["confidence"] == "estimated"
    assert k["sources"]["tokens"]["confidence"] == "reported"
    by_rt = {r["runtime_id"]: r for r in k["by_runtime"]}
    assert by_rt["anthropic"]["model_calls"] == 2
    assert any(a["agent_id"] == writer["id"] for a in k["by_agent"])


def test_secret_never_persisted_in_database(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    install_fake(client, "anthropic", [("status", 401, f"bad key {SECRET['anthropic']}")])
    cred = add_credential(client, company_id=cid)
    set_runtime(client, writer, "anthropic", {"credential_id": cred["id"]})
    tid = start_task(client, cid, writer)
    assert finished(client, tid)["status"] == "failed"
    assert runs_of(client, tid)[0]["error_code"] == "PROVIDER_AUTH_FAILED"
    engine = client.app.state.container.engine  # type: ignore[attr-defined]
    with engine.connect() as conn:
        tables = [
            r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        ]
        for t in tables:
            if t.startswith("knowledge_fts"):
                continue
            for row in conn.execute(text(f'SELECT * FROM "{t}"')):  # noqa: S608 - test only
                assert SECRET["anthropic"] not in json.dumps([str(v) for v in row])


def test_unpriced_openai_model_is_labelled_not_guessed(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    install_fake(client, "openai", [("text", "Xong.")])
    cred = add_credential(client, "openai")
    r = set_runtime(client, writer, "openai", {"model": "gpt-test", "credential_id": cred["id"]})
    assert r.status_code == 201, r.text
    tid = start_task(client, cid, writer)
    assert finished(client, tid)["status"] == "completed"
    k = client.get(f"{API}/companies/{cid}/kpis").json()["totals"]
    assert k["tokens_input"] == 11 and k["cost_usd"] == 0
    assert k["llm_runs"] == 1 and k["unpriced_runs"] == 1


def test_ollama_run_costs_no_api_fee(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    install_fake(client, "ollama", [("text", "Bản nháp cục bộ.")])
    r = set_runtime(client, writer, "ollama", {"model": "llama-test:8b"})
    assert r.status_code == 201, r.text
    tid = start_task(client, cid, writer)
    assert finished(client, tid)["status"] == "completed"
    events = events_of(client, cid)
    u = next(e for e in events if e["event_type"] == "agent.run.usage_recorded")["payload"]
    assert u["token_source"] == "local_runtime_reported"
    assert u["cost_usd"] == 0 and u["cost_source"] == "local_no_api_fee"
    health = client.get(f"{API}/runtimes/ollama/health").json()
    assert health["status"] == "ok" and health["limits"]["max_concurrency"] == 1


def test_revoked_credential_fails_run_before_calling_provider(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    server = install_fake(client, "anthropic", [("text", "never")])
    cred = add_credential(client)
    set_runtime(client, writer, "anthropic", {"credential_id": cred["id"]})
    client.post(f"{API}/credentials/{cred['id']}/revoke")
    tid = start_task(client, cid, writer)
    assert finished(client, tid)["status"] == "failed"
    assert runs_of(client, tid)[0]["error_code"] == "CREDENTIAL_REVOKED"
    assert server.requests == []


def test_retryable_provider_error_creates_new_attempt(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    install_fake(client, "anthropic", [("status", 529, "overloaded"), ("text", "Lần hai ổn.")])
    cred = add_credential(client)
    set_runtime(client, writer, "anthropic", {"credential_id": cred["id"]})
    r = client.post(
        f"{API}/companies/{cid}/tasks",
        json={"title": "Thử lại", "assigned_agent_id": writer["id"], "max_attempts": 2},
    )
    tid = r.json()["id"]
    assert finished(client, tid)["status"] == "completed"
    runs = sorted(runs_of(client, tid), key=lambda x: x["attempt"])
    assert [x["status"] for x in runs] == ["failed", "completed"]
    assert runs[0]["error_code"] == "PROVIDER_UNAVAILABLE"


def test_model_run_cancel_works_and_pause_is_not_supported(client: TestClient) -> None:
    cid = seed(client)
    writer = agents_by_role(client, cid)["Scriptwriter"]
    install_fake(client, "anthropic", [("hang",)])
    cred = add_credential(client)
    set_runtime(client, writer, "anthropic", {"credential_id": cred["id"]})
    tid = start_task(client, cid, writer)
    run = wait_for(
        lambda: next((r for r in runs_of(client, tid) if r["status"] == "running"), None)
    )
    r = client.post(f"{API}/runs/{run['id']}/pause")  # type: ignore[index]
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_supported"
    assert client.post(f"{API}/tasks/{tid}/cancel").status_code in (200, 202, 204)
    assert finished(client, tid)["status"] == "cancelled"


def test_keyring_store_refuses_insecure_backend() -> None:
    import keyring
    from keyring.backends import fail

    from orchestra_backend.credentials.store import KeyringSecretStore, SecretStoreUnavailable

    old = keyring.get_keyring()
    keyring.set_keyring(fail.Keyring())
    try:
        store = KeyringSecretStore()
        assert store.secure is False
        with pytest.raises(SecretStoreUnavailable):
            store.set("x", "sk-ant-should-not-store-123")
        assert store.get("x") is None
    finally:
        keyring.set_keyring(old)


def test_keyring_store_round_trip_with_secure_backend() -> None:
    import keyring
    from keyring.backend import KeyringBackend

    from orchestra_backend.credentials.store import KeyringSecretStore

    class Vault(KeyringBackend):
        priority = 1  # type: ignore[assignment]
        data: dict = {}

        def set_password(self, service: str, username: str, password: str) -> None:
            self.data[(service, username)] = password

        def get_password(self, service: str, username: str) -> str | None:
            return self.data.get((service, username))

        def delete_password(self, service: str, username: str) -> None:
            self.data.pop((service, username), None)

    old = keyring.get_keyring()
    keyring.set_keyring(Vault())
    try:
        store = KeyringSecretStore()
        assert store.secure
        store.set("abc", "sk-ant-stored-123456789")
        assert store.get("abc") == "sk-ant-stored-123456789"
        assert Vault.data[("orchestra-studio", "abc")] == "sk-ant-stored-123456789"
        store.delete("abc")
        assert store.get("abc") is None
    finally:
        keyring.set_keyring(old)


def test_redaction_masks_known_and_pattern_secrets() -> None:
    from orchestra_backend.core.redact import redact, register_secret

    register_secret("plain-secret-value-xyz")
    out = redact("a plain-secret-value-xyz b sk-ant-abcdefghijkl c Bearer abcdefghijklmnopqrstu")
    assert "plain-secret-value-xyz" not in out
    assert "sk-ant-abcdefghijkl" not in out
    assert "abcdefghijklmnopqrstu" not in out


# ---------------------------------------------------------------- P5: team.delegate (ADR-0026)


def _tool_results(server: FakeServer, n: int) -> str:
    return json.dumps(server.requests[n]["messages"], ensure_ascii=False)


def test_model_agent_delegates_to_direct_report_sharing_one_ollama_slot(
    client: TestClient,
) -> None:
    cid = seed(client)
    roles = agents_by_role(client, cid)
    cmo, writer = roles["Producer"], roles["Scriptwriter"]
    assert writer["reports_to_agent_id"] == cmo["id"]
    # Parent and child both on Ollama with max_concurrency 1: the parent must hand back
    # its slot while waiting, or this deadlocks.
    server = install_fake(
        client,
        "ollama",
        [
            ("tool", "team__delegate", {"to_role": "Scriptwriter", "title": "Viết kịch bản"}),
            ("text", "Kịch bản của cấp dưới."),
            ("text", "Đã duyệt kịch bản."),
        ],
    )
    for a in (cmo, writer):
        assert set_runtime(client, a, "ollama", {"model": "llama-test:8b"}).status_code == 201
    tid = start_task(client, cid, cmo, title="Chiến dịch trà sen")
    assert finished(client, tid)["status"] == "completed"

    spec = next(t for t in server.requests[0]["tools"] if t["function"]["name"] == "team__delegate")
    assert "Scriptwriter" in spec["function"]["parameters"]["properties"]["to_role"]["enum"]
    assert "team__delegate" not in json.dumps(server.requests[1].get("tools", []))  # leaf agent
    fed_back = _tool_results(server, 2)
    assert '\\"status\\": \\"completed\\"' in fed_back and "Kịch bản của cấp dưới" in fed_back

    tasks = client.get(f"{API}/companies/{cid}/tasks").json()
    child = next(t for t in tasks if t["parent_task_id"] == tid)
    assert child["assigned_agent_id"] == writer["id"] and child["status"] == "completed"


def test_model_agent_cannot_delegate_outside_direct_reports(client: TestClient) -> None:
    cid = seed(client)
    roles = agents_by_role(client, cid)
    cmo = roles["Producer"]
    server = install_fake(
        client,
        "ollama",
        [
            ("tool", "team__delegate", {"to_role": "CEO", "title": "Làm hộ"}),
            ("text", "Tự làm vậy."),
        ],
    )
    assert set_runtime(client, cmo, "ollama", {"model": "llama-test:8b"}).status_code == 201
    tid = start_task(client, cid, cmo)
    assert finished(client, tid)["status"] == "completed"
    assert "DELEGATION_NOT_ALLOWED" in _tool_results(server, 1)
    tasks = client.get(f"{API}/companies/{cid}/tasks").json()
    assert not [t for t in tasks if t["parent_task_id"] == tid]


def test_model_agent_delegation_limit_per_run(client: TestClient) -> None:
    from orchestra_backend.orchestrator.service import MAX_TOOL_DELEGATIONS

    cid = seed(client)
    roles = agents_by_role(client, cid)
    cmo = roles["Producer"]
    call = ("tool", "team__delegate", {"to_role": "Scriptwriter", "title": "Bản nháp"})
    server = install_fake(
        client, "ollama", [call] * (MAX_TOOL_DELEGATIONS + 1) + [("text", "Xong.")]
    )
    assert (
        set_runtime(client, cmo, "ollama", {"model": "llama-test:8b", "max_turns": 10}).status_code
        == 201
    )
    tid = start_task(client, cid, cmo)
    assert finished(client, tid)["status"] == "completed"
    assert "DELEGATION_LIMIT" in _tool_results(server, MAX_TOOL_DELEGATIONS + 1)
    tasks = client.get(f"{API}/companies/{cid}/tasks").json()
    assert len([t for t in tasks if t["parent_task_id"] == tid]) == MAX_TOOL_DELEGATIONS
