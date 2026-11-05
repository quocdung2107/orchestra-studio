"""Claude via the official `anthropic` SDK (ADR-0022)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

import anthropic
import httpx2
from pydantic import Field

from orchestra_backend.runtime.interface import RunRequest
from orchestra_backend.runtime.llm.base import (
    BaseSettingsModel,
    LlmRuntime,
    ProviderError,
    ProviderSession,
    ToolCall,
    ToolCallResult,
    Turn,
    classify_status,
    system_prompt,
    tools_for,
    user_prompt,
)

DEFAULT_MODEL = "claude-opus-5-5"
# Models that accept server-side `fallbacks: "default"` on the Claude API.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicSettings(BaseSettingsModel):
    model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=100)
    credential_id: uuid.UUID
    max_tokens: int = Field(default=16000, ge=256, le=64000)
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    # None = on for models that support it.
    fallbacks: bool | None = None


def _map_error(exc: Exception) -> ProviderError:
    if isinstance(exc, anthropic.APIStatusError):
        return classify_status(exc.status_code, exc.message)
    if isinstance(exc, anthropic.APIConnectionError):  # includes timeouts
        return ProviderError(
            "PROVIDER_UNAVAILABLE", f"Không kết nối được Anthropic: {type(exc).__name__}", True
        )
    raise exc


def _echo(content: list[Any]) -> list[dict[str, Any]]:
    """Assistant turn to send back. Blocks before a mid-output `fallback` marker are dropped
    except text; everything after it is echoed unchanged."""
    blocks = [b.model_dump(mode="json", exclude_none=True) for b in content]
    last = max((i for i, b in enumerate(blocks) if b.get("type") == "fallback"), default=-1)
    if last < 0:
        return blocks
    head = [b for b in blocks[:last] if b.get("type") == "text"]
    return head + blocks[last + 1 :]


class _Session(ProviderSession):
    def __init__(self, client: anthropic.AsyncAnthropic, req: RunRequest, s: AnthropicSettings):
        self.client = client
        self.s = s
        self.system = system_prompt(req)
        self.messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt(req)}]
        self.tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["schema"]}
            for t in tools_for(req)
        ]
        use_fb = s.fallbacks if s.fallbacks is not None else s.model in FALLBACK_MODELS
        self.extra: dict[str, Any] = (
            {"betas": [FALLBACK_BETA], "fallbacks": "default"} if use_fb else {}
        )

    async def send(self, results: list[ToolCallResult] | None) -> Turn:
        if results:
            self.messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r.call.id,
                            "content": r.content,
                            **({} if r.ok else {"is_error": True}),
                        }
                        for r in results
                    ],
                }
            )
        kwargs: dict[str, Any] = dict(
            model=self.s.model,
            max_tokens=self.s.max_tokens,
            system=self.system,
            messages=self.messages,
            output_config={"effort": self.s.effort},
            **self.extra,
        )
        if self.tools:
            kwargs["tools"] = self.tools
        try:
            resp = await self.client.beta.messages.create(**kwargs)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise _map_error(exc) from None

        usage = resp.usage
        turn = Turn(
            model=resp.model,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            turn.stop = "refusal"
            turn.refusal_detail = str(getattr(details, "category", "") or "")
            return turn
        echoed = _echo(resp.content)
        self.messages.append({"role": "assistant", "content": echoed})
        turn.text = "".join(b.get("text", "") for b in echoed if b.get("type") == "text")
        turn.tool_calls = [
            ToolCall(id=b["id"], name=b["name"], args=dict(b.get("input") or {}))
            for b in echoed
            if b.get("type") == "tool_use"
        ]
        if resp.stop_reason == "max_tokens":
            turn.stop = "max_tokens"
        elif turn.tool_calls:
            turn.stop = "tool_use"
        return turn

    async def close(self) -> None:
        await self.client.close()


class AnthropicRuntime(LlmRuntime):
    runtime_id = "anthropic"
    display_name = "Claude (Anthropic API)"
    provider = "anthropic"
    settings_model = AnthropicSettings

    def __init__(
        self,
        *,
        timeout_s: float = 300.0,
        max_retries: int = 2,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__()
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.transport = transport

    def _client(self, api_key: str) -> anthropic.AsyncAnthropic:
        http = (
            anthropic.DefaultAsyncHttpxClient(transport=self.transport) if self.transport else None
        )
        return anthropic.AsyncAnthropic(
            api_key=api_key, timeout=self.timeout_s, max_retries=self.max_retries, http_client=http
        )

    async def open_session(self, req: RunRequest, settings: BaseSettingsModel) -> ProviderSession:
        assert isinstance(settings, AnthropicSettings)
        if req.credential is None:
            raise ProviderError("CREDENTIAL_MISSING", "Agent chưa được gán credential Anthropic")
        return _Session(self._client(req.credential.reveal()), req, settings)

    async def verify(self, secret: str) -> tuple[bool, str]:
        client = self._client(secret)
        try:
            page = await client.models.list(limit=1)
            first = page.data[0].id if page.data else "không có model"
            return True, f"Kết nối được Anthropic (ví dụ model: {first})"
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            err = _map_error(exc)
            return False, f"{err.code}: {err.message}"
        finally:
            await client.close()
