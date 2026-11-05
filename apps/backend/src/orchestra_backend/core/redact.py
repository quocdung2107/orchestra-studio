"""Secret redaction for logs, events and error text (ADR-0021, SECURITY §6)."""

from __future__ import annotations

import logging
import re
import threading

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{16,}"),
]
_lock = threading.Lock()
_known: set[str] = set()
MASK = "[REDACTED]"


def register_secret(value: str) -> None:
    """Remember a secret that was loaded so it is masked wherever it appears."""
    if value and len(value) >= 6:
        with _lock:
            _known.add(value)


def forget_secret(value: str) -> None:
    with _lock:
        _known.discard(value)


def redact(text: str) -> str:
    if not text:
        return text
    with _lock:
        known = sorted(_known, key=len, reverse=True)
    for secret in known:
        if secret in text:
            text = text.replace(secret, MASK)
    for pat in _PATTERNS:
        text = pat.sub(lambda m: (m.group(1) if m.groups() else "") + MASK, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 - never break logging
            return True
        clean = redact(msg)
        if clean != msg:
            record.msg, record.args = clean, None
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            text = redact(str(exc))
            if text != str(exc):
                record.exc_info = None
                record.exc_text = None
                record.msg = f"{record.msg} ({type(exc).__name__}: {text})"
        return True


def install_log_redaction() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        root.addFilter(RedactingFilter())
    for h in root.handlers:
        if not any(isinstance(f, RedactingFilter) for f in h.filters):
            h.addFilter(RedactingFilter())
