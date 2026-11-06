"""ASR / subtitle QA benchmark (LOCAL_AI_BENCHMARK_PLAN §7).

Needs the faster-whisper sidecar running (docs/MEDIA_ENGINES.md). Transcribes TTS outputs from a
tts_listen run and reports WER against Orchestra's normalized text:

    uv run --project apps/backend python bench/asr/run_asr_bench.py --listen bench/results/tts_listen/<run id>

PhoWhisper-small: run `phowhisper_transcribe.py` in its own venv first, then pass --pho-json.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ResourceSampler, write_rows  # noqa: E402

from orchestra_backend.media_gateway.providers.faster_whisper import FasterWhisperAsr  # noqa: E402
from orchestra_backend.render.wer import wer  # noqa: E402
from orchestra_backend.voice.normalize_vi import normalize  # noqa: E402

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", required=True, type=Path)
    ap.add_argument("--url", default="http://127.0.0.1:8012")
    ap.add_argument("--model-label", default="faster-whisper-small-int8")
    ap.add_argument("--pho-json", type=Path, help="transcripts from phowhisper_transcribe.py")
    a = ap.parse_args()
    texts = yaml.safe_load((HERE.parent / "tts" / "texts.yaml").read_text("utf-8"))
    with (a.listen / "key.csv").open(encoding="utf-8") as f:
        items = list(csv.DictReader(f))
    asr = FasterWhisperAsr()
    pho = json.loads(a.pho_json.read_text("utf-8")) if a.pho_json else {}
    rows = []
    for it in items:
        ref = normalize(texts[it["text_id"]]["text"])
        wav = a.listen / it["file"]
        with ResourceSampler() as rs:
            tr = asr.transcribe(wav, a.url)
        rows.append({"asr": a.model_label, "tts_engine": it["engine"], "text_id": it["text_id"],
                     "wer": round(wer(ref, tr.text), 4), "asr_s": round(rs.seconds, 2),
                     "min_free_ram_mb": rs.min_free_ram_mb, "hypothesis": tr.text[:300]})
        if it["file"] in pho:
            rows.append({"asr": "phowhisper-small", "tts_engine": it["engine"], "text_id": it["text_id"],
                         "wer": round(wer(ref, pho[it["file"]]["text"]), 4), "asr_s": pho[it["file"]]["seconds"],
                         "min_free_ram_mb": "", "hypothesis": pho[it["file"]]["text"][:300]})
        print(rows[-1])
    print("->", write_rows("asr", rows))


if __name__ == "__main__":
    main()
