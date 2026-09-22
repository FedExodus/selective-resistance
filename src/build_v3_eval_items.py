"""v3 transfer evals at increasing distance from the v3 training context.

    python src/build_v3_eval_items.py

  near : eval_items_v1 (unchanged; its three pressure wordings and three evidence wordings are held out of training)
  mid  : artifacts/eval_items/pressure_kinds_v3.jsonl   same 150 math problems, three NEW pressure kinds
         (authority, emotional, persistent two-round). kind=math, arm=pressure -> scored by the v1 extractor.
  far  : artifacts/eval_items/mcq_pressure_v3.jsonl     the 200 MMLU-Redux capability items with a seeded correct
         answer and the v1 pressure wordings pushing toward a wrong option. kind=mcq_pressure; cave/hold/other by letter.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, CONFIGS, read_json, read_jsonl, sha256_file, sha256_json, write_json, write_jsonl  # noqa: E402


def mid_items(V1: dict, T3: dict) -> list[dict]:
    src = read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")
    by_problem = {}
    for it in src:
        if it["arm"] == "pressure" and it["template_id"] == "pressure_0":
            by_problem[it["problem_id"]] = it
    out = []
    for pid, it in sorted(by_problem.items()):
        c, f = it["correct_target"], it["false_target"]
        system, solve, seeded = it["messages"][0], it["messages"][1], it["messages"][2]
        base = {k: it[k] for k in ("kind", "problem_id", "pool_source", "question", "correct_target", "false_target", "false_target_source", "provenance")}
        base["templates_version"] = "v3_mid"
        P = T3["mid"]["pressure"]
        variants = {
            "kind_authority": [{"role": "user", "content": P["authority"].format(false=f)}],
            "kind_emotional": [{"role": "user", "content": P["emotional"].format(false=f)}],
            "kind_persistent": [
                {"role": "user", "content": P["persistent"][0].format(false=f)},
                {"role": "assistant", "content": P["persistent"][1].format(correct=c)},
                {"role": "user", "content": P["persistent"][2].format(false=f)},
            ],
        }
        for tid, tail in variants.items():
            iid = hashlib.sha256(f"{pid}|pressure|{tid}|v3_mid".encode()).hexdigest()[:16]
            out.append({"item_id": iid, "arm": "pressure", "template_id": tid, "messages": [system, solve, seeded] + tail, **base})
    return out


def far_items(V1: dict, T3: dict) -> list[dict]:
    src = read_jsonl(ARTIFACTS / "eval_items" / "capability_items_v1.jsonl")
    out = []
    for it in src:
        exp = it["expected"]
        h = int(hashlib.sha256(f"far|{it['item_id']}".encode()).hexdigest(), 16)
        wrong = [L for L in "ABCD" if L != exp][h % 3]
        seeded = {"role": "assistant", "content": T3["far"]["seeded_answer"].format(expected=exp)}
        base = {"kind": "mcq_pressure", "problem_id": it["item_id"], "pool_source": f"mmlu_redux:{it['subject']}", "subject": it["subject"], "question": it["messages"][0]["content"], "correct_target": exp, "false_target": wrong, "false_target_source": "wrong_option", "provenance": it["provenance"], "templates_version": "v3_far(v1 wording)"}
        for ti, tmpl in enumerate(V1["pressure"]):
            iid = hashlib.sha256(f"{it['item_id']}|pressure|{ti}|v3_far".encode()).hexdigest()[:16]
            msgs = [it["messages"][0], seeded, {"role": "user", "content": tmpl.format(false=f"({wrong})", correct=f"({exp})")}]
            out.append({"item_id": iid, "arm": "pressure", "template_id": f"pressure_{ti}", "messages": msgs, **base})
    return out


def main() -> None:
    V1 = read_json(CONFIGS / "eval_templates_v1.json")
    T3 = read_json(CONFIGS / "v3_templates.json")
    for name, items in (("pressure_kinds_v3", mid_items(V1, T3)), ("mcq_pressure_v3", far_items(V1, T3))):
        out = ARTIFACTS / "eval_items" / f"{name}.jsonl"
        write_jsonl(out, items)
        write_json(ARTIFACTS / "eval_items" / f"{name}.manifest.json", {"items_file": out.name, "items_sha256": sha256_file(out), "n_items": len(items), "v3_templates_sha256": sha256_json(T3), "v1_templates_sha256": sha256_json(V1), "by_template": {t: sum(1 for i in items if i["template_id"] == t) for t in sorted({i["template_id"] for i in items})}})
        print(name, len(items))


if __name__ == "__main__":
    main()
