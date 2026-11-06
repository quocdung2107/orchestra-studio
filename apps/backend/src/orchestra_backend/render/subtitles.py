"""ASS subtitle writer (burned in by libass)."""

from __future__ import annotations

from pathlib import Path

from orchestra_backend.render.timeline import Timeline


def _ts(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def write_ass(tl: Timeline, path: Path, font: str) -> Path:
    st = tl.subtitle_style
    size, margin = int(st.get("font_size", 64)), int(st.get("margin_v", 80))
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {tl.canvas.w}",
        f"PlayResY: {tl.canvas.h}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(2, size // 16)},1,2,60,60,{margin},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for sc in tl.scenes:
        for c in sc.cues:
            lines.append(f"Dialogue: 0,{_ts(c.t0)},{_ts(c.t1)},Default,,0,0,0,,{_esc(c.text)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_srt(tl: Timeline, path: Path) -> Path:
    def ts(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out, n = [], 1
    for sc in tl.scenes:
        for c in sc.cues:
            out += [str(n), f"{ts(c.t0)} --> {ts(c.t1)}", c.text, ""]
            n += 1
    path.write_text("\n".join(out), encoding="utf-8")
    return path
