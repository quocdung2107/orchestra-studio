"""Shared conversation loop for model-backed runtimes (ADR-0022).

Provider sessions keep their native message history private; only plain dataclasses
leave this package. Every error text passes through `redact()`.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.core.redact import redact
from orchestra_backend.credentials.store import SecretMissing
from orchestra_backend.runtime.interface import RunRequest, RuntimeCapabilities, RuntimeEvent

T = TypeVar("T")
TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_TOOL_RESULT_CHARS = 16_000
MAX_MESSAGE_CHARS = 3_900

CAPABILITIES = RuntimeCapabilities(
    supports_streaming=False,
    supports_cancel=True,
    supports_pause=False,
    supports_resume=False,
    supports_tool_calls=True,
)


class ProviderError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolCallResult:
    call: ToolCall
    ok: bool
    content: str


@dataclass
class Turn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop: str = "end"  # end | tool_use | max_tokens | refusal
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    refusal_detail: str = ""


class ProviderSession(ABC):
    @abstractmethod
    async def send(self, results: list[ToolCallResult] | None) -> Turn:
        """First call with None; later calls carry the results of the previous turn's tools."""

    async def close(self) -> None:
        return None


class BaseSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_turns: int = Field(default=8, ge=1, le=30)


DELEGATE_TOOL = "team.delegate"


def tool_name(key: str) -> str:
    return key.replace(".", "__")


def system_prompt(req: RunRequest) -> str:
    a = req.agent
    d = a.get("definition") or {}
    parts = [f"Bạn là {a.get('name', 'agent')}, vai trò: {a.get('role', '')}."]
    if d.get("instructions"):
        parts.append(str(d["instructions"]))
    if d.get("goals"):
        parts.append("Mục tiêu:\n" + "\n".join(f"- {g}" for g in d["goals"]))
    parts.append(
        "Hoàn thành task được giao. Chỉ dùng tool khi thật sự cần. "
        "Khi xong, trả lời bằng kết quả cuối cùng dạng Markdown; dòng đầu là tóm tắt một câu. "
        "Dùng ngôn ngữ của task."
    )
    return "\n\n".join(parts)


def user_prompt(req: RunRequest) -> str:
    t = req.task
    text = f"# Task: {t.get('title', '')}\n\n{t.get('description', '') or ''}".strip()
    ctx = {k: v for k, v in (req.context or {}).items() if k != "scenario_id"}
    if ctx:
        dumped = json.dumps(ctx, ensure_ascii=False)[:4000]
        text += f"\n\nNgữ cảnh (JSON): {dumped}"
    return text


def _artifact_name(title: str) -> str:
    base = re.sub(r"[^\w\-. ]", "", title).strip()[:80] or "ket-qua"
    return f"{base}.md"


def _summary(text: str, truncated: bool) -> str:
    first = next((ln.strip().lstrip("#").strip() for ln in text.splitlines() if ln.strip()), "")
    first = first[:300] or "Hoàn thành"
    return ("[bị cắt do max_tokens] " + first) if truncated else first


def _ev(type_: str, **data: Any) -> RuntimeEvent:
    return RuntimeEvent(type=type_, data=data)


class LlmRuntime(ABC):
    runtime_id: ClassVar[str]
    display_name: ClassVar[str]
    provider: ClassVar[str]
    requires_credential: ClassVar[bool] = True
    settings_model: ClassVar[type[BaseSettingsModel]] = BaseSettingsModel
    capabilities = CAPABILITIES

    def __init__(self) -> None:
        self._cancel: dict[uuid.UUID, asyncio.Event] = {}

    # ----- settings -----

    def validate_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.settings_model.model_validate(settings).model_dump(
                mode="json", exclude_none=True
            )
        except ValidationError as exc:
            raise DomainValidationError(
                f"Invalid settings for runtime '{self.runtime_id}'",
                code="invalid_runtime_settings",
                details=[
                    {"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors(include_url=False)
                ],
            ) from exc

    # ----- control -----

    def cancel(self, run_id: uuid.UUID) -> None:
        self._cancel.setdefault(run_id, asyncio.Event()).set()

    async def _cancellable(self, run_id: uuid.UUID, aw: Awaitable[T]) -> tuple[bool, T | None]:
        ev = self._cancel.setdefault(run_id, asyncio.Event())
        if ev.is_set():
            if asyncio.iscoroutine(aw):
                aw.close()
            return True, None
        job = asyncio.ensure_future(aw)
        waiter = asyncio.ensure_future(ev.wait())
        try:
            await asyncio.wait([job, waiter], return_when=asyncio.FIRST_COMPLETED)
        finally:
            waiter.cancel()
        if job.done():
            return False, job.result()
        job.cancel()
        try:
            await job
        except BaseException:  # noqa: BLE001,S110 - cancelled call, outcome irrelevant
            pass
        return True, None

    # ----- provider hooks -----

    @abstractmethod
    async def open_session(
        self, req: RunRequest, settings: BaseSettingsModel
    ) -> ProviderSession: ...

    async def acquire_slot(self) -> None:
        """Wait for capacity before the run starts. Default: unlimited."""
        return None

    def release_slot(self) -> None:
        return None

    async def verify(self, secret: str) -> tuple[bool, str]:  # pragma: no cover - per provider
        return False, "not supported"

    async def health_check(self) -> dict[str, Any]:
        return {"status": "ok", "detail": "Kiểm tra kết nối bằng nút 'Kiểm tra' của credential"}

    # ----- loop -----

    def execute(self, request: RunRequest) -> AsyncIterator[RuntimeEvent]:
        return self._execute(request)

    async def _execute(self, req: RunRequest) -> AsyncIterator[RuntimeEvent]:
        run_id = req.run_id
        self._cancel.setdefault(run_id, asyncio.Event())
        session: ProviderSession | None = None
        slot = False
        try:
            cancelled, _ = await self._cancellable(run_id, self.acquire_slot())
            if cancelled:
                yield _ev("run.started")
                yield _ev("run.cancelled")
                return
            slot = True
            yield _ev("run.started")
            settings = self.settings_model.model_validate(req.settings)
            model = getattr(settings, "model", "") or "?"
            yield _ev("run.progress", message=f"Gọi model {model} ({self.display_name})")
            cancelled, session = await self._cancellable(run_id, self.open_session(req, settings))
            if cancelled:
                yield _ev("run.cancelled")
                return
            assert session is not None
            names = {tool_name(s["key"]): s["key"] for s in req.tool_specs}
            results: list[ToolCallResult] | None = None
            for turn_no in range(1, settings.max_turns + 1):
                t0 = time.monotonic()
                cancelled, turn = await self._cancellable(run_id, session.send(results))
                if cancelled:
                    yield _ev("run.cancelled")
                    return
                assert turn is not None
                yield _ev(
                    "run.usage",
                    provider=self.provider,
                    model=turn.model or model,
                    input_tokens=turn.input_tokens,
                    output_tokens=turn.output_tokens,
                    source=(
                        "local_runtime_reported"
                        if not self.requires_credential
                        else "provider_reported"
                    ),
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
                if turn.stop == "refusal":
                    detail = f" ({turn.refusal_detail})" if turn.refusal_detail else ""
                    yield _ev(
                        "run.failed",
                        error_code="PROVIDER_REFUSED",
                        error_summary=f"Model từ chối yêu cầu{detail}"[:2000],
                        retryable=False,
                    )
                    return
                if turn.tool_calls and turn.stop != "max_tokens":
                    results = []
                    for call in turn.tool_calls:
                        waits = names.get(call.name) == DELEGATE_TOOL
                        if waits:
                            # The child run may need this runtime's slot (Ollama limit 1):
                            # hand it back while we wait, then queue again (ADR-0026).
                            self.release_slot()
                            slot = False
                        results.append(await self._run_tool(req, names, call))
                        if waits:
                            cancelled, _ = await self._cancellable(run_id, self.acquire_slot())
                            if cancelled:
                                yield _ev("run.cancelled")
                                return
                            slot = True
                        if self._cancel[run_id].is_set():
                            yield _ev("run.cancelled")
                            return
                    yield _ev(
                        "run.progress",
                        message="Đã dùng tool: "
                        + ", ".join(
                            names.get(r.call.name, r.call.name) + ("" if r.ok else " (lỗi)")
                            for r in results
                        ),
                        step=turn_no,
                    )
                    continue
                text = turn.text.strip()
                if not text:
                    yield _ev(
                        "run.failed",
                        error_code="EMPTY_RESPONSE",
                        error_summary="Model không trả về nội dung",
                        retryable=False,
                    )
                    return
                truncated = turn.stop == "max_tokens"
                yield _ev("run.message", text=text[:MAX_MESSAGE_CHARS])
                yield _ev(
                    "run.artifact.produced",
                    name=_artifact_name(str(req.task.get("title", ""))),
                    mime_type="text/markdown",
                    content=text[:1_000_000],
                )
                yield _ev("run.completed", summary=_summary(text, truncated))
                return
            yield _ev(
                "run.failed",
                error_code="MAX_TURNS_EXCEEDED",
                error_summary=f"Vượt quá {settings.max_turns} lượt gọi model",
                retryable=False,
            )
        except ProviderError as exc:
            yield _ev(
                "run.failed",
                error_code=exc.code,
                error_summary=redact(exc.message)[:2000] or exc.code,
                retryable=exc.retryable,
            )
        except SecretMissing:
            yield _ev(
                "run.failed",
                error_code="CREDENTIAL_MISSING",
                error_summary="Không đọc được secret của credential (đã xóa khỏi kho?)",
                retryable=False,
            )
        except ValidationError:
            yield _ev(
                "run.failed",
                error_code="INVALID_RUNTIME_SETTINGS",
                error_summary=f"Cấu hình runtime '{self.runtime_id}' của agent không hợp lệ",
                retryable=False,
            )
        finally:
            self._cancel.pop(run_id, None)
            try:
                if session is not None:
                    await session.close()
            finally:
                if slot:
                    self.release_slot()

    async def _run_tool(
        self, req: RunRequest, names: dict[str, str], call: ToolCall
    ) -> ToolCallResult:
        key = names.get(call.name)
        if key is None or req.tools is None:
            return ToolCallResult(call, False, json.dumps({"error": "UNKNOWN_TOOL"}))
        res = await req.tools.call(key, call.args)
        payload = (
            {"ok": True, "data": res.data}
            if res.ok
            else {"ok": False, "error_code": res.error_code, "error": res.error_summary}
        )
        text = json.dumps(payload, ensure_ascii=False, default=str)
        if len(text) > MAX_TOOL_RESULT_CHARS:
            text = text[:MAX_TOOL_RESULT_CHARS] + "…(truncated)"
        return ToolCallResult(call, res.ok, text)


def tools_for(req: RunRequest) -> list[dict[str, Any]]:
    """Provider-neutral tool list: name, description, JSON schema."""
    out = []
    for spec in req.tool_specs:
        name = tool_name(spec["key"])
        if not TOOL_NAME.match(name):
            continue
        schema = spec.get("input_schema") or {}
        if schema.get("type") != "object":
            schema = {"type": "object", "properties": {}, "additionalProperties": True}
        out.append(
            {
                "name": name,
                "description": (spec.get("description") or spec.get("name") or spec["key"])[:1000],
                "schema": schema,
            }
        )
    return out


def classify_status(status: int | None, message: str) -> ProviderError:
    msg = redact(message)[:500]
    if status in (401, 403):
        return ProviderError("PROVIDER_AUTH_FAILED", f"Xác thực thất bại ({status}): {msg}")
    if status == 404:
        return ProviderError("MODEL_NOT_FOUND", f"Không tìm thấy model/endpoint (404): {msg}")
    if status == 429:
        return ProviderError("PROVIDER_RATE_LIMITED", f"Bị giới hạn tần suất (429): {msg}", True)
    if status is not None and status >= 500:
        return ProviderError("PROVIDER_UNAVAILABLE", f"Provider lỗi ({status}): {msg}", True)
    if status in (400, 413, 422):
        return ProviderError("PROVIDER_BAD_REQUEST", f"Yêu cầu không hợp lệ ({status}): {msg}")
    return ProviderError("PROVIDER_ERROR", f"Lỗi provider ({status}): {msg}")
