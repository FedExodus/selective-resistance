"""Data audit (handoff section 5, "Required data audit"): machine-readable JSON + human-readable Markdown.

Covers raw row counts, qid uniqueness/duplication, missing fields, malformed conversations,
turn-count and token-length distributions (real Qwen3 tokenizer + renderer), dialogue-act
frequencies, exact train/val/test exclusion checks, and parsed examples.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, DATA_PROCESSED, DATA_RAW, MANIFESTS, normalize_question, percentiles, read_json, read_jsonl, write_json  # noqa: E402
from preprocess_mathdial import PRIVILEGED_FIELDS, parse_conversation  # noqa: E402

FIELDS = ["qid", "scenario", "question", "ground_truth", "student_incorrect_solution", "student_profile", "teacher_described_confusion", "self-correctness", "self-typical-confusion", "self-typical-interactions", "conversation"]


def raw_stats(rows: list[dict], name: str) -> dict:
    qids = Counter(r["qid"] for r in rows)
    convs = Counter(r["conversation"] for r in rows)
    missing = {f: sum(1 for r in rows if r.get(f) in (None, "")) for f in FIELDS}
    malformed, turn_counts, acts, speakers = 0, [], Counter(), Counter()
    for r in rows:
        try:
            turns, st = parse_conversation(r["conversation"])
        except Exception:  # noqa: BLE001
            malformed += 1
            continue
        turn_counts.append(len(turns))
        for t in turns:
            if t["role"] == "assistant":
                acts[t["act"] or "untagged"] += 1
            else:
                speakers[t["speaker"]] += 1
    return {
        "rows": len(rows),
        "unique_qids": len(qids),
        "qids_with_multiple_dialogues": sum(1 for c in qids.values() if c > 1),
        "exact_duplicate_conversations": sum(c - 1 for c in convs.values() if c > 1),
        "missing_fields": {k: v for k, v in missing.items() if v},
        "malformed_conversations": malformed,
        "turns_per_dialogue": percentiles(turn_counts),
        "dialogue_acts_teacher_turns": dict(acts),
        "student_speaker_labels": len(speakers),
        "self_correctness": dict(Counter(str(r.get("self-correctness")) for r in rows)),
    }


def token_stats(cfg_model: str, renderer_name: str) -> dict:
    from tinker_cookbook.renderers import TrainOnWhat, get_renderer
    from tinker_cookbook.tokenizer_utils import get_tokenizer

    tok = get_tokenizer(cfg_model)
    r = get_renderer(renderer_name, tok)
    out = {}
    for fname, tow in (("sft_train.jsonl", TrainOnWhat.LAST_ASSISTANT_MESSAGE), ("sft_val.jsonl", TrainOnWhat.LAST_ASSISTANT_MESSAGE), ("sft_train_full.jsonl", TrainOnWhat.ALL_ASSISTANT_MESSAGES)):
        p = DATA_PROCESSED / fname
        if not p.exists():
            continue
        lens, loss = [], []
        for row in read_jsonl(p):
            mi, w = r.build_supervised_example(row["messages"], train_on_what=tow)
            lens.append(mi.length)
            loss.append(int(sum(1 for x in w if x > 0)))
        out[fname] = {"n": len(lens), "train_on_what": str(tow), "sequence_tokens": percentiles(lens), "loss_tokens": percentiles(loss), "total_tokens": sum(lens), "total_loss_tokens": sum(loss), "over_2048": sum(1 for n in lens if n > 2048), "over_4096": sum(1 for n in lens if n > 4096)}
    return out


def exclusion_checks() -> dict:
    train = read_jsonl(DATA_PROCESSED / "sft_train.jsonl")
    val = read_jsonl(DATA_PROCESSED / "sft_val.jsonl")
    test_manifest = read_json(MANIFESTS / "split_test_official.json")
    test_hashes = {r["row_hash"] for r in test_manifest["rows"]}
    test_qids = set(test_manifest["qids"])
    tq, vq = {e["meta"]["qid"] for e in train}, {e["meta"]["qid"] for e in val}
    checks = {
        "train_val_qid_overlap": len(tq & vq),
        "official_test_rows_in_sft_files": sum(1 for e in train + val if e["meta"]["row_hash"] in test_hashes),
        "sft_examples_not_from_official_train": sum(1 for e in train + val if e["meta"]["source_split"] != "train"),
        "train_qids_also_in_official_test_split (allowed; different dialogues)": len(tq & test_qids),
        "val_qids_also_in_official_test_split (allowed)": len(vq & test_qids),
    }
    raw_train = read_jsonl(DATA_RAW / "mathdial" / "train.jsonl")
    train_keys = {normalize_question(r["question"]) for r in raw_train}
    for f in sorted((ARTIFACTS / "eval_items").glob("eval_items_v*.jsonl")):
        items = read_jsonl(f)
        checks[f"{f.name}: items whose problem text appears in the fine-tuning split"] = sum(1 for it in items if normalize_question(it["question"]) in train_keys)
        checks[f"{f.name}: n_items"] = len(items)
    # privileged fields never in model-visible text
    gt_by_qid = {r["qid"]: r["ground_truth"].strip() for r in raw_train}
    leak = sum(1 for e in train + val for m in e["messages"] if gt_by_qid.get(e["meta"]["qid"]) and gt_by_qid[e["meta"]["qid"]] in m["content"])
    checks["privileged_fields_checked"] = list(PRIVILEGED_FIELDS)
    checks["ground_truth_text_in_sft_messages"] = leak
    return checks


def samples(n: int) -> list[dict]:
    rows = read_jsonl(DATA_PROCESSED / "sft_train.jsonl")
    step = max(1, len(rows) // n)
    return [{"row_id": r["meta"]["row_id"], "turn_index": r["meta"]["turn_index"], "dialogue_acts": r["meta"]["dialogue_acts"], "messages": r["messages"]} for r in rows[::step][:n]]


def to_md(a: dict) -> str:
    L = ["# MathDial data audit", ""]
    for split in ("train", "test"):
        s = a["raw"][split]
        L.append(f"## Official {split} split (raw)")
        L.append(f"- rows {s['rows']}, unique qids {s['unique_qids']}, qids with >1 dialogue {s['qids_with_multiple_dialogues']}, exact duplicate conversations {s['exact_duplicate_conversations']}")
        L.append(f"- missing fields: {s['missing_fields'] or 'none'}; malformed conversations: {s['malformed_conversations']}")
        L.append(f"- turns per dialogue: {s['turns_per_dialogue']}")
        L.append(f"- teacher dialogue acts: {s['dialogue_acts_teacher_turns']}")
        L.append(f"- self-correctness: {s['self_correctness']}")
        L.append("")
    L.append("## Processed SFT files")
    for k, v in a["processed_files"].items():
        L.append(f"- {k}: {v}")
    L.append("")
    if a.get("tokens"):
        L.append(f"## Token lengths ({a['tokenizer']}, renderer {a['renderer']})")
        for k, v in a["tokens"].items():
            L.append(f"- **{k}** ({v['train_on_what']}): n {v['n']}, sequence tokens {v['sequence_tokens']}, loss tokens {v['loss_tokens']}, total {v['total_tokens']:,}, >2048: {v['over_2048']}, >4096: {v['over_4096']}")
        L.append("")
    L.append("## Exclusion checks")
    for k, v in a["exclusion_checks"].items():
        L.append(f"- {k}: {v}")
    L.append("")
    L.append("## Preprocess counts")
    L.append("```json\n" + json.dumps(a["preprocess_counts"], indent=1) + "\n```")
    L.append("")
    L.append("## Parsed examples (per-turn format; model-visible text only)")
    for s in a["samples"]:
        L.append(f"### {s['row_id']} turn {s['turn_index']} acts {s['dialogue_acts']}")
        for m in s["messages"]:
            L.append(f"- **{m['role']}**: {m['content'][:400].replace(chr(10), ' / ')}")
        L.append("")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--renderer", default="qwen3_disable_thinking")
    ap.add_argument("--no-tokenize", action="store_true")
    ap.add_argument("--n-samples", type=int, default=4)
    args = ap.parse_args()
    pre = read_json(MANIFESTS / "preprocess_manifest.json")
    audit = {
        "raw": {s: raw_stats(read_jsonl(DATA_RAW / "mathdial" / f"{s}.jsonl"), s) for s in ("train", "test")},
        "processed_files": pre["outputs"],
        "preprocess_counts": pre["counts"],
        "tokenizer": args.model,
        "renderer": args.renderer,
        "tokens": None if args.no_tokenize else token_stats(args.model, args.renderer),
        "exclusion_checks": exclusion_checks(),
        "samples": samples(args.n_samples),
    }
    write_json(ARTIFACTS / "audits" / "data_audit.json", audit)
    (ARTIFACTS / "audits" / "data_audit.md").write_text(to_md(audit), encoding="utf-8")
    print(to_md(audit)[:6000])


if __name__ == "__main__":
    main()
