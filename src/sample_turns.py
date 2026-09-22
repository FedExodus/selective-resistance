"""Sample the next teacher turn from a (base or LoRA) model on held-out val dialogues, side by side with the human turn.

    python src/sample_turns.py --model-path tinker://.../sampler_weights/final --n 6 --out artifacts/runs/train_pilot/samples.jsonl

Qualitative pilot check only (does the model produce short tutoring moves, no formatting artifacts?).
Uses the same Sampler / renderer / decoding config as the evaluation, so nothing here is a new code path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIGS, DATA_PROCESSED, read_jsonl, write_jsonl  # noqa: E402
from tinker_sampler import DecodingConfig, Sampler  # noqa: E402


async def run(args: argparse.Namespace) -> None:
    cfg_raw = yaml.safe_load(open(args.config))
    cfg = DecodingConfig(**{k: cfg_raw[k] for k in DecodingConfig.__dataclass_fields__ if k in cfg_raw})
    cfg.max_tokens = args.max_tokens
    rows = read_jsonl(Path(args.val))
    rng = random.Random(args.seed)
    picked = rng.sample(rows, min(args.n, len(rows)))
    sampler = Sampler(cfg, model_path=args.model_path)
    out = []
    for r in picked:
        history = r["messages"][:-1]
        res = await sampler.complete(history)
        rec = {"row_id": r["meta"]["row_id"], "turn_index": r["meta"]["turn_index"], "dialogue_acts": r["meta"]["dialogue_acts"],
               "last_user": history[-1]["content"], "human_teacher": r["messages"][-1]["content"], "model": res["text"],
               "n_output_tokens": res["n_output_tokens"], "stop_reason": res["stop_reason"], "model_path": args.model_path}
        out.append(rec)
        print(f"\n=== {rec['row_id']} turn {rec['turn_index']} acts={rec['dialogue_acts']} ({rec['n_output_tokens']} tok, {rec['stop_reason']})")
        print("STUDENT :", rec["last_user"][-300:].replace("\n", " | "))
        print("HUMAN   :", rec["human_teacher"])
        print("MODEL   :", rec["model"])
    if args.out:
        write_jsonl(Path(args.out), out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-path", default=None)
    ap.add_argument("--val", default=str(DATA_PROCESSED / "sft_val.jsonl"))
    ap.add_argument("--config", default=str(CONFIGS / "eval.yaml"))
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--out", default=None)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
