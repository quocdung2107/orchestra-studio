"""Write the OpenAPI document (ADR-0003 single source of truth).

Usage: uv run python -m orchestra_backend.export_openapi [output_path]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from orchestra_backend.app import create_app
from orchestra_backend.core.config import Settings

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "packages" / "contracts" / "openapi.json"


def build_openapi() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(data_dir=Path(tmp), token="export"))  # noqa: S106
        doc = app.openapi()
        app.state.container.engine.dispose()
    return doc


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(build_openapi()), encoding="utf-8", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
