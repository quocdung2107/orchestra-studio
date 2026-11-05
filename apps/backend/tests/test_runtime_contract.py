"""One contract for every model-backed runtime (ADR-0022). No network: fake transports."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest

from orchestra_backend.runtime import normalize
from orchestra_backend.runtime.interface import RunRequest, ToolResult
from tests.fake_providers import (
    IN_TOK,
    OUT_TOK,
    SECRET,
    FakeServer,
    handle_for,
    make_runtime,
    settings_for,
)

PROVIDERS = ["anthropic", "openai", "ollama"]
TERMINAL = {"run.completed", "run.failed", "run.cancelled"}


class RecordingTools:
    def __init__(self, result: ToolResult | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.result = result or ToolResult(ok=True, data={"hits": [{"title": "Ghi chú A"}]})

    async def call(self, tool_key: str, params: dict[str, Any]) -> ToolResult:
        self.calls.append((tool_key, params))
        return self.result


def _request(provider: str, tools: RecordingTools | None = None, **settings: Any) -> RunRequest:
    return RunRequest(
        run_id=uuid.uuid4(),
        agent={
            "id": str(uuid.uuid4()),
            "name": "Biên kịch",
            "role": "scriptwriter",
            "definition": {"instructions": "Viết kịch bản ngắn.", "goals": ["Rõ ràng"]},
        },
        task={"id": str(uuid.uuid4()), "title": "Kịch bản video 30s", "description": "Về trà"},
        tools=tools or RecordingTools(),
        settings=settings_for(provider, **settings),
        tool_specs=[
            {
                "key": "kb.search",
                "name": "Tìm tri thức",
                "description": "Tìm trong kho tri thức",
                "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
            }
        ],
        credential=handle_for(provider),
    )


async def _collect(rt, req: RunRequest) -> list:  # type: ignore[no-untyped-def]
    return [ev async for ev in rt.execute(req)]


def run(rt, req: RunRequest) -> list:  # type: ignore[no-untyped-def]
    return asyncio.run(_collect(rt, req))


def _assert_protocol(events: list) -> None:
    """Every event validates; started first; exactly one terminal, last."""
    types = [e.type for e in events]
    assert types[0] == "run.started"
    assert sum(t in TERMINAL for t in types) == 1
    assert types[-1] in TERMINAL
    for e in events:
        normalize.validate(e)  # raises RuntimeProtocolError on contract violation


def _no_secret(events: list) -> None:
    blob = json.dumps([e.data for e in events], ensure_ascii=False, default=str)
    for s in SECRET.values():
        assert s not in blob


# ---------------------------------------------------------------- contract


@pytest.mark.parametrize("provider", PROVIDERS)
def test_text_answer_produces_message_artifact_and_completion(provider: str) -> None:
    server = FakeServer(provider, [("text", "Kịch bản: mở cảnh ấm trà.\n\nCảnh 1...")])
    events = run(make_runtime(provider, server), _request(provider))
    _assert_protocol(events)
    types = [e.type for e in events]
    assert types[-1] == "run.completed"
    art = next(e for e in events if e.type == "run.artifact.produced")
    assert art.data["mime_type"] == "text/markdown"
    assert art.data["content"].startswith("Kịch bản")
    assert (
        next(e for e in events if e.type == "run.completed").data["summary"].startswith("Kịch bản")
    )
    _no_secret(events)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_usage_is_reported_with_source_label(provider: str) -> None:
    server = FakeServer(provider, [("text", "ok")])
    events = run(make_runtime(provider, server), _request(provider))
    usage = [normalize.validate(e) for e in events if e.type == "run.usage"]
    assert len(usage) == 1
    u = usage[0]
    assert (u.input_tokens, u.output_tokens) == (IN_TOK, OUT_TOK)
    assert u.provider == provider
    expected = "local_runtime_reported" if provider == "ollama" else "provider_reported"
    assert u.source == expected


@pytest.mark.parametrize("provider", PROVIDERS)
def test_tool_calls_go_through_tool_port_and_results_return(provider: str) -> None:
    tools = RecordingTools()
    server = FakeServer(
        provider, [("tool", "kb__search", {"q": "trà"}), ("text", "Xong, dùng ghi chú A.")]
    )
    events = run(make_runtime(provider, server), _request(provider, tools))
    _assert_protocol(events)
    assert tools.calls == [("kb.search", {"q": "trà"})]  # dotted key restored
    assert events[-1].type == "run.completed"
    assert sum(e.type == "run.usage" for e in events) == 2
    # The second request carried the tool result back to the model.
    second = json.dumps(server.requests[1], ensure_ascii=False)
    assert "Ghi chú A" in second
    # Tools were offered with provider-safe names.
    assert "kb__search" in json.dumps(server.requests[0])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_unknown_tool_is_reported_to_model_not_executed(provider: str) -> None:
    tools = RecordingTools()
    server = FakeServer(provider, [("tool", "rm_rf", {}), ("text", "Không dùng được tool.")])
    events = run(make_runtime(provider, server), _request(provider, tools))
    assert tools.calls == []
    assert events[-1].type == "run.completed"
    assert "UNKNOWN_TOOL" in json.dumps(server.requests[1])


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (429, "PROVIDER_RATE_LIMITED", True),
        (500, "PROVIDER_UNAVAILABLE", True),
        (401, "PROVIDER_AUTH_FAILED", False),
        (404, "MODEL_NOT_FOUND", False),
        (400, "PROVIDER_BAD_REQUEST", False),
    ],
)
def test_errors_are_classified(provider: str, status: int, code: str, retryable: bool) -> None:
    server = FakeServer(provider, [("status", status, "boom")])
    events = run(make_runtime(provider, server), _request(provider))
    _assert_protocol(events)
    failed = events[-1]
    assert failed.type == "run.failed"
    assert failed.data["error_code"] == code
    assert failed.data["retryable"] is retryable


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_secret_echoed_by_provider_is_redacted(provider: str) -> None:
    server = FakeServer(provider, [("status", 401, f"invalid key {SECRET[provider]}")])
    events = run(make_runtime(provider, server), _request(provider))
    assert events[-1].data["error_code"] == "PROVIDER_AUTH_FAILED"
    _no_secret(events)


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_missing_credential_fails_without_calling_provider(provider: str) -> None:
    server = FakeServer(provider, [("text", "never")])
    req = _request(provider)
    req = RunRequest(**{**req.__dict__, "credential": None})
    events = run(make_runtime(provider, server), req)
    assert events[-1].data["error_code"] == "CREDENTIAL_MISSING"
    assert server.requests == []


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_refusal_fails_without_retry(provider: str) -> None:
    server = FakeServer(provider, [("refusal", "cyber")])
    events = run(make_runtime(provider, server), _request(provider))
    _assert_protocol(events)
    assert events[-1].data["error_code"] == "PROVIDER_REFUSED"
    assert events[-1].data["retryable"] is False


@pytest.mark.parametrize("provider", PROVIDERS)
def test_max_turns_is_enforced(provider: str) -> None:
    server = FakeServer(provider, [("tool", "kb__search", {"q": str(i)}) for i in range(5)])
    events = run(make_runtime(provider, server), _request(provider, max_turns=2))
    assert events[-1].data["error_code"] == "MAX_TURNS_EXCEEDED"
    assert len(server.requests) == 2


@pytest.mark.parametrize("provider", PROVIDERS)
def test_cancel_stops_an_in_flight_call(provider: str) -> None:
    server = FakeServer(provider, [("hang",)])
    rt = make_runtime(provider, server)
    req = _request(provider)

    async def go() -> list:
        out = []
        async for ev in rt.execute(req):
            out.append(ev)
            if ev.type == "run.progress":
                asyncio.get_running_loop().call_later(0.05, rt.cancel, req.run_id)
        return out

    events = asyncio.run(asyncio.wait_for(go(), 5))
    _assert_protocol(events)
    assert events[-1].type == "run.cancelled"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_capabilities_and_settings_validation(provider: str) -> None:
    rt = make_runtime(provider, FakeServer(provider, []))
    caps = rt.capabilities.as_dict()
    assert caps["supports_cancel"] and caps["supports_tool_calls"]
    assert not caps["supports_pause"] and not caps["supports_resume"]
    assert rt.validate_settings(settings_for(provider))["max_turns"] == 8
    from orchestra_backend.core.errors import DomainValidationError

    with pytest.raises(DomainValidationError):
        rt.validate_settings({**settings_for(provider), "api_key": "x"})


@pytest.mark.parametrize("provider", PROVIDERS)
def test_health_check_shape(provider: str) -> None:
    rt = make_runtime(provider, FakeServer(provider, []))
    health = asyncio.run(rt.health_check())
    assert health["status"] in {"ok", "unreachable"}


# ---------------------------------------------------------------- provider specifics


def test_anthropic_request_shape() -> None:
    server = FakeServer("anthropic", [("text", "ok")])
    run(make_runtime("anthropic", server), _request("anthropic"))
    body, headers = server.requests[0], server.headers[0]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in headers["anthropic-beta"]
    assert "temperature" not in body
    assert "Biên kịch" in body["system"]


def test_anthropic_fallbacks_off_for_unsupported_model() -> None:
    server = FakeServer("anthropic", [("text", "ok")])
    run(make_runtime("anthropic", server), _request("anthropic", model="claude-haiku-5-5"))
    assert "fallbacks" not in server.requests[0]
    assert "anthropic-beta" not in server.headers[0]


def test_anthropic_echo_drops_pre_fallback_tool_use() -> None:
    from orchestra_backend.runtime.llm.anthropic_rt import _echo

    class B:
        def __init__(self, **kw: Any) -> None:
            self.kw = kw

        def model_dump(self, **_: Any) -> dict[str, Any]:
            return self.kw

    out = _echo(
        [
            B(type="text", text="a"),
            B(type="tool_use", id="x", name="t", input={}),
            B(type="fallback", **{"from": {"model": "m1"}, "to": {"model": "m2"}}),
            B(type="text", text="b"),
        ]
    )
    assert [b["type"] for b in out] == ["text", "text"]


def test_ollama_health_shows_resources_and_limits() -> None:
    rt = make_runtime("ollama", FakeServer("ollama", []), max_concurrency=2)
    h = asyncio.run(rt.health_check())
    assert h["status"] == "ok" and h["version"] == "0.12.0"
    assert h["limits"] == {"max_concurrency": 2, "running": 0, "waiting": 0}
    assert h["models"][0]["parameter_size"] == "8B"
    assert h["loaded"][0]["vram_bytes"] == 5_500_000_000


def test_ollama_concurrency_limit_queues_second_run() -> None:
    server = FakeServer("ollama", [("hang",)])
    rt = make_runtime("ollama", server, max_concurrency=1)
    a, b = _request("ollama"), _request("ollama")

    async def go() -> tuple[list, list]:
        first: list = []
        second: list = []

        async def consume(req: RunRequest, out: list) -> None:
            async for ev in rt.execute(req):
                out.append(ev)

        ta = asyncio.create_task(consume(a, first))
        await asyncio.sleep(0.05)
        tb = asyncio.create_task(consume(b, second))
        await asyncio.sleep(0.05)
        assert rt._waiting == 1 and rt._running == 1
        assert second == []  # still queued: no run.started yet
        rt.cancel(a.run_id)
        await ta
        await tb  # the queued run now gets the slot and answers "done"
        return first, second

    first, second = asyncio.run(asyncio.wait_for(go(), 5))
    assert first[-1].type == "run.cancelled"
    assert second[0].type == "run.started" and second[-1].type == "run.completed"
    assert rt._running == 0


def test_ollama_unreachable_is_retryable() -> None:
    import httpx2

    from orchestra_backend.runtime.llm.ollama_rt import OllamaRuntime

    def boom(_req: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused")

    rt = OllamaRuntime(transport=httpx2.MockTransport(boom), base_url="http://ollama.test")
    events = run(rt, _request("ollama"))
    assert events[-1].data["error_code"] == "PROVIDER_UNAVAILABLE"
    assert events[-1].data["retryable"] is True
    assert asyncio.run(rt.health_check())["status"] == "unreachable"


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_verify_lists_models(provider: str) -> None:
    rt = make_runtime(provider, FakeServer(provider, []))
    ok, msg = asyncio.run(rt.verify(SECRET[provider]))
    assert ok, msg
