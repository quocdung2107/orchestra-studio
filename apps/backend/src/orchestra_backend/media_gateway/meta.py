"""Provider metadata and contracts (ADR-0030)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from orchestra_backend.jobs.scheduler import ResourceReq

Kind = Literal["tts", "image", "asr", "render"]


class HardwareReq(BaseModel):
    device: Literal["cpu", "gpu", "none"] = "cpu"
    engine: str | None = None  # engine process id (jobs.engines); None = in-process/cloud
    min_vram_mb: int = 0
    est_ram_mb: int = 0
    exclusive_gpu: bool = False

    def as_req(self) -> ResourceReq:
        return ResourceReq(
            device=self.device,
            engine=self.engine,
            est_ram_mb=self.est_ram_mb,
            min_vram_mb=self.min_vram_mb,
            exclusive_gpu=self.exclusive_gpu,
        )


class LicenseMeta(BaseModel):
    code: str
    weights: str
    commercial: bool | None  # None = not verified -> blocked
    output_rights: str = ""
    source_url: str = ""
    checked_at: str = ""


class CostMeta(BaseModel):
    local: bool = True
    unit: str | None = None
    price: float | None = None
    currency: str | None = None
    checked_at: str | None = None


class ProviderMeta(BaseModel):
    provider_id: str
    version: str
    kind: Kind
    label: str = ""
    capabilities: dict[str, Any] = Field(default_factory=dict)
    hardware: HardwareReq = Field(default_factory=HardwareReq)
    license: LicenseMeta
    cost: CostMeta = Field(default_factory=CostMeta)
    fake: bool = False


# ---- requests / results ------------------------------------------------------------


@dataclass
class TtsRequest:
    text: str  # already normalized
    voice: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TtsResult:
    wav_path: Path  # any WAV; the service converts it to 48 kHz mono s16
    engine_version: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImageRequest:
    prompt: str
    width: int
    height: int
    seed: int | None = None
    negative_prompt: str = ""


@dataclass
class ImageResult:
    path: Path
    model: str
    cost_usd: float | None = None
    revised_prompt: str | None = None


@dataclass
class Transcript:
    text: str
    words: list[dict[str, Any]] = field(default_factory=list)  # {word, start, end}
    language: str | None = None


class TtsProvider(Protocol):
    meta: ProviderMeta

    def voices(self, base_url: str | None) -> list[dict[str, Any]]: ...

    def synthesize(self, req: TtsRequest, base_url: str | None, out: Path) -> TtsResult: ...


class ImageProvider(Protocol):
    meta: ProviderMeta

    def generate(self, req: ImageRequest, out: Path) -> ImageResult: ...


class AsrProvider(Protocol):
    meta: ProviderMeta

    def transcribe(self, wav: Path, base_url: str | None, language: str = "vi") -> Transcript: ...
