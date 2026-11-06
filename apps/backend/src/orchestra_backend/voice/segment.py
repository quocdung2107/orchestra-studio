"""Split normalized narration into TTS segments (ADR-0031)."""

from __future__ import annotations

import re

DEFAULT_MAX_CHARS = 180


def _split_long(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    parts = [p.strip() for p in re.split(r"(?<=[,;:])\s+", sentence) if p.strip()]
    out: list[str] = []
    cur = ""
    for p in parts:
        if len(p) > max_chars:
            words = p.split()
            for w in words:
                if cur and len(cur) + 1 + len(w) > max_chars:
                    out.append(cur)
                    cur = w
                else:
                    cur = f"{cur} {w}".strip()
            continue
        if cur and len(cur) + 1 + len(p) > max_chars:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return out


def split_segments(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    out: list[str] = []
    for s in sentences:
        out.extend(_split_long(s, max_chars))
    return out
