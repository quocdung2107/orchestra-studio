"""Resource scheduler for one PC: GPU lease, CPU slots, RAM/VRAM gate (ADR-0029)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from orchestra_backend.jobs import sysinfo
from orchestra_backend.jobs.engines import EngineManager

RAM_RESERVE_MB = 512  # keep for the OS, the backend and the UI


@dataclass(frozen=True)
class ResourceReq:
    device: Literal["cpu", "gpu", "none"] = "cpu"
    engine: str | None = None
    est_ram_mb: int = 0
    min_vram_mb: int = 0
    exclusive_gpu: bool = False
    cpu_slots: int = 1


@dataclass
class Lease:
    req: ResourceReq
    gpu: bool
    cpu: int


Decision = Literal["ok", "busy", "insufficient"]


class ResourceScheduler:
    def __init__(
        self,
        *,
        max_parallel: int,
        cpu_slots: int,
        engines: EngineManager | None = None,
        ram_probe: Callable[[], int | None] = sysinfo.available_ram_mb,
        vram_probe: Callable[[], int | None] | None = None,
    ):
        self.max_parallel = max_parallel
        self.cpu_total = cpu_slots
        self.engines = engines
        self.ram_probe = ram_probe
        self.vram_probe = vram_probe or (lambda: g.free_mb if (g := sysinfo.gpu_info()) else None)
        self._lock = threading.Lock()
        self.running = 0
        self.gpu_held = False
        self.cpu_used = 0
        self.last_reason = ""

    def _memory_ok(self, req: ResourceReq) -> bool:
        warm = bool(req.engine and self.engines and self.engines.is_warm(req.engine))
        if req.est_ram_mb and not warm:
            free = self.ram_probe()
            if free is not None and free - RAM_RESERVE_MB < req.est_ram_mb:
                self.last_reason = (
                    f"RAM trống {free} MB < cần {req.est_ram_mb} + {RAM_RESERVE_MB} MB"
                )
                return False
        if req.min_vram_mb and not warm:
            free_v = self.vram_probe()
            if free_v is not None and free_v < req.min_vram_mb:
                self.last_reason = f"VRAM trống {free_v} MB < cần {req.min_vram_mb} MB"
                return False
        return True

    def try_acquire(self, req: ResourceReq) -> tuple[Decision, Lease | None]:
        with self._lock:
            if self.running >= self.max_parallel:
                return "busy", None
            needs_gpu = req.device == "gpu" or req.exclusive_gpu
            if needs_gpu and self.gpu_held:
                return "busy", None
            cpu = req.cpu_slots if req.device == "cpu" else 0
            if cpu and self.cpu_used + cpu > self.cpu_total:
                return "busy", None
            if not self._memory_ok(req):
                # Free memory held by idle engines (LRU) and measure again.
                freed = False
                while self.engines and self.engines.stop_idle(exclude=req.engine):
                    freed = True
                    if self._memory_ok(req):
                        break
                if not freed or not self._memory_ok(req):
                    return "insufficient", None
            self.running += 1
            self.gpu_held = self.gpu_held or needs_gpu
            self.cpu_used += cpu
            return "ok", Lease(req=req, gpu=needs_gpu, cpu=cpu)

    def release(self, lease: Lease) -> None:
        with self._lock:
            self.running -= 1
            if lease.gpu:
                self.gpu_held = False
            self.cpu_used -= lease.cpu

    def snapshot(self) -> dict[str, object]:
        return {
            "running": self.running,
            "max_parallel": self.max_parallel,
            "gpu_held": self.gpu_held,
            "cpu_used": self.cpu_used,
            "cpu_slots": self.cpu_total,
            "free_ram_mb": self.ram_probe(),
            "free_vram_mb": self.vram_probe(),
            "last_wait_reason": self.last_reason,
        }
