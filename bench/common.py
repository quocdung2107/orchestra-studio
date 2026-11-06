"""Shared helpers for benchmarks (run with the backend env: no torch here)."""

from __future__ import annotations

import csv
import platform
import socket
import threading
import time
from datetime import date
from pathlib import Path

from orchestra_backend.jobs import sysinfo

RESULTS = Path(__file__).resolve().parent / "results"


class ResourceSampler:
    """Samples free RAM and GPU memory every 0.5 s while a block runs."""

    def __init__(self, every_s: float = 0.5):
        self.every_s = every_s
        self.min_free_ram_mb: int | None = None
        self.max_vram_used_mb: int | None = None
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            free = sysinfo.available_ram_mb()
            if free is not None:
                self.min_free_ram_mb = free if self.min_free_ram_mb is None else min(self.min_free_ram_mb, free)
            g = sysinfo.gpu_info(max_age_s=0)
            if g is not None:
                used = g.used_mb
                self.max_vram_used_mb = used if self.max_vram_used_mb is None else max(self.max_vram_used_mb, used)
            self._stop.wait(self.every_s)

    def __enter__(self) -> ResourceSampler:
        self.started = time.perf_counter()
        self._t.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.seconds = time.perf_counter() - self.started
        self._stop.set()
        self._t.join(timeout=2)


def machine_tag() -> str:
    return f"{socket.gethostname()}-{platform.system().lower()}"


def write_rows(kind: str, rows: list[dict[str, object]]) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{date.today().isoformat()}_{machine_tag()}_{kind}.csv"
    new = not path.exists()
    keys = list(rows[0].keys())
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        if new:
            w.writeheader()
        w.writerows(rows)
    return path
