"""Free RAM / VRAM probes without extra dependencies (ADR-0029)."""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GpuInfo:
    name: str
    total_mb: int
    used_mb: int

    @property
    def free_mb(self) -> int:
        return self.total_mb - self.used_mb


def available_ram_mb() -> int | None:
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
        except OSError:
            return None
        return None
    if sys.platform == "win32":

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [  # noqa: RUF012
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):  # type: ignore[attr-defined]
            return int(st.ullAvailPhys // (1024 * 1024))
    return None


_gpu_cache: tuple[float, GpuInfo | None] = (0.0, None)


def gpu_info(max_age_s: float = 2.0) -> GpuInfo | None:
    global _gpu_cache
    now = time.monotonic()
    if now - _gpu_cache[0] < max_age_s:
        return _gpu_cache[1]
    info: GpuInfo | None = None
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            res = subprocess.run(  # noqa: S603 - fixed args
                [exe, "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                first = res.stdout.decode().strip().splitlines()[0]
                name, total, used = (x.strip() for x in first.split(","))
                info = GpuInfo(name, int(total), int(used))
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            info = None
    _gpu_cache = (now, info)
    return info
