"""Shared helpers: paths, hashing, JSONL I/O, text normalisation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MANIFESTS = ROOT / "data" / "manifests"
ARTIFACTS = ROOT / "artifacts"
CONFIGS = ROOT / "configs"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_text(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_WS = re.compile(r"\s+")


def normalize_question(q: str) -> str:
    """Whitespace/case-insensitive key for matching the same word problem across datasets."""
    return _WS.sub(" ", q.strip()).lower()


def percentiles(values: list[int | float], ps=(50, 90, 95, 99)) -> dict[str, float]:
    if not values:
        return {f"p{p}": 0.0 for p in ps} | {"min": 0.0, "max": 0.0, "mean": 0.0}
    vs = sorted(values)
    out = {}
    for p in ps:
        idx = min(len(vs) - 1, int(round((p / 100.0) * (len(vs) - 1))))
        out[f"p{p}"] = float(vs[idx])
    out["min"] = float(vs[0])
    out["max"] = float(vs[-1])
    out["mean"] = float(sum(vs) / len(vs))
    return out
