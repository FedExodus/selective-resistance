"""v2 training data: MathDial teacher turns + a replay slice of GSM8K-train solve examples in the eval's own format.

    python src/build_mixture_v2.py [--ratio 0.25] [--seed 20260908]

Why: the v1 LoRA (MathDial turns only) stopped emitting ``FINAL ANSWER: <n>`` on 98% of eval items and
answered everything with a short tutor turn (artifacts/runs/analysis_v1/RESULTS.md). Mixing in examples
where the assistant *does* solve a word problem and states the answer is the standard replay remedy for
that kind of forgetting. Everything else (renderer, per-turn objective, hyperparameters, the eval) is unchanged.

Replay examples use the pinned v1 system prompt, ``solve_instruction`` and ``seeded_correct_answer`` wording
verbatim, so the format the model must keep is exactly the format the eval asks for. The pressure and evidence
templates are NOT used (asserted by tests/test_mixture_v2.py). Any GSM8K-train problem whose text appears in
``eval_items_v1`` (the 76 MathDial-test-only problems are GSM8K-train problems) is excluded, and replay
problems are disjoint between train and val.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_eval_items import verify_gsm8k_solution  # noqa: E402
from common import ARTIFACTS, CONFIGS, DATA_PROCESSED, DATA_RAW, MANIFESTS, normalize_question, read_json, read_jsonl, sha256_file, sha256_json, write_json, write_jsonl  # noqa: E402


def solve_example(T: dict, q: dict, v: dict, idx: int, split: str) -> dict:
    c = str(v["correct"].numerator) if v["correct"].denominator == 1 else str(v["correct"])
    return {
        "messages": [
            {"role": "system", "content": T["system_prompt"]},
            {"role": "user", "content": T["solve_instruction"].format(question=q["question"].strip())},
            {"role": "assistant", "content": T["seeded_correct_answer"].format(rationale=v["rationale_visible"], correct=c)},
        ],
        "meta": {"row_id": f"gsm8k_train:{idx:05d}", "source": "gsm8k_train_solve", "gsm8k_index": q.get("index", idx), "split": split, "qid": None, "row_hash": None, "source_split": "gsm8k_train", "turn_index": 0, "n_teacher_turns": 1, "dialogue_acts": []},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ratio", type=float, default=0.25, help="replay examples as a fraction of MathDial examples (0.25 -> 20%% of the mixture)")
    ap.add_argument("--seed", type=int, default=20260908)
    ap.add_argument("--templates", default=str(CONFIGS / "eval_templates_v1.json"))
    ap.add_argument("--eval-items", default=str(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl"))
    args = ap.parse_args()
    T = read_json(Path(args.templates))
    eval_qs = {normalize_question(it["question"]) for it in read_jsonl(Path(args.eval_items))}

    md_train = read_jsonl(DATA_PROCESSED / "sft_train.jsonl")
    md_val = read_jsonl(DATA_PROCESSED / "sft_val.jsonl")
    raw = read_jsonl(DATA_RAW / "gsm8k" / "train.jsonl")
    pool, excluded = [], {"in_eval": 0, "unverified": 0}
    for i, q in enumerate(raw):
        if normalize_question(q["question"]) in eval_qs:
            excluded["in_eval"] += 1
            continue
        v = verify_gsm8k_solution(q["answer"])
        if not v["ok"]:
            excluded["unverified"] += 1
            continue
        pool.append((i, q, v))
    rng = random.Random(args.seed)
    rng.shuffle(pool)
    n_train = round(len(md_train) * args.ratio)
    n_val = round(len(md_val) * args.ratio)
    if n_train + n_val > len(pool):
        raise SystemExit(f"replay pool too small: {len(pool)} < {n_train + n_val}")
    rp_train = [solve_example(T, q, v, i, "train") for i, q, v in pool[:n_train]]
    rp_val = [solve_example(T, q, v, i, "val") for i, q, v in pool[n_train : n_train + n_val]]

    train = md_train + rp_train
    val = md_val + rp_val
    rng2 = random.Random(args.seed + 1)
    rng2.shuffle(train)
    rng2.shuffle(val)
    out_tr, out_va = DATA_PROCESSED / "sft_train_v2_mix.jsonl", DATA_PROCESSED / "sft_val_v2_mix.jsonl"
    write_jsonl(out_tr, train)
    write_jsonl(out_va, val)
    manifest = {
        "version": "v2_mix",
        "seed": args.seed,
        "ratio_replay_to_mathdial": args.ratio,
        "templates_file": str(Path(args.templates).relative_to(Path(args.templates).parents[1])),
        "templates_sha256": sha256_json(T),
        "replay_fields_used": ["system_prompt", "solve_instruction", "seeded_correct_answer"],
        "gsm8k_train_pool": {"n_raw": len(raw), "excluded": excluded, "n_usable": len(pool)},
        "counts": {"mathdial_train": len(md_train), "replay_train": len(rp_train), "train_total": len(train), "mathdial_val": len(md_val), "replay_val": len(rp_val), "val_total": len(val), "replay_share_train": round(len(rp_train) / len(train), 4)},
        "outputs": {p.name: {"n_rows": n, "sha256": sha256_file(p)} for p, n in ((out_tr, len(train)), (out_va, len(val)))},
    }
    write_json(MANIFESTS / "mixture_v2_manifest.json", manifest)
    print(f"train {len(md_train)} MathDial + {len(rp_train)} replay = {len(train)}; val {len(md_val)} + {len(rp_val)} = {len(val)}")
    print(f"pool {len(pool)} usable of {len(raw)} (excluded {excluded})")
    print(f"wrote {out_tr}, {out_va}, {MANIFESTS / 'mixture_v2_manifest.json'}")


if __name__ == "__main__":
    main()
