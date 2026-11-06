"""Run in a separate venv: `pip install transformers torch soundfile` (CPU torch).

    python bench/asr/phowhisper_transcribe.py bench/results/tts_listen/<run id> out.json
"""

import json
import sys
import time
from pathlib import Path

from transformers import pipeline

folder, out = Path(sys.argv[1]), Path(sys.argv[2])
asr = pipeline("automatic-speech-recognition", model="vinai/PhoWhisper-small", device="cpu")
res = {}
for wav in sorted(folder.glob("sample_*.wav")):
    t0 = time.perf_counter()
    text = asr(str(wav))["text"]
    res[wav.name] = {"text": text, "seconds": round(time.perf_counter() - t0, 2)}
    print(wav.name, text)
out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
