from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from orchestra_backend.core.config import LOOPBACK_HOST, Settings


def serve(settings: Settings) -> None:
    import uvicorn

    from orchestra_backend.app import create_app

    app = create_app(settings)
    logging.getLogger("orchestra").info(
        "Backend on http://%s:%s (token file: %s)",
        LOOPBACK_HOST,
        settings.port,
        settings.token_file,
    )
    uvicorn.run(app, host=LOOPBACK_HOST, port=settings.port, log_level="info")


def _resolve(settings: Settings, name: str) -> Path:
    p = Path(name)
    if p.is_file():
        return p
    return settings.data_dir / "backups" / name


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="orchestra-backend")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="chạy backend (mặc định)")
    sub.add_parser("backup", help="tạo bản sao lưu vào data/backups")
    r = sub.add_parser("restore", help="khôi phục từ bản sao lưu (tắt app trước)")
    r.add_argument("file", help="tên file trong data/backups hoặc đường dẫn")
    r.add_argument("--yes", action="store_true", help="không hỏi lại")
    args = parser.parse_args(argv)
    settings = Settings()

    if args.cmd in (None, "serve"):
        serve(settings)
        return 0

    from orchestra_backend.backup import service as backup
    from orchestra_backend.core.errors import AppError

    try:
        if args.cmd == "backup":
            info = backup.create_backup(settings)
            print(f"Đã sao lưu: {backup.backups_dir(settings) / info.name}")
            return 0
        path = _resolve(settings, args.file)
        if not path.is_file():
            print(f"Không thấy file: {path}", file=sys.stderr)
            return 2
        manifest = backup.verify(path)
        n, when = len(manifest["files"]), manifest["created_at"]
        print(f"Bản sao lưu hợp lệ: {path.name} ({n} file, {when})")
        if not args.yes:
            ans = input("Thay toàn bộ dữ liệu hiện tại bằng bản này? Gõ 'yes' để tiếp tục: ")
            if ans.strip().lower() != "yes":
                print("Đã hủy.")
                return 1
        kept = backup.restore(settings, path)
        print(f"Đã khôi phục. Dữ liệu cũ giữ ở: {kept}")
        return 0
    except AppError as exc:
        print(f"Lỗi: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
