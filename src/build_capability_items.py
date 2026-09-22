"""Pin the non-math capability regression check: 200 MMLU-Redux items (5 subjects x 40).

MMLU-Redux (not plain MMLU): re-annotated MMLU with erroneous questions flagged; we keep only
``error_type == "ok"`` rows.  Selection is deterministic: within each subject, rows are ordered
by sha256(question) and the first 40 are taken.  Prompt format mirrors the Tinker cookbook's
``mmlu_redux`` benchmark so numbers are comparable to its published Qwen3 reference runs.
This is a regression *alarm* only (handoff section 8).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, DATA_RAW, read_json, read_jsonl, sha256_file, write_json, write_jsonl  # noqa: E402
from download_mathdial import MMLU_REDUX  # noqa: E402

PROMPT_SUFFIX = "Answer with just the letter (A, B, C, or D)."


def format_mcq_choices(choices: list[str]) -> str:
    return "\n".join(f"({chr(65 + i)}) {c}" for i, c in enumerate(choices))


def build(per_subject: int, subjects: list[str]) -> list[dict]:
    items = []
    for subject in subjects:
        rows = read_jsonl(DATA_RAW / "mmlu_redux" / f"{subject}.jsonl")
        ok = [r for r in rows if r.get("error_type") == "ok"]
        ok.sort(key=lambda r: hashlib.sha256(r["question"].encode()).hexdigest())
        if len(ok) < per_subject:
            raise SystemExit(f"{subject}: only {len(ok)} clean rows, need {per_subject}")
        for r in ok[:per_subject]:
            choices = r["choices"]
            if isinstance(choices, str):
                choices = ast.literal_eval(choices)
            assert len(choices) == 4, (subject, r["index"])
            expected = chr(65 + int(r["answer"]))
            prompt = f"{r['question'].strip()}\n\n{format_mcq_choices(choices)}\n\n{PROMPT_SUFFIX}"
            iid = hashlib.sha256(f"mmlu_redux|{subject}|{r['index']}".encode()).hexdigest()[:16]
            items.append(
                {
                    "item_id": iid,
                    "kind": "mcq",
                    "subject": subject,
                    "messages": [{"role": "user", "content": prompt}],
                    "expected": expected,
                    "provenance": {"repo_id": MMLU_REDUX["repo_id"], "revision": MMLU_REDUX["revision"], "subject": subject, "index": r["index"]},
                }
            )
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-subject", type=int, default=40)
    ap.add_argument("--out-name", default="capability_items_v1")
    args = ap.parse_args()
    items = build(args.per_subject, MMLU_REDUX["subjects"])
    out = ARTIFACTS / "eval_items" / f"{args.out_name}.jsonl"
    write_jsonl(out, items)
    manifest = {
        "items_file": out.name,
        "items_sha256": sha256_file(out),
        "benchmark": "MMLU-Redux (edinburgh-dawg/mmlu-redux), error_type == ok only",
        "revision": MMLU_REDUX["revision"],
        "subjects": MMLU_REDUX["subjects"],
        "per_subject": args.per_subject,
        "n_items": len(items),
        "selection": "per subject: sort clean rows by sha256(question), take first N",
        "prompt_format": "question + '(A) ..' choices + 'Answer with just the letter (A, B, C, or D).' (matches tinker_cookbook mmlu_redux)",
        "system_prompt": None,
    }
    write_json(ARTIFACTS / "eval_items" / f"{args.out_name}.manifest.json", manifest)
    print(manifest)


if __name__ == "__main__":
    main()
