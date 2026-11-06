"""Benchmark texts T3-T6 (LOCAL_AI_BENCHMARK_PLAN §3.1) with expected readings (plan L8)."""

from __future__ import annotations

import pytest

from orchestra_backend.voice.normalize_vi import normalize, number_words
from orchestra_backend.voice.segment import split_segments


@pytest.mark.parametrize(
    ("n", "south", "north"),
    [
        (0, "không", "không"),
        (15, "mười lăm", "mười lăm"),
        (21, "hai mươi mốt", "hai mươi mốt"),
        (24, "hai mươi tư", "hai mươi tư"),
        (105, "một trăm lẻ năm", "một trăm linh năm"),
        (1001, "một ngàn không trăm lẻ một", "một nghìn không trăm linh một"),
        (1945, "một ngàn chín trăm bốn mươi lăm", "một nghìn chín trăm bốn mươi lăm"),
        (1_250_000, "một triệu hai trăm năm mươi ngàn", "một triệu hai trăm năm mươi nghìn"),
        (2_000_000_000, "hai tỷ", "hai tỷ"),
    ],
)
def test_numbers_by_dialect(n, south, north):
    assert number_words(n, "south") == south
    assert number_words(n, "north") == north


def test_t3_proper_names_keep_text_and_soften_dash():
    out = normalize(
        "Nguyễn Thị Minh Khai, Đắk Lắk, Phan Rang–Tháp Chàm, Albert Einstein, Marie Curie"
    )
    assert out == "Nguyễn Thị Minh Khai, Đắk Lắk, Phan Rang Tháp Chàm, Albert Einstein, Marie Curie"


def test_t4_dates_times_quarters_centuries():
    out = normalize("Ngày 02/09/1945, lúc 14h30; quý III/2026; thế kỷ XXI", dialect="north")
    assert out == (
        "Ngày hai tháng chín năm một nghìn chín trăm bốn mươi lăm, lúc mười bốn giờ ba mươi phút; "
        "quý ba năm hai nghìn không trăm hai mươi sáu; thế kỷ hai mươi mốt"
    )


def test_t5_numbers_money_units():
    out = normalize("1.250.000 đồng; 3,14; 25%; 1/3; 150 km/h; 2.000 m²; −5°C")
    assert out == (
        "một triệu hai trăm năm mươi ngàn đồng; ba phẩy mười bốn; hai mươi lăm phần trăm; "
        "một phần ba; một trăm năm mươi ki lô mét trên giờ; hai ngàn mét vuông; âm năm độ C"
    )


def test_t6_english_terms_use_channel_lexicon():
    out = normalize(
        "Mô hình AI dùng GPU NVIDIA và framework PyTorch",
        lexicon={"NVIDIA": "en vi đi a", "PyTorch": "pai torch"},
    )
    assert out == "Mô hình ây ai dùng gi pi u en vi đi a và framework pai torch"


def test_ordinals_months_ranges_and_short_dates():
    out = normalize("Thứ 4 ngày 2/9 lúc 8h, tháng 4/2025, giai đoạn 2020–2026, 0,05%, $5.")
    assert out == (
        "Thứ tư ngày hai tháng chín lúc tám giờ, tháng tư năm hai ngàn không trăm hai mươi lăm, "
        "giai đoạn hai ngàn không trăm hai mươi đến hai ngàn không trăm hai mươi sáu, "
        "không phẩy không năm phần trăm, năm đô la."
    )


def test_lexicon_matches_whole_words_only():
    assert normalize("TRAIN và AI") == "TRAIN và ây ai"


def test_segments_split_by_sentence_and_length():
    text = "Câu một. Câu hai! " + "rất dài, " * 30 + "hết."
    segs = split_segments(text, 80)
    assert segs[0] == "Câu một." and segs[1] == "Câu hai!"
    assert all(len(s) <= 80 for s in segs)
    assert " ".join(segs).replace("  ", " ") == " ".join(text.split())


def test_normalize_preview_endpoint(client):
    r = client.post(
        "/api/v1/voice/normalize-preview", json={"text": "Giá 99.000đ. Lúc 7h15.", "max_chars": 60}
    )
    assert r.status_code == 200
    assert r.json()["segments"] == ["Giá chín mươi chín ngàn đồng.", "Lúc bảy giờ mười lăm phút."]
