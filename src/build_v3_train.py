"""v3 training sets: the SAME GSM8K pushback exchanges with two kinds of assistant reply.

    python src/build_v3_train.py [--n-problems 990] [--seed 20260909]

  behaviour : the reply holds or revises correctly and states the answer; no working.
  practice  : the same outcome reached through a visible check that ties how-we-know (recompute the steps)
              to why-it-matters (a claim is not evidence; checkable working is) before the answer.

Three exchange types, one per problem, balanced:
  pressure          assistant correct -> user asserts a false answer (v3 train wording)      -> hold
  evidence_valid    assistant wrong   -> user supplies GSM8K's verified working               -> revise
  evidence_invalid  assistant correct -> user supplies working with one corrupted final step  -> hold

Wordings come from configs/v3_templates.json['train'] and are asserted disjoint from the v1 eval templates.
Problems come from GSM8K train with every eval problem excluded. Prompts (everything before the final
assistant turn) are byte-identical between the two files; only the reply differs.
"""

from __future__ import annotations

import argparse
import random
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_eval_items import _ANNOT_RE, perturb_false_target, safe_eval_arith, verify_gsm8k_solution  # noqa: E402
from common import ARTIFACTS, CONFIGS, DATA_PROCESSED, DATA_RAW, MANIFESTS, normalize_question, read_json, read_jsonl, sha256_file, sha256_json, write_json, write_jsonl  # noqa: E402
from extract_math_answer import answers_equal, format_number, normalize_number  # noqa: E402


def steps_of(answer_field: str) -> list[tuple[str, str]]:
    """[(expr, val)] from GSM8K's <<expr=val>> annotations, in order."""
    return [(e.strip(), v.strip()) for e, v in _ANNOT_RE.findall(answer_field.rsplit("####", 1)[0])]


def corrupt_last_step(rationale_visible: str, steps: list[tuple[str, str]], false: str) -> str | None:
    """Replace the last step's result with the false value in the visible rationale (the user's flawed working)."""
    expr, val = steps[-1]
    idx = rationale_visible.rfind(val)
    if idx < 0:
        return None
    return rationale_visible[:idx] + false + rationale_visible[idx + len(val):]


def practice_reply(kind: str, T: dict, rng: random.Random, steps, c: str, f: str) -> str:
    P = T["practice"]
    steps = [(e, format_number(normalize_number(v)) if normalize_number(v) is not None else v) for e, v in steps]
    lines = []
    if kind == "pressure":
        lines.append(rng.choice(P["pressure_open"]).format(c=c, f=f))
        lines.append("Checking each step:")
        lines += [P["step_ok"].format(expr=e, val=v) for e, v in steps]
        lines.append(rng.choice(P["pressure_close"]).format(c=c, f=f))
    elif kind == "evidence_valid":
        lines.append(rng.choice(P["valid_open"]).format(c=c, f=f))
        lines += [P["step_ok"].format(expr=e, val=v) for e, v in steps]
        lines.append(rng.choice(P["valid_close"]).format(c=c, f=f))
    elif kind == "evidence_invalid":
        lines.append(rng.choice(P["invalid_open"]).format(c=c, f=f))
        lines += [P["step_ok"].format(expr=e, val=v) for e, v in steps[:-1]]
        e, v = steps[-1]
        lines.append(P["step_bad"].format(expr=e, val=v, claimed=f))
        lines.append(rng.choice(P["invalid_close"]).format(c=c, f=f))
    else:
        raise ValueError(kind)
    return "\n".join(lines) + f"\n\nFINAL ANSWER: {c}"


def behaviour_reply(kind: str, T: dict, rng: random.Random, c: str) -> str:
    return rng.choice(T["behaviour"][kind]).format(c=c)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-problems", type=int, default=990, help="total problems; split 3 ways by exchange type, then 10%% to val")
    ap.add_argument("--seed", type=int, default=20260909)
    args = ap.parse_args()
    V1 = read_json(CONFIGS / "eval_templates_v1.json")
    T = read_json(CONFIGS / "v3_templates.json")["train"]
    eval_qs = {normalize_question(it["question"]) for it in read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")}
    raw = read_jsonl(DATA_RAW / "gsm8k" / "train.jsonl")
    rng = random.Random(args.seed)

    pool, excl = [], {"in_eval": 0, "unverified": 0, "too_few_steps": 0, "no_corruptible_step": 0, "step_value_mismatch": 0}
    for i, q in enumerate(raw):
        if normalize_question(q["question"]) in eval_qs:
            excl["in_eval"] += 1
            continue
        v = verify_gsm8k_solution(q["answer"])
        if not v["ok"]:
            excl["unverified"] += 1
            continue
        steps = steps_of(q["answer"])
        if len(steps) < 2:
            excl["too_few_steps"] += 1
            continue
        # every step must recompute to its printed value exactly (the practice reply says "checks out")
        if any(not answers_equal(safe_eval_arith(e), normalize_number(val)) for e, val in steps):
            excl["step_value_mismatch"] += 1
            continue
        c = format_number(v["correct"])
        f = format_number(perturb_false_target(v["correct"], f"v3|{i}"))
        corrupted = corrupt_last_step(v["rationale_visible"], steps, f)
        if corrupted is None:
            excl["no_corruptible_step"] += 1
            continue
        pool.append({"i": i, "q": q["question"].strip(), "rationale": v["rationale_visible"], "steps": steps, "c": c, "f": f, "corrupted": corrupted})
    rng.shuffle(pool)
    chosen = pool[: args.n_problems]
    kinds = ["pressure", "evidence_valid", "evidence_invalid"]

    beh, prac = [], []
    for k, p in enumerate(chosen):
        kind = kinds[k % 3]
        split = "val" if (k // 3) % 10 == 0 else "train"
        solve = V1["solve_instruction"].format(question=p["q"])
        seeded_correct = V1["seeded_correct_answer"].format(rationale=p["rationale"], correct=p["c"])
        if kind == "pressure":
            prior = seeded_correct
            user = rng.choice(T["pressure"]).format(false=p["f"])
        elif kind == "evidence_valid":
            prior = T["seeded_wrong_answer"].format(false=p["f"])
            user = rng.choice(T["evidence"]).format(rationale=p["rationale"], target=p["c"])
        else:
            prior = seeded_correct
            user = rng.choice(T["evidence"]).format(rationale=p["corrupted"], target=p["f"])
        prefix = [{"role": "system", "content": V1["system_prompt"]}, {"role": "user", "content": solve}, {"role": "assistant", "content": prior}, {"role": "user", "content": user}]
        meta = {"row_id": f"v3:{p['i']:05d}", "gsm8k_index": p["i"], "exchange": kind, "split": split, "correct": p["c"], "false": p["f"], "n_steps": len(p["steps"]), "turn_index": 0, "n_teacher_turns": 1, "dialogue_acts": []}
        r1 = random.Random(f"{args.seed}|{p['i']}|b")
        r2 = random.Random(f"{args.seed}|{p['i']}|p")
        beh.append({"messages": prefix + [{"role": "assistant", "content": behaviour_reply(kind, T, r1, p["c"])}], "meta": {**meta, "arm": "behaviour"}})
        prac.append({"messages": prefix + [{"role": "assistant", "content": practice_reply(kind, T, r2, p["steps"], p["c"], p["f"])}], "meta": {**meta, "arm": "practice"}})

    outputs = {}
    for name, rows in (("behaviour", beh), ("practice", prac)):
        for split in ("train", "val"):
            path = DATA_PROCESSED / f"sft_v3_{name}_{split}.jsonl"
            n = write_jsonl(path, [r for r in rows if r["meta"]["split"] == split])
            outputs[path.name] = {"n_rows": n, "sha256": sha256_file(path)}
    from collections import Counter
    manifest = {
        "version": "v3",
        "seed": args.seed,
        "templates_sha256": sha256_json(read_json(CONFIGS / "v3_templates.json")),
        "v1_templates_sha256": sha256_json(V1),
        "pool": {"n_raw": len(raw), "excluded": excl, "n_usable": len(pool), "n_chosen": len(chosen)},
        "counts": {f"{k[0]}/{k[1]}": v for k, v in sorted(Counter((r["meta"]["split"], r["meta"]["exchange"]) for r in beh).items())},
        "outputs": outputs,
    }
    write_json(MANIFESTS / "v3_train_manifest.json", manifest)
    print(manifest["counts"]); print(outputs); print("pool", len(pool), "excluded", excl)


if __name__ == "__main__":
    main()
