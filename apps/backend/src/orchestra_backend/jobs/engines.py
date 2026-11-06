"""Engine processes (TTS, ASR, ...) run outside the backend venv (ADR-0029, ADR-0030).

An engine is either *managed* (we have a start command and own the process) or *external*
(Dung starts it, e.g. the VieNeu Windows app); external engines are only health-checked.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx2
from pydantic import BaseModel, Field, field_validator

from orchestra_backend.core.errors import AppError

log = logging.getLogger(__name__)


class EngineUnavailable(AppError):
    status_code = 503
    code = "engine_unavailable"


class EngineSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    label: str = ""
    base_url: str
    health_path: str = "/health"
    # Start command as an argument list (no shell). None = external engine.
    command: list[str] | None = None
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    install_hint: str = ""

    @field_validator("base_url")
    @classmethod
    def _loopback_only(cls, v: str) -> str:
        v = v.rstrip("/")
        host = v.split("://", 1)[-1].split("/", 1)[0].rsplit(":", 1)[0]
        if host not in ("127.0.0.1", "localhost", "[::1]"):
            raise ValueError("engine must listen on 127.0.0.1 (ADR-0030)")
        return v


DEFAULT_ENGINES: list[EngineSpec] = [
    EngineSpec(
        id="vieneu",
        label="VieNeu-TTS v3 Turbo (OpenAI-compatible server)",
        base_url="http://127.0.0.1:8000",
        install_hint="Xem docs/MEDIA_ENGINES.md §VieNeu: `uv run python -m apps.openai_speech` "
        "trong thư mục VieNeu-TTS (VIENEU_BACKEND=onnx).",
    ),
    EngineSpec(
        id="zerotts",
        label="ZeroTTS (sidecar Orchestra)",
        base_url="http://127.0.0.1:8011",
        install_hint="Xem docs/MEDIA_ENGINES.md §ZeroTTS.",
    ),
    EngineSpec(
        id="faster_whisper",
        label="faster-whisper (sidecar Orchestra, QA phụ đề)",
        base_url="http://127.0.0.1:8012",
        install_hint="Xem docs/MEDIA_ENGINES.md §faster-whisper.",
    ),
]


class EnginesConfig(BaseModel):
    engines: list[EngineSpec]


def load_config(path: Path) -> list[EngineSpec]:
    specs = {e.id: e for e in DEFAULT_ENGINES}
    if path.is_file():
        try:
            cfg = EnginesConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
            specs.update({e.id: e for e in cfg.engines})
        except (ValueError, OSError) as exc:
            log.warning("Ignoring invalid %s: %s", path, exc)
    return list(specs.values())


def save_config(path: Path, specs: list[EngineSpec]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(EnginesConfig(engines=specs).model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)


HealthCheck = Callable[[EngineSpec], bool]


def http_health(spec: EngineSpec) -> bool:
    try:
        r = httpx2.get(spec.base_url + spec.health_path, timeout=3.0)
        return r.status_code < 500
    except httpx2.HTTPError:
        return False


@dataclass
class _State:
    proc: subprocess.Popen[bytes] | None = None
    in_use: int = 0
    last_used: float = 0.0
    last_ok: float = 0.0
    log_path: Path | None = None
    extra: dict[str, str] = field(default_factory=dict)


class EngineManager:
    def __init__(
        self,
        specs: list[EngineSpec],
        *,
        log_dir: Path,
        keep_warm_s: float = 0.0,
        start_timeout_s: float = 180.0,
        health: HealthCheck = http_health,
    ):
        self._specs = {s.id: s for s in specs}
        self._state: dict[str, _State] = {}
        self._lock = threading.RLock()
        self.log_dir = log_dir
        self.keep_warm_s = keep_warm_s
        self.start_timeout_s = start_timeout_s
        self._health = health

    # -- config ---------------------------------------------------------------
    def specs(self) -> list[EngineSpec]:
        return list(self._specs.values())

    def spec(self, engine_id: str) -> EngineSpec:
        s = self._specs.get(engine_id)
        if s is None:
            raise EngineUnavailable(f"Engine chưa được cấu hình: {engine_id}")
        return s

    def replace_specs(self, specs: list[EngineSpec]) -> None:
        with self._lock:
            for s in specs:
                old = self._specs.get(s.id)
                if old is not None and old != s:
                    self.stop(s.id)
            self._specs = {s.id: s for s in specs}

    # -- lifecycle --------------------------------------------------------------
    def _st(self, engine_id: str) -> _State:
        return self._state.setdefault(engine_id, _State())

    def is_managed_alive(self, engine_id: str) -> bool:
        st = self._state.get(engine_id)
        return bool(st and st.proc and st.proc.poll() is None)

    def is_warm(self, engine_id: str) -> bool:
        st = self._state.get(engine_id)
        if st is None:
            return False
        return self.is_managed_alive(engine_id) or (time.monotonic() - st.last_ok < 30)

    def status(self, engine_id: str) -> dict[str, object]:
        spec = self.spec(engine_id)
        ok = self._health(spec)
        st = self._st(engine_id)
        if ok:
            st.last_ok = time.monotonic()
        return {
            "id": spec.id,
            "label": spec.label,
            "base_url": spec.base_url,
            "managed": spec.command is not None,
            "running": ok,
            "started_by_orchestra": self.is_managed_alive(engine_id),
            "in_use": st.in_use,
            "install_hint": spec.install_hint,
        }

    def ensure_running(self, engine_id: str) -> str:
        """Return the engine base URL once healthy; start it if we can."""
        spec = self.spec(engine_id)
        with self._lock:
            st = self._st(engine_id)
            if self._health(spec):
                st.last_ok = time.monotonic()
                return spec.base_url
            if spec.command is None:
                raise EngineUnavailable(
                    f"{spec.label or spec.id} chưa chạy ở {spec.base_url}. {spec.install_hint}"
                )
            if not self.is_managed_alive(engine_id):
                self._start(spec, st)
        deadline = time.monotonic() + self.start_timeout_s
        while time.monotonic() < deadline:
            if self._health(spec):
                st.last_ok = time.monotonic()
                return spec.base_url
            if st.proc is not None and st.proc.poll() is not None:
                raise EngineUnavailable(
                    f"{spec.id} thoát với mã {st.proc.returncode}; xem log {st.log_path}"
                )
            time.sleep(0.5)
        self.stop(engine_id)
        raise EngineUnavailable(f"{spec.id} không sẵn sàng sau {self.start_timeout_s:.0f}s")

    def _start(self, spec: EngineSpec, st: _State) -> None:
        assert spec.command is not None
        self.log_dir.mkdir(parents=True, exist_ok=True)
        st.log_path = self.log_dir / f"{spec.id}.log"
        logf = st.log_path.open("ab")
        kwargs: dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kwargs["start_new_session"] = True
        log.info("Starting engine %s: %s", spec.id, spec.command)
        st.proc = subprocess.Popen(  # noqa: S603 - argument list from local config, no shell
            spec.command,
            cwd=spec.cwd or None,
            env={**os.environ, **spec.env},
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            **kwargs,  # type: ignore[arg-type]
        )

    def acquire(self, engine_id: str) -> str:
        url = self.ensure_running(engine_id)
        with self._lock:
            st = self._st(engine_id)
            st.in_use += 1
            st.last_used = time.monotonic()
        return url

    def release(self, engine_id: str) -> None:
        with self._lock:
            st = self._st(engine_id)
            st.in_use = max(0, st.in_use - 1)
            st.last_used = time.monotonic()
            if st.in_use == 0 and self.keep_warm_s == 0:
                self.stop(engine_id)

    def stop(self, engine_id: str) -> bool:
        with self._lock:
            st = self._state.get(engine_id)
            if st is None or st.proc is None or st.proc.poll() is not None:
                return False
            _kill_tree(st.proc)
            st.proc = None
            st.last_ok = 0.0
            return True

    def stop_idle(self, exclude: str | None = None) -> bool:
        """Stop the least recently used idle engine we started. True if one was stopped."""
        with self._lock:
            idle = [
                (st.last_used, eid)
                for eid, st in self._state.items()
                if eid != exclude and st.in_use == 0 and self.is_managed_alive(eid)
            ]
            for _, eid in sorted(idle):
                if self.stop(eid):
                    return True
        return False

    def reap_expired(self) -> None:
        if self.keep_warm_s <= 0:
            return
        now = time.monotonic()
        with self._lock:
            for eid, st in list(self._state.items()):
                if (
                    st.in_use == 0
                    and self.is_managed_alive(eid)
                    and now - st.last_used > self.keep_warm_s
                ):
                    self.stop(eid)

    def shutdown(self) -> None:
        with self._lock:
            for eid in list(self._state):
                self.stop(eid)


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    try:
        if sys.platform == "win32":
            cmd = ["taskkill", "/PID", str(proc.pid), "/T", "/F"]
            subprocess.run(  # noqa: S603, S607 - fixed args, Windows system tool
                cmd,
                capture_output=True,
                check=False,
                timeout=15,
            )
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired, ProcessLookupError):
        try:
            proc.kill()
        except OSError:
            pass
