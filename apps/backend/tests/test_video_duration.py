from __future__ import annotations

import pytest

from orchestra_backend.core.errors import DomainValidationError
from orchestra_backend.production import duration


def test_fit_keeps_whole_scenes_then_sentences():
    a = "Câu một ngắn. " * 3  # ~41 chars -> ~2.9 s with overhead
    kept, dropped = duration.fit_narrations([a.strip(), a.strip(), a.strip(), a.strip()], 6)
    assert len(kept) == 2 and dropped == 2


def test_fit_always_keeps_one_sentence():
    long = "Một câu rất dài " * 40 + "."
    kept, dropped = duration.fit_narrations([long, "Hai."], 5)
    assert kept == [long.strip()] and dropped == 1


def test_fit_trims_last_scene_by_sentence():
    one = "Câu thứ nhất này dài khoảng bốn mươi chữ."  # ~2.9 s each
    two = "Câu thứ hai này cũng dài bốn mươi chữ cái."
    s = f"{one} {two} Câu thứ ba này dài bốn mươi chữ cái luôn."
    kept, dropped = duration.fit_narrations([s], 4)
    assert kept == [one] and dropped == 0


def test_validate_respects_profile_and_machine_cap(monkeypatch):
    monkeypatch.setattr(duration, "MAX_S", 120.0)
    assert duration.validate_target(15, "short") == 15
    assert duration.limits("short") == (5, 90)
    assert duration.limits("long") == (5, 120)
    with pytest.raises(DomainValidationError):
        duration.validate_target(4, "short")
    with pytest.raises(DomainValidationError):
        duration.validate_target(150, "long")
