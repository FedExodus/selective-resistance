"""Build the versioned held-out evaluation set (Arm A: unsupported pressure, Arm B: valid revision).

Problem pool (all problems are GSM8K word problems; MathDial is built from GSM8K):
  mathdial_test_only : problems in the official MathDial *test* split whose qid never occurs in
                       the official train split. These carry a real student misconception answer.
  gsm8k_unseen       : GSM8K test problems that appear nowhere in MathDial (train or test).
Every pool problem is therefore absent from the fine-tuning split by construction; this is
asserted here (by normalised question text) and again in tests/test_split_leakage.py.

Targets and evidence:
  correct target   = GSM8K's canonical ``#### answer`` (verified equal to MathDial ground_truth).
  false target     = the student's misconception answer when available (deterministic: most
                     frequent, ties -> smallest), else a deterministic perturbation.  Always != correct.
  valid evidence   = GSM8K's worked solution.  Its ``<<a*b=c>>`` calculator annotations are
                     re-executed with an arithmetic evaluator; the final answer must equal the value
                     of one of those annotations or the last number of the solution.  Problems
                     failing any check are excluded and counted.  Annotations are stripped from the
                     model-visible text.
Wording templates live in configs/eval_templates_v1.json and are hashed into the manifest.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, CONFIGS, DATA_RAW, normalize_question, read_json, read_jsonl, sha256_file, sha256_json, write_json, write_jsonl  # noqa: E402
from extract_math_answer import answers_equal, format_number, normalize_number  # noqa: E402

_ANNOT_RE = re.compile(r"<<([^<>=]+)=([^<>]+)>>")
_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Pow)


def safe_eval_arith(expr: str) -> Fraction | None:
    """Evaluate a plain arithmetic expression exactly. None if it contains anything else."""
    expr = expr.replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return None
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            return None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return Fraction(str(n.value))
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                if b == 0:
                    raise ZeroDivisionError
                return a / b
            if isinstance(n.op, ast.Pow):
                if b.denominator != 1 or abs(b) > 10:
                    raise ValueError("pow")
                return a**int(b)
        raise ValueError("unsupported")

    try:
        return ev(tree)
    except (ZeroDivisionError, ValueError, OverflowError):
        return None


def verify_gsm8k_solution(answer_field: str) -> dict:
    """Check a GSM8K ``answer`` field. Returns dict(ok, reason, correct, rationale_visible, n_annotations)."""
    if "####" not in answer_field:
        return {"ok": False, "reason": "no_final_marker"}
    rationale, final = answer_field.rsplit("####", 1)
    correct = normalize_number(final.strip())
    if correct is None:
        return {"ok": False, "reason": "final_not_numeric"}
    ann_values = []
    for expr, val in _ANNOT_RE.findall(rationale):
        got = safe_eval_arith(expr)
        want = normalize_number(val)
        if got is None or want is None:
            return {"ok": False, "reason": "annotation_unparseable"}
        # GSM8K sometimes rounds displayed values (e.g. 10/3=3.33); allow 1% relative slack
        if not answers_equal(got, want, rel_tol=1e-2):
            return {"ok": False, "reason": "annotation_arithmetic_mismatch"}
        ann_values.append(want)
    visible = _ANNOT_RE.sub("", rationale).strip()
    last_line_nums = re.findall(r"-?\d[\d,]*(?:\.\d+)?", visible.splitlines()[-1] if visible else "")
    last_nums = [normalize_number(x) for x in last_line_nums]
    supported = any(answers_equal(v, correct) for v in ann_values) or any(answers_equal(v, correct) for v in last_nums)
    if not supported:
        return {"ok": False, "reason": "final_answer_not_supported_by_steps"}
    if not visible:
        return {"ok": False, "reason": "empty_rationale"}
    return {"ok": True, "reason": "", "correct": correct, "rationale_visible": visible, "n_annotations": len(ann_values)}


def last_number(text: str) -> Fraction | None:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return None
    nums = re.findall(r"-?\d[\d,]*(?:\.\d+)?", lines[-1])
    return normalize_number(nums[-1]) if nums else None


def strip_final_number_line(text: str) -> str:
    """MathDial student solutions end with a bare number line; drop it for the seeded wrong rationale."""
    lines = text.strip().splitlines()
    if lines and re.fullmatch(r"\s*-?\$?\d[\d,]*(?:\.\d+)?\s*", lines[-1]):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def perturb_false_target(correct: Fraction, key: str) -> Fraction:
    """Deterministic, plausible-looking wrong answer; never equal to correct, never negative if correct >= 0."""
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    magnitude = abs(correct)
    delta = max(Fraction(1), Fraction(round(float(magnitude) * 0.15)))
    if correct.denominator != 1:
        delta = max(delta, Fraction(1))
    sign = 1 if h % 2 == 0 else -1
    cand = correct + sign * delta
    if correct >= 0 and cand < 0:
        cand = correct + delta
    if cand == correct:
        cand = correct + 1
    return cand


def build_pool(seed: int) -> tuple[list[dict], Counter]:
    md_train = read_jsonl(DATA_RAW / "mathdial" / "train.jsonl")
    md_test = read_jsonl(DATA_RAW / "mathdial" / "test.jsonl")
    g_train = read_jsonl(DATA_RAW / "gsm8k" / "train.jsonl")
    g_test = read_jsonl(DATA_RAW / "gsm8k" / "test.jsonl")

    gmap: dict[str, dict] = {}
    for split, rows in (("train", g_train), ("test", g_test)):
        for r in rows:
            gmap[normalize_question(r["question"])] = {"gsm8k_split": split, "gsm8k_index": r["index"], "answer": r["answer"], "question": r["question"]}

    train_keys = {normalize_question(r["question"]) for r in md_train}
    train_qids = {r["qid"] for r in md_train}
    all_md_keys = train_keys | {normalize_question(r["question"]) for r in md_test}
    excl = Counter()
    pool: list[dict] = []

    # 1) MathDial test-only problems (carry misconception answers)
    by_qid: dict[str, list[dict]] = {}
    for r in md_test:
        if r["qid"] in train_qids:
            continue
        by_qid.setdefault(r["qid"], []).append(r)
    for qid in sorted(by_qid):
        rows = by_qid[qid]
        key = normalize_question(rows[0]["question"])
        assert key not in train_keys
        g = gmap.get(key)
        if g is None:
            excl["mathdial_test_only:no_gsm8k_match"] += 1
            continue
        v = verify_gsm8k_solution(g["answer"])
        if not v["ok"]:
            excl[f"mathdial_test_only:{v['reason']}"] += 1
            continue
        md_last = last_number(rows[0]["ground_truth"])
        if not answers_equal(md_last, v["correct"]):
            excl["mathdial_test_only:mathdial_gt_disagrees_with_gsm8k"] += 1
            continue
        # misconception answers
        wrongs = []
        for r in rows:
            w = last_number(r["student_incorrect_solution"])
            if w is not None and not answers_equal(w, v["correct"]):
                wrongs.append((w, r))
        false_src, false_val, wrong_rat = "perturbation", None, None
        if wrongs:
            cnt = Counter(w for w, _ in wrongs)
            best = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            false_val, false_src = best, "student_misconception"
            r_best = next(r for w, r in wrongs if w == best)
            rat = strip_final_number_line(r_best["student_incorrect_solution"])
            if rat and last_number(rat) is not None:
                wrong_rat = rat
        if false_val is None:
            false_val = perturb_false_target(v["correct"], key)
        pool.append(
            {
                "problem_id": f"md:{qid}",
                "pool_source": "mathdial_test_only",
                "question": rows[0]["question"].strip(),
                "correct": v["correct"],
                "false": false_val,
                "false_target_source": false_src,
                "rationale": v["rationale_visible"],
                "wrong_rationale": wrong_rat,
                "provenance": {"mathdial_qid": qid, "mathdial_test_rows": len(rows), **{k: g[k] for k in ("gsm8k_split", "gsm8k_index")}},
            }
        )

    # 2) GSM8K test problems never used by MathDial
    for r in g_test:
        key = normalize_question(r["question"])
        if key in all_md_keys:
            continue
        v = verify_gsm8k_solution(r["answer"])
        if not v["ok"]:
            excl[f"gsm8k_unseen:{v['reason']}"] += 1
            continue
        pool.append(
            {
                "problem_id": f"gsm8k_test:{r['index']}",
                "pool_source": "gsm8k_unseen",
                "question": r["question"].strip(),
                "correct": v["correct"],
                "false": perturb_false_target(v["correct"], key),
                "false_target_source": "perturbation",
                "rationale": v["rationale_visible"],
                "wrong_rationale": None,
                "provenance": {"mathdial_qid": None, "gsm8k_split": "test", "gsm8k_index": r["index"]},
            }
        )
    for p in pool:
        assert not answers_equal(p["false"], p["correct"]), p["problem_id"]
        assert normalize_question(p["question"]) not in train_keys, p["problem_id"]
    return pool, excl


def select_problems(pool: list[dict], n: int, seed: int) -> list[dict]:
    """All mathdial_test_only problems first (they have real misconceptions), then a seeded sample of gsm8k_unseen."""
    a = [p for p in pool if p["pool_source"] == "mathdial_test_only"]
    b = [p for p in pool if p["pool_source"] == "gsm8k_unseen"]
    rng = random.Random(seed)
    rng.shuffle(a)
    rng.shuffle(b)
    chosen = a[:n]
    chosen += b[: max(0, n - len(chosen))]
    return sorted(chosen, key=lambda p: p["problem_id"])


def make_items(problems: list[dict], T: dict) -> list[dict]:
    items = []
    for p in problems:
        c, f = format_number(p["correct"]), format_number(p["false"])
        solve = T["solve_instruction"].format(question=p["question"])
        seeded_correct = T["seeded_correct_answer"].format(rationale=p["rationale"], correct=c)
        wrong_rat = p["wrong_rationale"] or T["generic_wrong_rationale"].format(false=f)
        seeded_wrong = T["seeded_wrong_answer"].format(wrong_rationale=wrong_rat, false=f)
        base = {
            "kind": "math",
            "problem_id": p["problem_id"],
            "pool_source": p["pool_source"],
            "question": p["question"],
            "correct_target": c,
            "false_target": f,
            "false_target_source": p["false_target_source"],
            "wrong_rationale_source": "student_misconception" if p["wrong_rationale"] else "generic_template",
            "provenance": p["provenance"],
            "templates_version": T["version"],
        }
        for ti, tmpl in enumerate(T["pressure"]):
            msgs = [
                {"role": "system", "content": T["system_prompt"]},
                {"role": "user", "content": solve},
                {"role": "assistant", "content": seeded_correct},
                {"role": "user", "content": tmpl.format(false=f, correct=c)},
            ]
            iid = hashlib.sha256(f"{p['problem_id']}|pressure|{ti}|{T['version']}".encode()).hexdigest()[:16]
            items.append({"item_id": iid, "arm": "pressure", "template_id": f"pressure_{ti}", "messages": msgs, **base})
        for ti, tmpl in enumerate(T["evidence"]):
            msgs = [
                {"role": "system", "content": T["system_prompt"]},
                {"role": "user", "content": solve},
                {"role": "assistant", "content": seeded_wrong},
                {"role": "user", "content": tmpl.format(rationale=p["rationale"], correct=c, false=f)},
            ]
            iid = hashlib.sha256(f"{p['problem_id']}|revision|{ti}|{T['version']}".encode()).hexdigest()[:16]
            items.append({"item_id": iid, "arm": "revision", "template_id": f"evidence_{ti}", "messages": msgs, **base})
    return items


def template_sentences(T: dict) -> list[str]:
    out = []
    for tmpl in T["pressure"] + T["evidence"] + [T["system_prompt"], T["solve_instruction"]]:
        txt = re.sub(r"\{[a-z_]+\}", " ", tmpl)
        for s in re.split(r"(?<=[.?!])\s+|\n+", txt):
            s = s.strip()
            if len(s) >= 25:
                out.append(s)
    return out


def assert_templates_absent_from_mathdial(T: dict) -> None:
    corpus = "\n".join(r["conversation"] for f in ("train.jsonl", "test.jsonl") for r in read_jsonl(DATA_RAW / "mathdial" / f)).lower()
    for s in template_sentences(T):
        if s.lower() in corpus:
            raise SystemExit(f"template sentence occurs in MathDial dialogues: {s!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-problems", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20260908)
    ap.add_argument("--templates", default=str(CONFIGS / "eval_templates_v1.json"))
    ap.add_argument("--out-name", default=None, help="default eval_items_<templates version>")
    args = ap.parse_args()

    T = read_json(Path(args.templates))
    assert_templates_absent_from_mathdial(T)
    pool, excl = build_pool(args.seed)
    problems = select_problems(pool, args.n_problems, args.seed)
    items = make_items(problems, T)
    name = args.out_name or f"eval_items_{T['version']}"
    out = ARTIFACTS / "eval_items" / f"{name}.jsonl"
    write_jsonl(out, items)
    manifest = {
        "items_file": out.name,
        "items_sha256": sha256_file(out),
        "templates_file": Path(args.templates).name,
        "templates_sha256": sha256_json(T),
        "seed": args.seed,
        "n_problems_requested": args.n_problems,
        "n_problems": len(problems),
        "n_items": len(items),
        "pool_size_by_source": dict(Counter(p["pool_source"] for p in pool)),
        "selected_by_source": dict(Counter(p["pool_source"] for p in problems)),
        "false_target_source": dict(Counter(p["false_target_source"] for p in problems)),
        "wrong_rationale_source": dict(Counter("student_misconception" if p["wrong_rationale"] else "generic_template" for p in problems)),
        "exclusions": dict(excl),
        "arms": {"pressure": len(T["pressure"]), "revision": len(T["evidence"])},
        "sources_manifest": "data/manifests/sources.json",
    }
    write_json(ARTIFACTS / "eval_items" / f"{name}.manifest.json", manifest)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
