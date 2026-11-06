"""Render benchmark R1-R4 (LOCAL_AI_BENCHMARK_PLAN §6) through Orchestra's real renderer.

    uv run --project apps/backend python bench/render/run_render_bench.py --cases R1,R2 --encoders libx264,h264_nvenc

Synthetic inputs (gradient images, tone voice) so nothing needs downloading. Each case renders
`--runs` times per encoder (the first run is reported separately as cold). Results -> bench/results/*.csv.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ResourceSampler, write_rows  # noqa: E402

from orchestra_backend.media_gateway import audio  # noqa: E402
from orchestra_backend.media_gateway.meta import TtsRequest  # noqa: E402
from orchestra_backend.media_gateway.providers.fakes import FakeTts, write_png  # noqa: E402
from orchestra_backend.render import ffmpeg_render, qa, subtitles  # noqa: E402
from orchestra_backend.render.presets import PROFILES  # noqa: E402
from orchestra_backend.render.timeline import (  # noqa: E402
    MOTIONS,
    Canvas,
    Music,
    Timeline,
    TimelineScene,
    Visual,
    VoicePlacement,
    cues_for_segment,
)

CASES = {  # id: (profile, seconds, images)
    "R1": ("short", 30, 6),
    "R2": ("short", 90, 15),
    "R3": ("long", 300, 40),
    "R4": ("long", 600, 80),
}
LINE = "Đây là câu thử nghiệm cho phụ đề tiếng Việt có dấu, đủ dài để xuống dòng."


def build_case(case: str, work: Path) -> tuple[Timeline, ffmpeg_render.RenderInputs]:
    profile_id, seconds, n = CASES[case]
    prof = PROFILES[profile_id]
    per = seconds / n
    images, scenes, parts = {}, [], []
    tts = FakeTts()
    seg_wav = work / "seg.wav"
    tts.synthesize(TtsRequest(text="x" * int(15 * (per - 0.6)), voice="bench"), None, seg_wav)
    seg_d = audio.duration(seg_wav)
    music = work / "music.wav"
    tts.synthesize(TtsRequest(text="m" * 300, voice="music"), None, music)
    for i in range(n):
        img = work / f"img{i}.png"
        write_png(img, prof.width, prof.height, (40 + i * 7 % 200, 80, 160), (10, 20 + i * 5 % 200, 40))
        aid = uuid.uuid4()
        images[str(aid)] = img
        start = i * per
        scenes.append(TimelineScene(
            id=uuid.uuid4(), index=i, start=round(start, 3), duration=round(per, 3),
            visual=Visual(asset_id=aid, motion=MOTIONS[i % len(MOTIONS)]),
            voice=[VoicePlacement(segment_id=uuid.uuid4(), asset_id=uuid.uuid4(), start=start + 0.3, duration=seg_d)],
            cues=cues_for_segment(LINE, start + 0.3, seg_d, prof.max_chars_per_line),
        ))
        parts += [(None, 0.3), (seg_wav, seg_d), (None, max(0.0, per - 0.3 - seg_d))]
    voice = work / "voice.wav"
    audio.concat_house(parts, voice)
    tl = Timeline(profile=profile_id, preset=prof.preset, canvas=Canvas(w=prof.width, h=prof.height, fps=prof.fps),
                  duration=round(per * n, 3), scenes=scenes, music=Music(asset_id=uuid.uuid4(), gain_db=-18),
                  subtitle_style={"font_size": prof.font_size, "margin_v": prof.margin_v})
    subtitles.write_ass(tl, work / "subs.ass", "Arial")
    return tl, ffmpeg_render.RenderInputs(images=images, voice_wav=voice, music=music, subtitles_ass="subs.ass")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="R1,R2,R3,R4")
    ap.add_argument("--encoders", default="libx264,h264_nvenc")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args()
    audio.configure(a.ffmpeg)
    version = ffmpeg_render.ffmpeg_version()
    rows = []
    for case in a.cases.split(","):
        work = Path(tempfile.mkdtemp(prefix=f"bench-{case}-"))
        try:
            tl, inp = build_case(case, work)
            for enc in a.encoders.split(","):
                for run in range(1, a.runs + 1):
                    args = ffmpeg_render.build_args(tl, inp, "out.mp4", enc)
                    err = ""
                    try:
                        with ResourceSampler() as rs:
                            ffmpeg_render.run_render(args, cwd=work, total_s=tl.duration, timeout_s=7200)
                        report = qa.run_qa(work / "out.mp4", tl, PROFILES[tl.profile], assets_license=[], placeholders=[])
                        passed, size = report["passed"], (work / "out.mp4").stat().st_size
                        failed = [c["id"] for c in report["checks"] if not c["ok"] and c["severity"] == "error"]
                    except Exception as exc:  # noqa: BLE001 - record and continue
                        rs = locals().get("rs")
                        passed, size, failed, err = False, 0, [], str(exc)[:300]
                    row = {
                        "case": case, "encoder": enc, "run": run, "cold": run == 1,
                        "video_s": tl.duration, "render_s": round(getattr(rs, "seconds", 0) or 0, 2),
                        "speed_x": round(tl.duration / rs.seconds, 2) if getattr(rs, "seconds", 0) else "",
                        "min_free_ram_mb": getattr(rs, "min_free_ram_mb", ""),
                        "max_vram_used_mb": getattr(rs, "max_vram_used_mb", ""),
                        "file_mb": round(size / 1e6, 1), "qa_passed": passed, "qa_failed": ";".join(failed),
                        "ffmpeg": version, "error": err,
                    }
                    print(row)
                    rows.append(row)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    print("->", write_rows("render", rows))


if __name__ == "__main__":
    main()
