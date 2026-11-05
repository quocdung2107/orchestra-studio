"""P5 R8: backup and restore (ADR-0027)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestra_backend.__main__ import main
from orchestra_backend.app import create_app
from orchestra_backend.backup import service as backup
from orchestra_backend.core.config import Settings
from tests.conftest import BASE_URL, TOKEN
from tests.fake_providers import SECRET

API = "/api/v1"


def _companies(c: TestClient) -> list[str]:
    return sorted(x["name"] for x in c.get(f"{API}/companies").json())


def _make_backup(client: TestClient, settings: Settings) -> Path:
    r = client.post(f"{API}/backups")
    assert r.status_code == 201, r.text
    return backup.backups_dir(settings) / r.json()["name"]


def test_backup_contains_db_artifacts_and_no_secrets(
    client: TestClient, settings: Settings
) -> None:
    client.post(f"{API}/demo/seed")
    client.post(
        f"{API}/credentials",
        json={"provider": "anthropic", "label": "k", "secret": SECRET["anthropic"]},
    )
    art = settings.artifacts_dir / "x" / "note.md"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text("nội dung", encoding="utf-8")

    path = _make_backup(client, settings)
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        manifest = json.loads(z.read("manifest.json"))
        blob = b"".join(z.read(n) for n in names)
    assert {"manifest.json", "orchestra.db", "artifacts/x/note.md"} <= names
    assert "backend-token" not in " ".join(names)
    assert manifest["format"] == 1 and manifest["schema_revision"]
    assert SECRET["anthropic"].encode() not in blob and TOKEN.encode() not in blob
    backup.verify(path)

    listed = client.get(f"{API}/backups").json()
    assert listed["items"][0]["name"] == path.name and listed["items"][0]["files"] == 2


def test_restore_round_trip_keeps_previous_data(settings: Settings) -> None:
    def client_for() -> TestClient:
        return TestClient(
            create_app(settings), base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}
        )

    with client_for() as c:
        c.post(f"{API}/demo/seed")
        before = _companies(c)
        path = _make_backup(c, settings)
        c.post(f"{API}/demo/seed")
        assert len(_companies(c)) == len(before) + 1
    kept = backup.restore(settings, path, check_running=False)
    assert (kept / "orchestra.db").is_file()
    with client_for() as c:
        assert _companies(c) == before


def _rewrite(src: Path, dst: Path, change: dict[str, bytes]) -> None:
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
        for n in zi.namelist():
            zo.writestr(n, change.get(n, zi.read(n)))
        for n, data in change.items():
            if n not in zi.namelist():
                zo.writestr(n, data)


def test_tampered_or_unsafe_backup_is_refused(client: TestClient, settings: Settings) -> None:
    path = _make_backup(client, settings)
    bad = path.with_name("orchestra-backup-bad.zip")
    _rewrite(path, bad, {"orchestra.db": b"not a db"})
    with pytest.raises(backup.BackupInvalid, match="Checksum"):
        backup.verify(bad)

    with zipfile.ZipFile(path) as z:
        m = json.loads(z.read("manifest.json"))
    m["files"]["../evil.txt"] = {"sha256": "0", "size": 1}
    _rewrite(path, bad, {"manifest.json": json.dumps(m).encode(), "../evil.txt": b"x"})
    with pytest.raises(backup.BackupInvalid, match="không hợp lệ"):
        backup.verify(bad)

    bad.write_bytes(b"garbage")
    with pytest.raises(backup.BackupInvalid):
        backup.restore(settings, bad, check_running=False)
    assert client.post(f"{API}/backups").status_code == 201  # live data untouched


def test_cli_backup_and_restore(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ORCHESTRA_DATA_DIR", str(settings.data_dir))
    with TestClient(create_app(settings), base_url=BASE_URL, headers={"X-Orchestra-Token": TOKEN}):
        pass  # creates the database
    assert main(["backup"]) == 0
    name = backup.list_backups(settings)[0].name

    monkeypatch.setattr(backup, "backend_running", lambda s: True)
    assert main(["restore", name, "--yes"]) == 1
    assert "Tắt app" in capsys.readouterr().err

    monkeypatch.setattr(backup, "backend_running", lambda s: False)
    monkeypatch.setattr("builtins.input", lambda _: "no")
    assert main(["restore", name]) == 1
    assert main(["restore", name, "--yes"]) == 0
    assert "Đã khôi phục" in capsys.readouterr().out
    assert main(["restore", "missing.zip", "--yes"]) == 2
