from __future__ import annotations

import hashlib

import pytest

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.media.store import MediaStore, image_size, sniff_mime
from tests.media_helpers import png_bytes


def test_upload_png_dedupes_and_streams_with_range(client, company, tmp_path):
    data = png_bytes(tmp_path, 120, 80)
    url = f"/api/v1/companies/{company['id']}/assets?kind=image&label=test"
    r1 = client.put(url, content=data)
    assert r1.status_code == 201, r1.text
    a = r1.json()
    assert a["mime"] == "image/png" and (a["width"], a["height"]) == (120, 80)
    assert a["sha256"] == hashlib.sha256(data).hexdigest()
    assert a["license_json"]["source"] == "user_upload"
    r2 = client.put(url, content=data)
    assert r2.json()["sha256"] == a["sha256"]  # same bytes, one file on disk
    full = client.get(f"/api/v1/assets/{a['id']}/content")
    assert full.status_code == 200 and full.content == data
    part = client.get(f"/api/v1/assets/{a['id']}/content", headers={"Range": "bytes=0-9"})
    assert part.status_code == 206 and part.content == data[:10]


def test_upload_rejects_wrong_magic_bytes_and_empty(client, company):
    url = f"/api/v1/companies/{company['id']}/assets?kind=image"
    r = client.put(url, content=b"#!/bin/sh\necho not an image\n")
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_media_type"
    r = client.put(url, content=b"")
    assert r.status_code == 422


def test_upload_size_limit(client, company, monkeypatch):
    from orchestra_backend.media import service

    monkeypatch.setitem(service.UPLOAD_LIMITS, "image", 1000)
    r = client.put(
        f"/api/v1/companies/{company['id']}/assets?kind=image", content=b"\x89PNG" + b"0" * 2000
    )
    assert r.status_code == 413


def test_upload_kind_must_be_uploadable(client, company, tmp_path):
    r = client.put(
        f"/api/v1/companies/{company['id']}/assets?kind=render", content=png_bytes(tmp_path)
    )
    assert r.status_code == 422


def test_store_never_builds_paths_from_untrusted_digest(tmp_path):
    store = MediaStore(tmp_path)
    with pytest.raises(DomainValidationError):
        store.path_for("../../etc/passwd")
    with pytest.raises(DomainValidationError):
        store.path_for("A" * 64)


def test_store_write_is_atomic_and_cleans_part_files(tmp_path):
    store = MediaStore(tmp_path)

    def chunks():
        yield b"abc"
        raise RuntimeError("client went away")

    with pytest.raises(RuntimeError):
        store.put_chunks(chunks())
    assert list((tmp_path / "tmp").iterdir()) == []


def test_sniff_and_jpeg_size(tmp_path):
    assert sniff_mime(b"RIFF\x00\x00\x00\x00WAVEfmt ") == "audio/wav"
    assert sniff_mime(b"\x00\x00\x00\x18ftypisom") == "video/mp4"
    assert sniff_mime(b"<html>") is None
    # Minimal JPEG header with SOF0 for 300x200
    jpg = (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x10"
        + b"JFIF\x00"
        + b"\x00" * 9
        + b"\xff\xc0\x00\x11\x08\x00\xc8\x01\x2c\x03"
        + b"\x00" * 9
    )
    p = tmp_path / "a.jpg"
    p.write_bytes(jpg)
    assert image_size(p) == (300, 200)
