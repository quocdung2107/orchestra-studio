"""`orchestra-worker` CLI: pair | run (default) | status | forget."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys

from orchestra_backend.core.config import Settings
from orchestra_backend.credentials.store import make_store
from orchestra_backend.worker_client import client as wc


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="orchestra-worker")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("pair", help="ghép nối bằng mã tạo ở mục Workers")
    p.add_argument("code")
    p.add_argument("--server", help="địa chỉ control plane (mặc định http://127.0.0.1:<cổng>)")
    sub.add_parser("run", help="nhận và chạy việc (mặc định)")
    sub.add_parser("status", help="xem worker đã ghép nối chưa")
    sub.add_parser("forget", help="xóa danh tính worker trên máy này")
    args = parser.parse_args(argv)
    settings = Settings()

    try:
        if args.cmd == "pair":
            ident = asyncio.run(wc.pair(settings, args.code, args.server))
            print(f"Đã ghép nối: {ident.name} ({ident.worker_id}). Chạy: pnpm worker")
            return 0
        if args.cmd == "status":
            ident = wc.load_identity(settings)
            print(f"Worker {ident.name} ({ident.worker_id}) → {ident.server_url}")
            return 0
        if args.cmd == "forget":
            with contextlib.suppress(wc.NotPaired):
                ident = wc.load_identity(settings)
                make_store(settings.secret_store).delete(wc.secret_ref(ident.worker_id))
            wc.identity_file(settings).unlink(missing_ok=True)
            print("Đã xóa danh tính worker trên máy này (nhớ thu hồi nó trong app).")
            return 0
        return asyncio.run(_run(settings))
    except wc.NotPaired as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except wc.WorkerError as exc:
        print(f"Lỗi: {exc.message} ({exc.code})", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


async def _run(settings: Settings) -> int:
    cp = wc.connect(settings)
    worker = wc.Worker(cp, wc.local_runtimes(settings))
    logging.getLogger("orchestra.worker").info(
        "Worker đang chờ việc từ %s (Ctrl+C để dừng)", wc.load_identity(settings).server_url
    )
    try:
        await worker.run_forever()
    finally:
        await cp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
