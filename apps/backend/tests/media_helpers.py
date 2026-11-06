from __future__ import annotations

import asyncio

from orchestra_backend.media_gateway.providers.fakes import write_png


def png_bytes(tmp_path, w=64, h=48) -> bytes:
    p = tmp_path / f"img_{w}x{h}.png"
    write_png(p, w, h, (200, 30, 30), (20, 20, 200))
    return p.read_bytes()


def drain(container, timeout: float = 120) -> None:
    asyncio.run(container.extras["job_runner"].drain(timeout))
