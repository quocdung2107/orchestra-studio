"""Scripted fake model servers in each provider's wire format (no network).

A script is a list of steps, each one model response:
  ("text", "final answer")          - plain answer
  ("tool", "kb__search", {"q": 1})   - one tool call
  ("status", 429, "message")         - HTTP error
  ("refusal", "cyber")               - provider refusal
  ("hang",)                          - never answers (for cancel tests)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx2

from orchestra_backend.credentials.store import MemorySecretStore, SecretHandle
from orchestra_backend.runtime.llm.anthropic_rt import AnthropicRuntime
from orchestra_backend.runtime.llm.ollama_rt import OllamaRuntime
from orchestra_backend.runtime.llm.openai_rt import OpenAIRuntime

SECRET = {"anthropic": "sk-ant-test-SECRET-0123456789", "openai": "sk-test-SECRET-0123456789abcd"}
IN_TOK, OUT_TOK = 11, 7


class FakeServer:
    def __init__(self, provider: str, script: list[tuple]) -> None:
        self.provider = provider
        self.script = list(script)
        self.requests: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []

    # ---- transport ----

    async def handle(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if request.method == "GET":
            return self._get(path)
        self.requests.append(json.loads(request.content or b"{}"))
        self.headers.append(dict(request.headers))
        step = self.script.pop(0) if self.script else ("text", "done")
        kind = step[0]
        if kind == "hang":
            await asyncio.Event().wait()
        if kind == "status":
            return self._error(step[1], step[2])
        return httpx2.Response(200, json=self._ok(step))

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handle)

    # ---- wire formats ----

    def _get(self, path: str) -> httpx2.Response:
        if path.endswith("/models"):  # anthropic + openai verify
            if self.provider == "anthropic":
                return httpx2.Response(
                    200,
                    json={
                        "data": [
                            {
                                "type": "model",
                                "id": "claude-opus-5-5",
                                "display_name": "Claude Opus 5.5",
                                "created_at": "2026-10-01T00:00:00Z",
                            }
                        ],
                        "has_more": False,
                        "first_id": "claude-opus-5-5",
                        "last_id": "claude-opus-5-5",
                    },
                )
            return httpx2.Response(
                200,
                json={
                    "object": "list",
                    "data": [{"id": "gpt-test", "object": "model", "created": 1, "owned_by": "x"}],
                },
            )
        if path == "/api/version":
            return httpx2.Response(200, json={"version": "0.12.0"})
        if path == "/api/tags":
            return httpx2.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "llama-test:8b",
                            "size": 4_900_000_000,
                            "details": {
                                "parameter_size": "8B",
                                "quantization_level": "Q4_K_M",
                                "family": "llama",
                            },
                        }
                    ]
                },
            )
        if path == "/api/ps":
            return httpx2.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "llama-test:8b",
                            "size": 6_000_000_000,
                            "size_vram": 5_500_000_000,
                            "expires_at": "2026-11-05T12:00:00Z",
                            "context_length": 8192,
                        }
                    ]
                },
            )
        return httpx2.Response(404, json={"error": "not found"})

    def _error(self, status: int, message: str) -> httpx2.Response:
        if self.provider == "anthropic":
            body = {"type": "error", "error": {"type": "api_error", "message": message}}
        elif self.provider == "openai":
            body = {"error": {"message": message, "type": "api_error", "code": None}}
        else:
            body = {"error": message}
        return httpx2.Response(status, json=body)

    def _ok(self, step: tuple) -> dict[str, Any]:
        kind = step[0]
        n = len(self.requests)
        if self.provider == "anthropic":
            usage = {"input_tokens": IN_TOK, "output_tokens": OUT_TOK}
            base = {
                "id": f"msg_{n}",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "stop_sequence": None,
                "usage": usage,
            }
            if kind == "text":
                return {
                    **base,
                    "content": [{"type": "text", "text": step[1]}],
                    "stop_reason": "end_turn",
                }
            if kind == "tool":
                return {
                    **base,
                    "content": [
                        {"type": "text", "text": "Đang tra cứu."},
                        {"type": "tool_use", "id": f"tu_{n}", "name": step[1], "input": step[2]},
                    ],
                    "stop_reason": "tool_use",
                }
            if kind == "refusal":
                return {
                    **base,
                    "content": [],
                    "stop_reason": "refusal",
                    "stop_details": {"type": "refusal", "category": step[1], "explanation": "no"},
                }
        if self.provider == "openai":
            usage = {"prompt_tokens": IN_TOK, "completion_tokens": OUT_TOK, "total_tokens": 18}
            base = {"id": f"c{n}", "object": "chat.completion", "created": 1, "model": "gpt-test"}
            if kind == "text":
                msg = {"role": "assistant", "content": step[1]}
                finish = "stop"
            elif kind == "tool":
                msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call_{n}",
                            "type": "function",
                            "function": {"name": step[1], "arguments": json.dumps(step[2])},
                        }
                    ],
                }
                finish = "tool_calls"
            else:  # refusal
                msg = {"role": "assistant", "content": None, "refusal": f"refused: {step[1]}"}
                finish = "stop"
            return {
                **base,
                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                "usage": usage,
            }
        # ollama
        base = {
            "model": "llama-test:8b",
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": IN_TOK,
            "eval_count": OUT_TOK,
        }
        if kind == "text":
            return {**base, "message": {"role": "assistant", "content": step[1]}}
        if kind == "tool":
            return {
                **base,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": step[1], "arguments": step[2]}}],
                },
            }
        return {**base, "message": {"role": "assistant", "content": ""}}


def make_runtime(provider: str, server: FakeServer, **kw: Any):  # type: ignore[no-untyped-def]
    t = server.transport()
    if provider == "anthropic":
        return AnthropicRuntime(transport=t, max_retries=0)
    if provider == "openai":
        return OpenAIRuntime(transport=t, max_retries=0)
    return OllamaRuntime(transport=t, base_url="http://ollama.test", **kw)


def settings_for(provider: str, **extra: Any) -> dict[str, Any]:
    if provider == "anthropic":
        return {"credential_id": "00000000-0000-0000-0000-000000000001", **extra}
    if provider == "openai":
        return {
            "model": "gpt-test",
            "credential_id": "00000000-0000-0000-0000-000000000002",
            **extra,
        }
    return {"model": "llama-test:8b", **extra}


def handle_for(provider: str) -> SecretHandle | None:
    if provider not in SECRET:
        return None
    store = MemorySecretStore()
    store.set("ref", SECRET[provider])
    return SecretHandle(
        credential_id="cred", provider=provider, store="memory", store_ref="ref", _secrets=store
    )
