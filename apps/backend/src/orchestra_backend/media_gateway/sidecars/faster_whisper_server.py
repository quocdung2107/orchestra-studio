"""faster-whisper sidecar. Runs in its own venv (`pip install faster-whisper`).

    python faster_whisper_server.py --port 8012 --model small --compute-type int8

GET /health; POST /transcribe?language=vi with a WAV body -> {"text", "language", "words": [...]}.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MODEL = None
LOCK = threading.Lock()
MAX_BODY = 200 * 1024 * 1024


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
            self._json(200, {"status": "ok", "engine": "faster_whisper"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path != "/transcribe":
            self._json(404, {"error": "not found"})
            return
        n = int(self.headers.get("content-length") or 0)
        if n <= 0 or n > MAX_BODY:
            self._json(413, {"error": "bad body size"})
            return
        lang = parse_qs(url.query).get("language", ["vi"])[0]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "in.wav"
            p.write_bytes(self.rfile.read(n))
            with LOCK:
                segments, info = MODEL.transcribe(str(p), language=lang, word_timestamps=True)
                words, texts = [], []
                for seg in segments:
                    texts.append(seg.text.strip())
                    for w in seg.words or []:
                        words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
        self._json(200, {"text": " ".join(texts), "language": info.language, "words": words})

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def main() -> None:
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8012)
    ap.add_argument("--model", default="small")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    from faster_whisper import WhisperModel

    MODEL = WhisperModel(a.model, device="cpu", compute_type=a.compute_type, cpu_threads=a.threads)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
