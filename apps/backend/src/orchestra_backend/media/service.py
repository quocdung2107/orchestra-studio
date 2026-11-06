from __future__ import annotations

import uuid
import wave
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import DomainValidationError, NotFoundError
from orchestra_backend.events.service import append_event
from orchestra_backend.media.models import ASSET_KINDS, Asset
from orchestra_backend.media.store import MediaStore, Stored, image_size, sniff_mime

MB = 1024 * 1024
# Upload limits per kind (bytes). Renders are produced locally, not uploaded.
UPLOAD_LIMITS = {
    "image": 30 * MB,
    "music": 60 * MB,
    "reference_audio": 20 * MB,
    "voice": 60 * MB,
    "other": 30 * MB,
}
ALLOWED_MIME = {
    "image": {"image/png", "image/jpeg", "image/webp"},
    "music": {"audio/wav", "audio/mpeg", "audio/mp4", "audio/flac", "audio/ogg"},
    "reference_audio": {"audio/wav", "audio/mpeg", "audio/flac", "audio/ogg", "audio/mp4"},
    "voice": {"audio/wav"},
    "render": {"video/mp4"},
    "subtitle": {"text/x-ass"},
    "other": {"image/png", "image/jpeg", "audio/wav", "video/mp4"},
}
USER_UPLOAD_LICENSE = {
    "source": "user_upload",
    "commercial": True,
    "note": "Người dùng chịu trách nhiệm về quyền sử dụng",
}


def wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, OSError):
        return None


def _probe(path: Path, mime: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if mime.startswith("image/"):
        size = image_size(path)
        if size:
            out["width"], out["height"] = size
    elif mime == "audio/wav":
        out["duration_s"] = wav_duration(path)
    if mime.startswith(("video/", "audio/")) and out.get("duration_s") is None:
        from orchestra_backend.render.probe import probe_media

        info = probe_media(path)
        if info:
            out["duration_s"] = info.get("duration_s")
            out["width"] = info.get("width")
            out["height"] = info.get("height")
    return out


def register(
    session: Session,
    store: MediaStore,
    stored: Stored,
    *,
    company_id: uuid.UUID,
    kind: str,
    source: str,
    label: str = "",
    provider: str | None = None,
    model: str | None = None,
    params: dict[str, Any] | None = None,
    license_info: dict[str, Any] | None = None,
    parent_asset_id: uuid.UUID | None = None,
    retention: str = "keep",
    expected_mime: str | None = None,
) -> Asset:
    if kind not in ASSET_KINDS:
        raise DomainValidationError(f"Unknown asset kind: {kind}", code="invalid_asset_kind")
    with stored.path.open("rb") as f:
        head = f.read(64)
    mime = sniff_mime(head) or expected_mime
    if mime is None or mime not in ALLOWED_MIME.get(kind, set()):
        raise DomainValidationError(
            f"Định dạng file không hợp lệ cho loại '{kind}'", code="unsupported_media_type"
        )
    meta = _probe(stored.path, mime)
    asset = Asset(
        company_id=company_id,
        kind=kind,
        label=label[:300],
        sha256=stored.sha256,
        mime=mime,
        bytes=stored.bytes,
        source=source,
        provider=provider,
        model=model,
        params_json=params or {},
        license_json=license_info or {},
        parent_asset_id=parent_asset_id,
        retention=retention,
        **meta,
    )
    session.add(asset)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="asset.created",
        payload={"asset_id": str(asset.id), "kind": kind, "source": source, "bytes": stored.bytes},
        source="media",
    )
    return asset


def upload(
    session: Session,
    store: MediaStore,
    *,
    company_id: uuid.UUID,
    kind: str,
    chunks: Iterable[bytes],
    label: str,
) -> Asset:
    get_company(session, company_id)
    if kind not in UPLOAD_LIMITS:
        raise DomainValidationError(f"Không tải lên được loại '{kind}'", code="invalid_asset_kind")
    stored = store.put_chunks(chunks, max_bytes=UPLOAD_LIMITS[kind])
    if stored.bytes == 0:
        raise DomainValidationError("File rỗng", code="empty_file")
    return register(
        session,
        store,
        stored,
        company_id=company_id,
        kind=kind,
        source="upload",
        label=label,
        license_info=USER_UPLOAD_LICENSE,
    )


def get_asset(session: Session, asset_id: uuid.UUID) -> Asset:
    a = session.get(Asset, asset_id)
    if a is None:
        raise NotFoundError("Asset not found", code="asset_not_found")
    return a


def list_assets(
    session: Session, company_id: uuid.UUID, kind: str | None = None, limit: int = 100
) -> list[Asset]:
    q = select(Asset).where(Asset.company_id == company_id)
    if kind:
        q = q.where(Asset.kind == kind)
    return list(session.scalars(q.order_by(Asset.created_at.desc()).limit(limit)))
