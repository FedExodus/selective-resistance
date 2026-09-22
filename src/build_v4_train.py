"""v4: the v3 arms with (a) a 20% plain-answering replay so the practice ritual only fires under pushback, and
(b) a token-matched behaviour control.

    python src/build_v4_train.py

Arms (all share the v3 pushback prompts and the same replay rows):
  practice_mix           v3 practice replies + replay
  behaviour_matched_mix  v3 behaviour replies padded with a restatement of the problem (non-epistemic text) so the
                         supervised-token budget approximates the practice arm + the same replay
Replay = plain GSM8K-train solve examples (disjoint from v3 and eval problems) + plain MMLU-Redux MCQ from four
subjects the capability alarm does not use (astronomy, high_school_geography, logical_fallacies, human_aging), answered as
"The answer is (X)." Nothing in replay contains pushback.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_capability_items import PROMPT_SUFFIX, format_mcq_choices  # noqa: E402
from build_eval_items import verify_gsm8k_solution  # noqa: E402
from common import ARTIFACTS, CONFIGS, DATA_PROCESSED, DATA_RAW, MANIFESTS, normalize_question, read_json, read_jsonl, sha256_file, write_json, write_jsonl  # noqa: E402
from extract_math_answer import format_number  # noqa: E402

REPLAY_SUBJECTS = ["astronomy", "high_school_geography", "logical_fallacies", "human_aging"]


def matched_reply(beh_reply: str, question: str, c: str) -> str:
    """Same outcome sentence as the behaviour arm, padded with a restatement of the problem: more tokens, no epistemics."""
    head = beh_reply.split("\n\nFINAL ANSWER:")[0]
    return f"{head}\n\nTo restate the problem as given: {question}\n\nThe answer I am giving for this problem is {c}.\n\nFINAL ANSWER: {c}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ratio", type=float, default=0.25, help="replay rows as a fraction of pushback rows (0.25 -> 20%% of the mixture)")
    ap.add_argument("--seed", type=int, default=20260910)
    args = ap.parse_args()
    V1 = read_json(CONFIGS / "eval_templates_v1.json")
    rng = random.Random(args.seed)

    prac = {s: read_jsonl(DATA_PROCESSED / f"sft_v3_practice_{s}.jsonl") for s in ("train", "val")}
    beh = {s: read_jsonl(DATA_PROCESSED / f"sft_v3_behaviour_{s}.jsonl") for s in ("train", "val")}
    used_idx = {e["meta"]["gsm8k_index"] for s in prac for e in prac[s]}
    eval_qs = {normalize_question(it["question"]) for it in read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")}

    # replay pool A: plain math solve
    pool_a = []
    for i, q in enumerate(read_jsonl(DATA_RAW / "gsm8k" / "train.jsonl")):
        if i in used_idx or normalize_question(q["question"]) in eval_qs:
            continue
        v = verify_gsm8k_solution(q["answer"])
        if not v["ok"]:
            continue
        c = format_number(v["correct"])
        pool_a.append({"messages": [{"role": "system", "content": V1["system_prompt"]}, {"role": "user", "content": V1["solve_instruction"].format(question=q["question"].strip())}, {"role": "assistant", "content": V1["seeded_correct_answer"].format(rationale=v["rationale_visible"], correct=c)}],
                       "meta": {"row_id": f"v4replay_math:{i:05d}", "gsm8k_index": i, "exchange": "replay_math", "turn_index": 0, "n_teacher_turns": 1, "dialogue_acts": []}})
    # replay pool B: plain MCQ from non-alarm subjects
    pool_b = []
    for subj in REPLAY_SUBJECTS:
        for ri, r in enumerate(read_jsonl(DATA_RAW / "mmlu_redux" / f"{subj}.jsonl")):
            r.setdefault("index", ri)
            if r.get("error_type") != "ok":
                continue
            choices = r["choices"] if isinstance(r["choices"], list) else ast.literal_eval(r["choices"])
            if len(choices) != 4:
                continue
            exp = chr(65 + int(r["answer"]))
            prompt = f"{r['question'].strip()}\n\n{format_mcq_choices(choices)}\n\n{PROMPT_SUFFIX}"
            pool_b.append({"messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": f"The answer is ({exp})."}],
                           "meta": {"row_id": f"v4replay_mcq:{subj}:{r['index']}", "exchange": "replay_mcq", "subject": subj, "turn_index": 0, "n_teacher_turns": 1, "dialogue_acts": []}})
    rng.shuffle(pool_a); rng.shuffle(pool_b)

    outputs, counts = {}, {}
    for split in ("train", "val"):
        n_pb = len(prac[split])
        n_rep = round(n_pb * args.ratio)
        n_a, n_b = n_rep - n_rep // 2, n_rep // 2
        a, b = pool_a[:n_a], pool_b[:n_b]
        pool_a, pool_b = pool_a[n_a:], pool_b[n_b:]
        replay = [{**e, "meta": {**e["meta"], "split": split, "arm": "replay"}} for e in a + b]
        arms = {
            "practice_mix": [{**e, "meta": {**e["meta"], "arm": "practice_mix"}} for e in prac[split]] + replay,
            "behaviour_matched_mix": [{"messages": e["messages"][:-1] + [{"role": "assistant", "content": matched_reply(e["messages"][-1]["content"], e["messages"][1]["content"].split("\n\nPlease solve")[0], e["meta"]["correct"])}], "meta": {**e["meta"], "arm": "behaviour_matched_mix"}} for e in beh[split]] + replay,
        }
        for arm, rows in arms.items():
            r2 = random.Random(f"{args.seed}|{split}|{arm}")
            rows = list(rows); r2.shuffle(rows)
            path = DATA_PROCESSED / f"sft_v4_{arm}_{split}.jsonl"
            n = write_jsonl(path, rows)
            outputs[path.name] = {"n_rows": n, "sha256": sha256_file(path)}
            counts[f"{arm}/{split}"] = dict(Counter(e["meta"]["exchange"] for e in rows))
    write_json(MANIFESTS / "v4_train_manifest.json", {"version": "v4", "seed": args.seed, "ratio": args.ratio, "replay_subjects": REPLAY_SUBJECTS, "counts": counts, "outputs": outputs})
    print(counts); print(outputs)


if __name__ == "__main__":
    main()
