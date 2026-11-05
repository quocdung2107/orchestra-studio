"""OpenAI via the official `openai` SDK, Chat Completions (ADR-0022)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx2
import openai
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


class OpenAISettings(BaseSettingsModel):
    # No default model on purpose: the user picks one they have access to.
    model: str = Field(min_length=1, max_length=100)
    credential_id: uuid.UUID
    max_tokens: int = Field(default=8000, ge=256, le=64000)


def _map_error(exc: Exception) -> ProviderError:
    if isinstance(exc, openai.APIStatusError):
        return classify_status(exc.status_code, exc.message)
    if isinstance(exc, openai.APIConnectionError):
        return ProviderError(
            "PROVIDER_UNAVAILABLE", f"Không kết nối được OpenAI: {type(exc).__name__}", True
        )
    raise exc


class _Session(ProviderSession):
    def __init__(self, client: openai.AsyncOpenAI, req: RunRequest, s: OpenAISettings):
        self.client = client
        self.s = s
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt(req)},
            {"role": "user", "content": user_prompt(req)},
        ]
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["schema"],
                },
            }
            for t in tools_for(req)
        ]

    async def send(self, results: list[ToolCallResult] | None) -> Turn:
        for r in results or []:
            self.messages.append({"role": "tool", "tool_call_id": r.call.id, "content": r.content})
        kwargs: dict[str, Any] = dict(
            model=self.s.model,
            messages=self.messages,
            max_completion_tokens=self.s.max_tokens,
        )
        if self.tools:
            kwargs["tools"] = self.tools
        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except (openai.APIStatusError, openai.APIConnectionError) as exc:
            raise _map_error(exc) from None
        if not resp.choices:
            raise ProviderError("EMPTY_RESPONSE", "OpenAI không trả về lựa chọn nào")
        choice = resp.choices[0]
        msg = choice.message
        usage = resp.usage
        turn = Turn(
            model=resp.model or self.s.model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
        if getattr(msg, "refusal", None):
            turn.stop = "refusal"
            turn.refusal_detail = str(msg.refusal)[:300]
            return turn
        if choice.finish_reason == "content_filter":
            turn.stop = "refusal"
            turn.refusal_detail = "content_filter"
            return turn
        calls = []
        for tc in msg.tool_calls or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            try:
                args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_invalid_json": fn.arguments}
            calls.append(
                ToolCall(id=tc.id, name=fn.name, args=args if isinstance(args, dict) else {})
            )
        self.messages.append(msg.model_dump(mode="json", exclude_none=True))
        turn.text = msg.content or ""
        turn.tool_calls = calls
        if choice.finish_reason == "length":
            turn.stop = "max_tokens"
        elif calls:
            turn.stop = "tool_use"
        return turn

    async def close(self) -> None:
        await self.client.close()


class OpenAIRuntime(LlmRuntime):
    runtime_id = "openai"
    display_name = "OpenAI API"
    provider = "openai"
    settings_model = OpenAISettings

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

    def _client(self, api_key: str) -> openai.AsyncOpenAI:
        http = openai.DefaultAsyncHttpxClient(transport=self.transport) if self.transport else None
        return openai.AsyncOpenAI(
            api_key=api_key, timeout=self.timeout_s, max_retries=self.max_retries, http_client=http
        )

    async def open_session(self, req: RunRequest, settings: BaseSettingsModel) -> ProviderSession:
        assert isinstance(settings, OpenAISettings)
        if req.credential is None:
            raise ProviderError("CREDENTIAL_MISSING", "Agent chưa được gán credential OpenAI")
        return _Session(self._client(req.credential.reveal()), req, settings)

    async def verify(self, secret: str) -> tuple[bool, str]:
        client = self._client(secret)
        try:
            page = await client.models.list()
            n = len(page.data)
            return True, f"Kết nối được OpenAI ({n} model khả dụng)"
        except (openai.APIStatusError, openai.APIConnectionError) as exc:
            err = _map_error(exc)
            return False, f"{err.code}: {err.message}"
        finally:
            await client.close()
