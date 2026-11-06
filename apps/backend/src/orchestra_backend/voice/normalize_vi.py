"""Vietnamese text normalization before TTS (ADR-0031, plan L8).

Pure stdlib. Reads numbers, decimals, percentages, money, dates, clock times, units, Roman
numerals after words such as "thế kỷ"/"quý", ordinals after "thứ", and applies a per-channel
pronunciation lexicon. Dialect "south" says "ngàn"/"lẻ"; "north" says "nghìn"/"linh".
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Dialect = Literal["south", "north"]

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

DEFAULT_LEXICON: dict[str, str] = {
    "AI": "ây ai",
    "GPU": "gi pi u",
    "CPU": "xi pi u",
    "TP.HCM": "thành phố Hồ Chí Minh",
    "TP HCM": "thành phố Hồ Chí Minh",
    "v.v.": "vân vân",
    "&": "và",
}

UNITS: list[tuple[str, str]] = [
    ("km/h", "ki lô mét trên giờ"),
    ("m/s", "mét trên giây"),
    ("km²", "ki lô mét vuông"),
    ("m²", "mét vuông"),
    ("m2", "mét vuông"),
    ("m³", "mét khối"),
    ("km", "ki lô mét"),
    ("cm", "xen ti mét"),
    ("mm", "mi li mét"),
    ("kg", "ki lô gam"),
    ("mg", "mi li gam"),
    ("ml", "mi li lít"),
    ("°C", "độ C"),
    ("°F", "độ F"),
    ("kWh", "ki lô oát giờ"),
    ("kW", "ki lô oát"),
    ("GB", "gi ga bai"),
    ("MB", "mê ga bai"),
    ("Hz", "héc"),
    ("m", "mét"),
    ("g", "gam"),
    ("l", "lít"),
    ("h", "giờ"),
    ("s", "giây"),
]
CURRENCY = [("VNĐ", "đồng"), ("VND", "đồng"), ("đ", "đồng"), ("USD", "đô la Mỹ"), ("$", "đô la")]
ROMAN_CONTEXT = r"(thế kỷ|thế kỉ|quý|chương|phần|khóa|khoá|tập|kỳ|kì)"


@dataclass(frozen=True)
class Words:
    thousand: str
    zero_tens: str


def _words(dialect: Dialect) -> Words:
    return Words("ngàn", "lẻ") if dialect == "south" else Words("nghìn", "linh")


def _read_triple(n: int, full: bool, w: Words) -> list[str]:
    h, t, u = n // 100, (n // 10) % 10, n % 10
    out: list[str] = []
    if h or full:
        out += [DIGITS[h], "trăm"]
    if t == 0:
        if u:
            if h or full:
                out.append(w.zero_tens)
            out.append(DIGITS[u])
    elif t == 1:
        out.append("mười")
        if u:
            out.append("lăm" if u == 5 else DIGITS[u])
    else:
        out += [DIGITS[t], "mươi"]
        if u == 1:
            out.append("mốt")
        elif u == 4:
            out.append("tư")
        elif u == 5:
            out.append("lăm")
        elif u:
            out.append(DIGITS[u])
    return out


def number_words(n: int, dialect: Dialect = "south") -> str:
    if n < 0:
        return "âm " + number_words(-n, dialect)
    if n == 0:
        return "không"
    w = _words(dialect)
    if n >= 1_000_000_000:
        hi, lo = divmod(n, 1_000_000_000)
        rest = _below_billion(lo, True, w) if lo else []
        return " ".join([number_words(hi, dialect), "tỷ", *rest])
    return " ".join(_below_billion(n, False, w))


def _below_billion(n: int, full: bool, w: Words) -> list[str]:
    groups = [(n // 1_000_000) % 1000, (n // 1000) % 1000, n % 1000]
    names = ["triệu", w.thousand, ""]
    out: list[str] = []
    started = full
    for g, name in zip(groups, names, strict=True):
        if g == 0:
            continue
        out += _read_triple(g, started, w)
        if name:
            out.append(name)
        started = True
    return out


def digits_words(s: str) -> str:
    return " ".join(DIGITS[int(c)] for c in s)


def _int_from(s: str) -> int:
    return int(s.replace(".", ""))


def _decimal(int_part: str, frac: str, d: Dialect) -> str:
    left = number_words(_int_from(int_part), d)
    right = (
        digits_words(frac) if frac.startswith("0") or len(frac) > 3 else number_words(int(frac), d)
    )
    return f"{left} phẩy {right}"


def _month(m: int, d: Dialect) -> str:
    return "tư" if m == 4 else number_words(m, d)


def _roman(s: str) -> int | None:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    if not s or any(c not in vals for c in s):
        return None
    total = 0
    for i, c in enumerate(s):
        v = vals[c]
        total += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
    return total if 0 < total < 400 else None


NUM = r"\d{1,3}(?:\.\d{3})+|\d+"


def normalize(
    text: str,
    *,
    dialect: Dialect = "south",
    lexicon: Mapping[str, str] | None = None,
) -> str:
    d = dialect
    t = text.replace("−", "-").replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t).strip()

    # Lexicon first (longest keys first), whole tokens only.
    lex = {**DEFAULT_LEXICON, **(lexicon or {})}
    for key in sorted(lex, key=len, reverse=True):
        pat = r"(?<![\wÀ-ỹ])" + re.escape(key) + r"(?![\wÀ-ỹ])"
        t = re.sub(pat, lex[key], t)

    # Roman numerals after context words: "thế kỷ XXI" -> "thế kỷ hai mươi mốt".
    def roman(m: re.Match[str]) -> str:
        v = _roman(m.group(2))
        return f"{m.group(1)} {number_words(v, d)}" if v else m.group(0)

    t = re.sub(ROMAN_CONTEXT + r"\s+([IVXLC]+)\b", roman, t, flags=re.IGNORECASE)
    # "quý ba/2026" after roman conversion -> "quý ba năm 2026"
    t = re.sub(
        ROMAN_CONTEXT + r" ([^\W\d_]+(?: [^\W\d_]+)*)/(\d{4})\b",
        lambda m: f"{m.group(1)} {m.group(2)} năm {m.group(3)}",
        t,
        flags=re.IGNORECASE,
    )

    # Full dates dd/mm/yyyy (also with - or .)
    def date_full(m: re.Match[str]) -> str:
        pre, day, mon, year = m.group(1) or "", int(m.group(2)), int(m.group(3)), int(m.group(4))
        if not (1 <= day <= 31 and 1 <= mon <= 12):
            return m.group(0)
        word = "" if pre else "ngày "
        return (
            f"{pre}{word}{number_words(day, d)} tháng {_month(mon, d)} năm {number_words(year, d)}"
        )

    t = re.sub(
        r"(ngày\s+)?\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b", date_full, t, flags=re.IGNORECASE
    )
    # Month/year: "tháng 9/2026" or "09/2026"
    t = re.sub(
        r"\btháng\s+(\d{1,2})/(\d{4})\b",
        lambda m: f"tháng {_month(int(m.group(1)), d)} năm {number_words(int(m.group(2)), d)}",
        t,
    )
    # "ngày 2/9" (day/month with context)
    t = re.sub(
        r"\b(ngày|mùng|hôm)\s+(\d{1,2})/(\d{1,2})\b",
        lambda m: (
            f"{m.group(1)} {number_words(int(m.group(2)), d)} tháng {_month(int(m.group(3)), d)}"
        ),
        t,
        flags=re.IGNORECASE,
    )
    # "tháng 4" -> "tháng tư"
    t = re.sub(r"\btháng\s+(\d{1,2})\b", lambda m: f"tháng {_month(int(m.group(1)), d)}", t)

    # "năm 1945"
    # Clock times: 14h30, 14:30, 8h, 8 giờ 5 phút
    def clock(m: re.Match[str]) -> str:
        hh, mm = int(m.group(1)), m.group(2)
        if hh > 24:
            return m.group(0)
        out = f"{number_words(hh, d)} giờ"
        if mm and int(mm):
            out += f" {number_words(int(mm), d)} phút"
        return out

    t = re.sub(r"\b(\d{1,2})[h:](\d{2})\b", clock, t)
    t = re.sub(r"\b(\d{1,2})h()(?![\wÀ-ỹ])", clock, t)

    # Ordinals: "thứ 1" -> "thứ nhất", "thứ 4" -> "thứ tư"
    t = re.sub(
        r"\b(thứ)\s+(\d+)\b",
        lambda m: (
            m.group(1)
            + " "
            + {"1": "nhất", "4": "tư"}.get(m.group(2), number_words(int(m.group(2)), d))
        ),
        t,
        flags=re.IGNORECASE,
    )

    # Numeric ranges "2020–2026" / "5-10" -> "đến"
    t = re.sub(rf"\b({NUM})\s*[–—-]\s*({NUM})\b", r"\1 đến \2", t)
    # Words joined by dashes: "Phan Rang–Tháp Chàm" -> pause
    t = re.sub(r"(?<=[^\W\d_])\s*[–—]\s*(?=[^\W\d_])", " ", t)

    # Percent / money / units on numbers (decimal comma or thousands dots)
    numval = rf"(-)?({NUM})(?:,(\d+))?"

    def num_text(sign: str | None, ip: str, frac: str | None) -> str:
        s = _decimal(ip, frac, d) if frac else number_words(_int_from(ip), d)
        return ("âm " + s) if sign else s

    t = re.sub(rf"(?<![\w,]){numval}\s?%", lambda m: num_text(*m.groups()) + " phần trăm", t)
    for sym, word in CURRENCY:
        if sym == "$":
            t = re.sub(rf"\$\s?{numval}", lambda m, w=word: num_text(*m.groups()) + " " + w, t)
        else:
            t = re.sub(
                rf"(?<![\w,]){numval}\s?{re.escape(sym)}(?![\wÀ-ỹ])",
                lambda m, w=word: num_text(*m.groups()) + " " + w,
                t,
            )
    for sym, word in UNITS:
        t = re.sub(
            rf"(?<![\w,]){numval}\s?{re.escape(sym)}(?![\wÀ-ỹ²³/])",
            lambda m, w=word: num_text(*m.groups()) + " " + w,
            t,
        )

    # English-style decimals "3.5" (not a thousands group) -> "ba phẩy năm"
    t = re.sub(
        r"(?<![\w.,])(\d+)\.(\d{1,2}|\d{4,})(?![\d.])",
        lambda m: _decimal(m.group(1), m.group(2), d),
        t,
    )

    # Fractions a/b (dates were handled above)
    t = re.sub(
        r"(?<![\w/])(\d{1,3})/(\d{1,3})(?![\w/])",
        lambda m: f"{number_words(int(m.group(1)), d)} phần {number_words(int(m.group(2)), d)}",
        t,
    )

    # Remaining numbers (signed, decimal, thousands)
    t = re.sub(rf"(?<![\w,.]){numval}(?![\w])", lambda m: num_text(*m.groups()), t)
    t = re.sub(r"\d+", lambda m: number_words(int(m.group(0)), d), t)

    # Units after spelled-out scale words: "150 triệu km" -> "... triệu ki lô mét".
    for sym, word in UNITS:
        if len(sym) > 1:
            t = re.sub(
                rf"\b(triệu|tỷ|ngàn|nghìn|trăm|mươi|mười) {re.escape(sym)}(?![\wÀ-ỹ²³/])",
                lambda m, w=word: f"{m.group(1)} {w}",
                t,
            )

    t = re.sub(r"\s+([,.!?;:])", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()
