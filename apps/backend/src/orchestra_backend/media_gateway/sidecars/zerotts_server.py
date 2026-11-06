"""ZeroTTS sidecar. Runs in ZeroTTS's own venv, NOT in the backend venv.

    python zerotts_server.py --port 8011 [--model zeroweight-ai/ZeroTTS]

Stdlib HTTP only, loopback only. Endpoints: GET /health, GET /voices, POST /synthesize
{"text", "voice", optional cfg_scale/audio_temperature/audio_topk/audio_topp/
audio_repetition_penalty/seed} -> audio/wav. Text must already be normalized by Orchestra.
"""

from __future__ import annotations

import argparse
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TTS = None
LOCK = threading.Lock()  # one synthesis at a time (CPU)
KEYS = ("cfg_scale", "audio_temperature", "audio_topk", "audio_topp", "audio_repetition_penalty")
MAX_BODY = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: object) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok", "engine": "zerotts"})
        elif self.path == "/voices":
            out = []
            for vid in TTS.list_voices():
                v = TTS.load_voice(vid)
                out.append(
                    {
                        "id": vid,
                        "name": getattr(v, "display_name", vid),
                        "gender": getattr(v, "gender", ""),
                        "tags": getattr(v, "tags", []),
                    }
                )
            self._json(200, {"data": out})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/synthesize":
            self._json(404, {"error": "not found"})
            return
        n = int(self.headers.get("content-length") or 0)
        if n <= 0 or n > MAX_BODY:
            self._json(413, {"error": "body too large"})
            return
        try:
            req = json.loads(self.rfile.read(n))
            text = str(req["text"])
            voice = req.get("voice") or None
            kwargs = {k: req[k] for k in KEYS if k in req}
            if voice is None:
                raise ValueError("voice is required (voice=None is not stable across runs)")
        except (ValueError, KeyError) as exc:
            self._json(400, {"error": str(exc)})
            return
        with LOCK:
            if "seed" in req:
                import numpy as np

                np.random.seed(int(req["seed"]))
            audio = TTS.synthesize(text, voice=voice, **kwargs)
            buf = io.BytesIO()
            import soundfile as sf

            sf.write(buf, audio.reshape(-1), TTS.sample_rate, format="WAV", subtype="PCM_16")
        data = buf.getvalue()
        self.send_response(200)
        self.send_header("content-type", "audio/wav")
        self.send_header("content-length", str(len(data)))
        self.send_header("x-engine-version", "zerotts")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def main() -> None:
    global TTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--model", default="zeroweight-ai/ZeroTTS")
    a = ap.parse_args()
    from zerotts import ZeroTTS

    TTS = ZeroTTS.from_pretrained(a.model)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
