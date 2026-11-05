"""Local models through Ollama's HTTP API (ADR-0022, ADR-0024)."""

from __future__ import annotations

import asyncio
from typing import Any

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


class OllamaSettings(BaseSettingsModel):
    model: str = Field(min_length=1, max_length=200)
    num_ctx: int | None = Field(default=None, ge=512, le=262144)
    max_tokens: int | None = Field(default=None, ge=16, le=65536)
    # Thinking models (e.g. qwen3) reason before answering. Off by default: on small local
    # hardware it multiplies latency. None = let the model decide (field not sent).
    think: bool | None = False


class _Session(ProviderSession):
    def __init__(self, rt: OllamaRuntime, req: RunRequest, s: OllamaSettings):
        self.rt = rt
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
            self.messages.append({"role": "tool", "content": r.content, "tool_name": r.call.name})
        body: dict[str, Any] = {"model": self.s.model, "messages": self.messages, "stream": False}
        if self.s.think is not None:
            body["think"] = self.s.think
        if self.tools:
            body["tools"] = self.tools
        options: dict[str, Any] = {}
        if self.s.num_ctx:
            options["num_ctx"] = self.s.num_ctx
        if self.s.max_tokens:
            options["num_predict"] = self.s.max_tokens
        if options:
            body["options"] = options
        data = await self.rt._post("/api/chat", body)
        msg = data.get("message") or {}
        turn = Turn(
            model=str(data.get("model") or self.s.model),
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
            text=str(msg.get("content") or ""),
        )
        calls = []
        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function") or {}
            args = fn.get("arguments") or {}
            calls.append(
                ToolCall(
                    id=str(tc.get("id") or f"call_{len(self.messages)}_{i}"),
                    name=str(fn.get("name") or ""),
                    args=args if isinstance(args, dict) else {},
                )
            )
        self.messages.append(
            {k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")}
            or {"role": "assistant", "content": ""}
        )
        turn.tool_calls = calls
        if data.get("done_reason") == "length":
            turn.stop = "max_tokens"
        elif calls:
            turn.stop = "tool_use"
        return turn


class OllamaRuntime(LlmRuntime):
    runtime_id = "ollama"
    display_name = "Ollama (model cục bộ)"
    provider = "ollama"
    requires_credential = False
    settings_model = OllamaSettings

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        max_concurrency: int = 1,
        timeout_s: float = 300.0,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.max_concurrency = max_concurrency
        self.timeout_s = timeout_s
        self.transport = transport
        self._sem = asyncio.Semaphore(max_concurrency)
        self._running = 0
        self._waiting = 0

    def _http(self, timeout: float) -> httpx2.AsyncClient:
        kw: dict[str, Any] = {"base_url": self.base_url, "timeout": timeout}
        if self.transport is not None:
            kw["transport"] = self.transport
        return httpx2.AsyncClient(**kw)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._http(self.timeout_s) as http:
                r = await http.post(path, json=body)
        except httpx2.HTTPError as exc:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                f"Không kết nối được Ollama tại {self.base_url} ({type(exc).__name__})",
                True,
            ) from None
        if r.status_code >= 400:
            try:
                msg = str(r.json().get("error", r.text))
            except ValueError:
                msg = r.text
            raise classify_status(r.status_code, msg[:500])
        return r.json()

    async def acquire_slot(self) -> None:
        """Queue for a local-model slot; the run stays `queued` meanwhile (ADR-0024)."""
        self._waiting += 1
        try:
            await self._sem.acquire()
        finally:
            self._waiting -= 1
        self._running += 1

    def release_slot(self) -> None:
        self._running -= 1
        self._sem.release()

    async def open_session(self, req: RunRequest, settings: BaseSettingsModel) -> ProviderSession:
        assert isinstance(settings, OllamaSettings)
        return _Session(self, req, settings)

    async def health_check(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": "unreachable",
            "base_url": self.base_url,
            "limits": {
                "max_concurrency": self.max_concurrency,
                "running": self._running,
                "waiting": self._waiting,
            },
            "models": [],
            "loaded": [],
        }
        try:
            async with self._http(5.0) as http:
                version = (await http.get("/api/version")).json()
                tags = (await http.get("/api/tags")).json()
                ps = (await http.get("/api/ps")).json()
        except (httpx2.HTTPError, ValueError) as exc:
            out["detail"] = f"Không kết nối được Ollama ({type(exc).__name__})"
            return out
        out["status"] = "ok"
        out["version"] = version.get("version")
        for m in tags.get("models") or []:
            d = m.get("details") or {}
            out["models"].append(
                {
                    "name": m.get("name"),
                    "size_bytes": m.get("size"),
                    "parameter_size": d.get("parameter_size"),
                    "quantization": d.get("quantization_level"),
                    "family": d.get("family"),
                }
            )
        for m in ps.get("models") or []:
            out["loaded"].append(
                {
                    "name": m.get("name"),
                    "size_bytes": m.get("size"),
                    "vram_bytes": m.get("size_vram"),
                    "expires_at": m.get("expires_at"),
                    "context_length": m.get("context_length"),
                }
            )
        return out
