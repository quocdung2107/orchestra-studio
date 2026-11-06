"""Provider registry, company media settings and license policy (ADR-0030)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import AppError, DomainValidationError
from orchestra_backend.media_gateway.meta import ProviderMeta
from orchestra_backend.media_gateway.providers.fakes import FakeAsr, FakeImage, FakeTts
from orchestra_backend.media_gateway.providers.faster_whisper import FasterWhisperAsr
from orchestra_backend.media_gateway.providers.openai_images import OpenAiImages
from orchestra_backend.media_gateway.providers.vieneu import VieneuTts
from orchestra_backend.media_gateway.providers.zerotts import ZeroTts


class LicenseBlocked(AppError):
    status_code = 409
    code = "license_blocked"


class CloudImageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(default="", max_length=300)
    model: str = Field(default="", max_length=200)
    size: str = Field(default="1024x1024", pattern=r"^\d{3,4}x\d{3,4}$")
    credential_id: uuid.UUID | None = None
    # Dung confirms the provider's terms allow commercial use of outputs.
    commercial_use_confirmed: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def _https(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v and not (v.startswith("https://") or v.startswith("http://127.0.0.1")):
            raise ValueError("base_url phải là https:// (hoặc http://127.0.0.1 cho dịch vụ local)")
        return v

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)


class MediaSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tts_provider: Literal["vieneu", "zerotts", "fake_tts"] = "vieneu"
    asr_provider: Literal["none", "faster_whisper", "fake_asr"] = "none"
    asr_max_wer: float = Field(default=0.15, ge=0, le=1)
    encoder: Literal["libx264", "h264_nvenc"] = "libx264"
    subtitle_font: str = Field(default="Arial", max_length=100)
    burn_subtitles: bool = True
    cloud_image: CloudImageSettings = Field(default_factory=CloudImageSettings)


def get_settings(s: Session, company_id: uuid.UUID) -> MediaSettings:
    co = get_company(s, company_id)
    raw = (co.settings_json or {}).get("media") or {}
    try:
        return MediaSettings.model_validate(raw)
    except ValueError:
        return MediaSettings()


def put_settings(s: Session, company_id: uuid.UUID, value: MediaSettings) -> MediaSettings:
    co = get_company(s, company_id)
    data = dict(co.settings_json or {})
    data["media"] = value.model_dump(mode="json")
    co.settings_json = data
    s.flush()
    return value


TTS_PROVIDERS: dict[str, Any] = {"vieneu": VieneuTts(), "zerotts": ZeroTts(), "fake_tts": FakeTts()}
ASR_PROVIDERS: dict[str, Any] = {"faster_whisper": FasterWhisperAsr(), "fake_asr": FakeAsr()}
FAKE_IMAGE = FakeImage()


def check_license(meta: ProviderMeta) -> None:
    if meta.license.commercial is not True:
        raise LicenseBlocked(
            f"Provider {meta.provider_id} chưa xác nhận được phép dùng thương mại "
            f"(license: {meta.license.weights or meta.license.code}). Đã chặn theo ADR-0030."
        )


def tts_provider(provider_id: str) -> Any:
    p = TTS_PROVIDERS.get(provider_id)
    if p is None:
        raise DomainValidationError(f"Unknown TTS provider {provider_id}", code="unknown_provider")
    check_license(p.meta)
    return p


def asr_provider(provider_id: str) -> Any | None:
    if provider_id == "none":
        return None
    p = ASR_PROVIDERS[provider_id]
    check_license(p.meta)
    return p


def cloud_image_provider(
    cfg: CloudImageSettings, api_key: str | None, transport: Any = None
) -> OpenAiImages:
    if not cfg.configured:
        raise DomainValidationError(
            "Chưa cấu hình dịch vụ ảnh cloud (base URL + model) trong Cài đặt sản xuất",
            code="cloud_image_not_configured",
        )
    p = OpenAiImages(
        base_url=cfg.base_url,
        model=cfg.model,
        api_key=api_key,
        size=cfg.size,
        extra=cfg.extra,
        commercial_confirmed=cfg.commercial_use_confirmed,
        transport=transport,
    )
    check_license(p.meta)
    return p


def catalog() -> list[ProviderMeta]:
    metas = [p.meta for p in TTS_PROVIDERS.values()]
    metas += [p.meta for p in ASR_PROVIDERS.values()]
    metas.append(FAKE_IMAGE.meta)
    return metas
