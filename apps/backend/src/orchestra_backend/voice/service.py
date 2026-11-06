from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import DomainValidationError, NotFoundError
from orchestra_backend.media.models import Asset
from orchestra_backend.voice.models import VoiceProfile, VoiceProfileVersion
from orchestra_backend.voice.schemas import (
    VoiceProfileCreate,
    VoiceProfileOut,
    VoiceProfileVersionOut,
    VoiceSettings,
)

# Dung's choice (2026-11-06): Southern female voice, configurable. "Thùy Dung" is listed by the
# VieNeu README under Southern + editors' picks; gender inferred from the name, not verified.
DEFAULT_PROFILE = VoiceProfileCreate(
    name="Giọng kênh — nữ miền Nam",
    engine="vieneu",
    voice="Thùy Dung",
    dialect="south",
    is_default=True,
)


def _version(s: Session, profile_id: uuid.UUID, version: int) -> VoiceProfileVersion:
    v = s.scalar(
        select(VoiceProfileVersion).where(
            VoiceProfileVersion.profile_id == profile_id, VoiceProfileVersion.version == version
        )
    )
    assert v is not None
    return v


def to_out(s: Session, p: VoiceProfile) -> VoiceProfileOut:
    v = _version(s, p.id, p.current_version)
    return VoiceProfileOut(
        id=p.id,
        company_id=p.company_id,
        name=p.name,
        is_default=p.is_default,
        current_version=p.current_version,
        current=VoiceProfileVersionOut.model_validate(v),
    )


def _check_reference(s: Session, company_id: uuid.UUID, data: VoiceSettings) -> None:
    if data.reference_asset_id is None:
        return
    a = s.get(Asset, data.reference_asset_id)
    if a is None or a.company_id != company_id or a.kind != "reference_audio":
        raise DomainValidationError("Tham chiếu giọng không hợp lệ", code="invalid_reference")
    if not data.consent_note.strip():
        raise DomainValidationError(
            "Clone giọng cần ghi chú đồng ý của người có giọng", code="consent_required"
        )


def _new_version(profile: VoiceProfile, version: int, data: VoiceSettings) -> VoiceProfileVersion:
    return VoiceProfileVersion(
        profile_id=profile.id,
        version=version,
        engine=data.engine,
        voice=data.voice,
        dialect=data.dialect,
        speed=data.speed,
        max_chars=data.max_chars,
        params_json=dict(data.params),
        lexicon_json=dict(data.lexicon),
        reference_asset_id=data.reference_asset_id,
        consent_note=data.consent_note,
    )


def create(s: Session, company_id: uuid.UUID, data: VoiceProfileCreate) -> VoiceProfile:
    get_company(s, company_id)
    _check_reference(s, company_id, data)
    if data.is_default:
        for p in s.scalars(select(VoiceProfile).where(VoiceProfile.company_id == company_id)):
            p.is_default = False
    p = VoiceProfile(company_id=company_id, name=data.name, is_default=data.is_default)
    s.add(p)
    s.flush()
    s.add(_new_version(p, 1, data))
    s.flush()
    return p


def update(s: Session, p: VoiceProfile, data: VoiceSettings) -> VoiceProfile:
    _check_reference(s, p.company_id, data)
    p.current_version += 1
    s.add(_new_version(p, p.current_version, data))
    s.flush()
    return p


def get(s: Session, profile_id: uuid.UUID) -> VoiceProfile:
    p = s.get(VoiceProfile, profile_id)
    if p is None:
        raise NotFoundError("Voice profile not found", code="voice_profile_not_found")
    return p


def list_for(s: Session, company_id: uuid.UUID) -> list[VoiceProfile]:
    return list(
        s.scalars(
            select(VoiceProfile)
            .where(VoiceProfile.company_id == company_id)
            .order_by(VoiceProfile.created_at)
        )
    )


def default_for(s: Session, company_id: uuid.UUID) -> VoiceProfile:
    p = s.scalar(
        select(VoiceProfile).where(
            VoiceProfile.company_id == company_id, VoiceProfile.is_default.is_(True)
        )
    )
    return p or create(s, company_id, DEFAULT_PROFILE)


def current_version(s: Session, p: VoiceProfile) -> VoiceProfileVersion:
    return _version(s, p.id, p.current_version)
