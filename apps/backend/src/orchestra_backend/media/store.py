"""Content-addressed media store: data/media/<ab>/<cd>/<sha256> (ADR-0028)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from orchestra_backend.core.errors import DomainValidationError

_SHA = re.compile(r"[0-9a-f]{64}")
CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Stored:
    sha256: str
    bytes: int
    path: Path


class TooLarge(DomainValidationError):
    status_code = 413
    code = "asset_too_large"


class MediaStore:
    def __init__(self, root: Path):
        self.root = root

    def path_for(self, sha256: str) -> Path:
        if not _SHA.fullmatch(sha256):  # never build a path from untrusted text
            raise DomainValidationError("Invalid digest", code="invalid_digest")
        return self.root / sha256[:2] / sha256[2:4] / sha256

    def exists(self, sha256: str) -> bool:
        return self.path_for(sha256).is_file()

    def put_chunks(self, chunks: Iterable[bytes], *, max_bytes: int | None = None) -> Stored:
        tmp_dir = self.root / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"{uuid.uuid4().hex}.part"
        h = hashlib.sha256()
        size = 0
        try:
            with tmp.open("wb") as f:
                for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise TooLarge(f"File lớn hơn giới hạn {max_bytes // (1024 * 1024)} MB")
                    h.update(chunk)
                    f.write(chunk)
            digest = h.hexdigest()
            final = self.path_for(digest)
            if final.is_file():
                tmp.unlink()
            else:
                final.parent.mkdir(parents=True, exist_ok=True)
                os.replace(tmp, final)
            return Stored(digest, size, final)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def put_bytes(self, data: bytes) -> Stored:
        return self.put_chunks([data])

    def put_file(self, src: Path) -> Stored:
        def read() -> Iterable[bytes]:
            with src.open("rb") as f:
                while chunk := f.read(CHUNK):
                    yield chunk

        return self.put_chunks(read())

    def copy_out(self, sha256: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.path_for(sha256), dest)
        return dest


def sniff_mime(head: bytes) -> str | None:
    """Detect a supported format from magic bytes; never trust names or client types."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"M4A ", b"M4B "):
            return "audio/mp4"
        return "video/mp4"
    if head.startswith(b"fLaC"):
        return "audio/flac"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"[Script Info]") or head.startswith(b"\xef\xbb\xbf[Script Info]"):
        return "text/x-ass"
    return None


def image_size(path: Path) -> tuple[int, int] | None:
    """Width/height for PNG and JPEG without Pillow."""
    with path.open("rb") as f:
        head = f.read(32)
        if head.startswith(b"\x89PNG\r\n\x1a\n") and head[12:16] == b"IHDR":
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        if head.startswith(b"\xff\xd8"):
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                code = marker[1]
                seg_len = int.from_bytes(f.read(2), "big")
                if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD):
                    data = f.read(5)
                    return int.from_bytes(data[3:5], "big"), int.from_bytes(data[1:3], "big")
                f.seek(seg_len - 2, 1)
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            chunk = head[12:16]
            if chunk == b"VP8X":
                return (
                    1 + int.from_bytes(head[24:27], "little"),
                    1 + int.from_bytes(head[27:30], "little"),
                )
    return None
