"""Fetch the pinned third-party datasets into data/raw/ and write data/manifests/sources.json.

Everything is pinned to an exact Hugging Face dataset revision and checked by sha256, so
`python src/download_mathdial.py` reproduces the raw inputs byte-for-byte.

Sources and licenses (keep this block accurate; it is copied into the manifest):
  MathDial   eth-nlped/mathdial          CC BY-SA 4.0 per the official GitHub README
             (the HF card says CC BY 4.0; we treat the dataset as BY-SA, the stricter reading).
  GSM8K      openai/gsm8k                MIT. Used only for (a) canonical "#### answer" labels and
             calculator annotations to verify evidence payloads, (b) held-out problems that MathDial
             never used.
  MMLU-Redux edinburgh-dawg/mmlu-redux   CC BY 4.0. Non-math capability regression alarm only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_RAW, MANIFESTS, read_jsonl, sha256_file, write_json, write_jsonl  # noqa: E402

MATHDIAL = {
    "repo_id": "eth-nlped/mathdial",
    "revision": "acc3878459e0bd8c04ab840056572f0b8b1abe1f",
    "license": "CC BY-SA 4.0 (official repo README; HF card shows CC BY 4.0 -- treat as BY-SA)",
    "citation": "Macina et al. 2023, MathDial, arXiv:2305.14536",
    "files": {
        "train.jsonl": "d6135869c02dccf8d14756fa2f0367c5352922bb263ec22dc0eeace4da815d43",
        "test.jsonl": "3ec54ee8ab921dc6191bf5e2ee766d4e7916b4264394eb17a6be9b3fe486e50b",
    },
}
GSM8K = {
    "repo_id": "openai/gsm8k",
    "revision": "740312add88f781978c0658806c59bc2815b9866",
    "config": "main",
    "license": "MIT",
    "citation": "Cobbe et al. 2021, GSM8K, arXiv:2110.14168",
}
MMLU_REDUX = {
    "repo_id": "edinburgh-dawg/mmlu-redux",
    "revision": "3720db6aeb3d019de48bf37916c1a54074ff4997",
    "license": "CC BY 4.0",
    "citation": "Gema et al. 2024, Are We Done with MMLU?, arXiv:2406.04127",
    # Non-math subjects used for the capability regression alarm (see build_capability_items.py).
    "subjects": ["business_ethics", "high_school_us_history", "philosophy", "professional_law", "anatomy"],
}


def fetch_mathdial(force: bool) -> dict:
    out_dir = DATA_RAW / "mathdial"
    out_dir.mkdir(parents=True, exist_ok=True)
    info = {}
    for fname, expected in MATHDIAL["files"].items():
        dest = out_dir / fname
        if dest.exists() and not force and sha256_file(dest) == expected:
            print(f"[mathdial] {fname} present, sha256 ok")
        else:
            print(f"[mathdial] downloading {fname} @ {MATHDIAL['revision'][:12]}")
            src = hf_hub_download(
                repo_id=MATHDIAL["repo_id"],
                filename=fname,
                repo_type="dataset",
                revision=MATHDIAL["revision"],
            )
            dest.write_bytes(Path(src).read_bytes())
        got = sha256_file(dest)
        if got != expected:
            raise SystemExit(f"[mathdial] sha256 mismatch for {fname}: {got} != {expected}")
        info[fname] = {"sha256": got, "bytes": dest.stat().st_size, "n_rows": len(read_jsonl(dest))}
    return info


def fetch_gsm8k(force: bool) -> dict:
    from datasets import load_dataset

    out_dir = DATA_RAW / "gsm8k"
    out_dir.mkdir(parents=True, exist_ok=True)
    info = {}
    for split in ("train", "test"):
        dest = out_dir / f"{split}.jsonl"
        if dest.exists() and not force:
            print(f"[gsm8k] {split}.jsonl present")
        else:
            print(f"[gsm8k] downloading {split} @ {GSM8K['revision'][:12]}")
            ds = load_dataset(GSM8K["repo_id"], GSM8K["config"], split=split, revision=GSM8K["revision"])
            write_jsonl(dest, ({"index": i, **row} for i, row in enumerate(ds)))
        info[f"{split}.jsonl"] = {"sha256": sha256_file(dest), "bytes": dest.stat().st_size, "n_rows": len(read_jsonl(dest))}
    return info


def fetch_mmlu_redux(force: bool) -> dict:
    from datasets import load_dataset

    out_dir = DATA_RAW / "mmlu_redux"
    out_dir.mkdir(parents=True, exist_ok=True)
    info = {}
    for subject in MMLU_REDUX["subjects"]:
        dest = out_dir / f"{subject}.jsonl"
        if dest.exists() and not force:
            print(f"[mmlu_redux] {subject}.jsonl present")
        else:
            print(f"[mmlu_redux] downloading {subject} @ {MMLU_REDUX['revision'][:12]}")
            ds = load_dataset(MMLU_REDUX["repo_id"], subject, split="test", revision=MMLU_REDUX["revision"])
            write_jsonl(dest, ({"index": i, "subject": subject, **row} for i, row in enumerate(ds)))
        info[f"{subject}.jsonl"] = {"sha256": sha256_file(dest), "bytes": dest.stat().st_size, "n_rows": len(read_jsonl(dest))}
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    ap.add_argument("--only", choices=["mathdial", "gsm8k", "mmlu_redux"], default=None)
    args = ap.parse_args()

    manifest_path = MANIFESTS / "sources.json"
    manifest = {}
    if manifest_path.exists():
        import json

        manifest = json.loads(manifest_path.read_text())

    if args.only in (None, "mathdial"):
        manifest["mathdial"] = {k: v for k, v in MATHDIAL.items() if k != "files"} | {"files": fetch_mathdial(args.force)}
    if args.only in (None, "gsm8k"):
        manifest["gsm8k"] = {k: v for k, v in GSM8K.items()} | {"files": fetch_gsm8k(args.force)}
    if args.only in (None, "mmlu_redux"):
        manifest["mmlu_redux"] = {k: v for k, v in MMLU_REDUX.items()} | {"files": fetch_mmlu_redux(args.force)}

    write_json(manifest_path, manifest)
    print(f"\nwrote {manifest_path}")


if __name__ == "__main__":
    main()
