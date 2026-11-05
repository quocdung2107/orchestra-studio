from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_FILE = Path(__file__).with_name("pricing.yaml")


@dataclass(frozen=True)
class PriceTable:
    as_of: str
    source: str
    models: dict[str, dict[str, float]]

    def cost_usd(self, model: str, input_tokens: int, output_tokens: int) -> float | None:
        p = self.models.get(model)
        if p is None:
            return None
        inp, out = p["input"], p["output"]
        threshold = p.get("long_threshold")
        if threshold and input_tokens > threshold:
            inp, out = p.get("long_input", inp), p.get("long_output", out)
        return (input_tokens * inp + output_tokens * out) / 1_000_000


@lru_cache(maxsize=1)
def load(path: Path = _FILE) -> PriceTable:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PriceTable(
        as_of=str(raw.get("as_of", "")),
        source=str(raw.get("source", "")),
        models={
            str(k): {kk: float(vv) for kk, vv in v.items()}
            for k, v in (raw.get("models") or {}).items()
        },
    )
