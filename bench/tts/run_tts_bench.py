"""Vietnamese TTS benchmark (LOCAL_AI_BENCHMARK_PLAN §3) against running engines.

Start the engines first (docs/MEDIA_ENGINES.md), then from the repo root:

    uv run --project apps/backend python bench/tts/run_tts_bench.py --engines vieneu,zerotts \
        --vieneu-voice "Thùy Dung" --zerotts-voice maichi --runs 3

Writes:
  bench/results/<date>_<machine>_tts.csv          one row per synthesis (RTF, RAM, VRAM)
  bench/results/tts_listen/<run id>/*.wav         blinded files for MOS listening
  bench/results/tts_listen/<run id>/key.csv       which file is which (open only after scoring)
  bench/results/tts_listen/<run id>/mos_sheet.csv blank score sheet (1-5)
T11: 40 segments + segment 17 generated again, to listen for voice drift.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RESULTS, ResourceSampler, write_rows  # noqa: E402

from orchestra_backend.media_gateway import audio  # noqa: E402
from orchestra_backend.media_gateway.meta import TtsRequest  # noqa: E402
from orchestra_backend.media_gateway.providers.vieneu import VieneuTts  # noqa: E402
from orchestra_backend.media_gateway.providers.zerotts import ZeroTts  # noqa: E402
from orchestra_backend.voice.normalize_vi import normalize  # noqa: E402
from orchestra_backend.voice.segment import split_segments  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
URLS = {"vieneu": "http://127.0.0.1:8000", "zerotts": "http://127.0.0.1:8011"}


def t11_segments() -> list[str]:
    data = json.loads((REPO / "templates/video_samples/long_mat_troi.json").read_text("utf-8"))
    segs: list[str] = []
    while len(segs) < 40:
        for sc in data["scenes"]:
            segs += split_segments(sc["narration"], 180)
    return segs[:40]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="vieneu,zerotts")
    ap.add_argument("--vieneu-voice", default="Thùy Dung")
    ap.add_argument("--zerotts-voice", default="maichi")
    ap.add_argument("--runs", type=int, default=3, help="runs per text; run 1 is cold")
    ap.add_argument("--skip-t11", action="store_true")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args()
    audio.configure(a.ffmpeg)
    texts = yaml.safe_load((HERE / "texts.yaml").read_text("utf-8"))
    providers = {"vieneu": (VieneuTts(), a.vieneu_voice), "zerotts": (ZeroTts(), a.zerotts_voice)}
    run_id = time.strftime("%Y%m%d-%H%M%S")
    listen = RESULTS / "tts_listen" / run_id
    listen.mkdir(parents=True, exist_ok=True)
    rows, key = [], []
    for eng in a.engines.split(","):
        prov, voice = providers[eng]
        jobs = [(tid, t["text"]) for tid, t in texts.items()]
        if not a.skip_t11:
            segs = t11_segments()
            jobs += [(f"T11-{i + 1:02d}", s) for i, s in enumerate(segs)] + [("T11-17b", segs[16])]
        for tid, raw in jobs:
            norm = normalize(raw, dialect="south")
            runs = 1 if tid.startswith("T11") else a.runs
            for run in range(1, runs + 1):
                out = listen / f"_{eng}_{tid}_{run}.wav"
                err, dur = "", 0.0
                with ResourceSampler() as rs:
                    try:
                        prov.synthesize(TtsRequest(text=norm, voice=voice), URLS[eng], out)
                    except Exception as exc:  # noqa: BLE001 - record and continue
                        err = str(exc)[:300]
                if not err:
                    house = out.with_suffix(".house.wav")
                    audio.to_house_wav(out, house)
                    dur = audio.duration(house)
                    house.replace(out)
                row = {"engine": eng, "voice": voice, "text_id": tid, "run": run, "cold": run == 1,
                       "chars": len(norm), "audio_s": round(dur, 2), "synth_s": round(rs.seconds, 2),
                       "rtf": round(rs.seconds / dur, 3) if dur else "",
                       "min_free_ram_mb": rs.min_free_ram_mb, "max_vram_used_mb": rs.max_vram_used_mb,
                       "error": err}
                print(row)
                rows.append(row)
                if not err and (run == runs) and not tid.startswith("T11"):
                    key.append((eng, tid, out))
                elif not err and tid.startswith("T11"):
                    out.rename(listen / f"t11_{eng}_{tid}.wav")
                else:
                    out.unlink(missing_ok=True)
    # Blind the files used for MOS: random names, key kept separately.
    random.shuffle(key)
    with (listen / "key.csv").open("w", newline="", encoding="utf-8") as kf, \
         (listen / "mos_sheet.csv").open("w", newline="", encoding="utf-8") as sf:
        kw, sw = csv.writer(kf), csv.writer(sf)
        kw.writerow(["file", "engine", "text_id"])
        sw.writerow(["file", "text_id", "naturalness_1_5", "accent_1_5", "emotion_1_5", "mispronounced_words", "note"])
        for i, (eng, tid, path) in enumerate(key, 1):
            name = f"sample_{i:03d}.wav"
            path.rename(listen / name)
            kw.writerow([name, eng, tid])
            sw.writerow([name, tid, "", "", "", "", ""])
    print("->", write_rows("tts", rows))
    print("-> nghe và chấm:", listen / "mos_sheet.csv")


if __name__ == "__main__":
    main()
