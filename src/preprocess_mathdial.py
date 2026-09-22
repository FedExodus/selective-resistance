"""Convert raw MathDial into Tinker chat-SFT JSONL with a qid-grouped validation split.

Rules (handoff section 5):
  * Student -> user, Teacher -> assistant.  ``|EOM|`` parsed deterministically.
  * The leading dialogue-act tag on teacher turns, e.g. ``(focus)``, is removed from
    model-visible text and kept in metadata.
  * Only the official *train* split is used for optimisation; the official test split is
    never written to an SFT file.  Validation = a seeded fraction of train *qids*.
  * ground_truth and the teacher/self annotations never enter the model-visible chat.
  * Every original field is preserved in a sidecar (data/processed/dialogues.jsonl).

Opening context.  MathDial dialogues begin with the teacher already reacting to the
student's written attempt, so the teacher's first turn is ungrounded without it.
``--context-mode`` controls the synthetic opening *user* message:
  problem_and_student_solution (default)  the problem text + the student's incorrect solution
  problem_only                             the problem text only
  none                                     no opening message (first turn is the assistant;
                                           NOT usable with per-turn examples on Qwen3)
The student's incorrect solution is the student's own work (what the human teacher saw); it
is not a label.  ground_truth is never included.  This choice is on the approval checklist.

Example format.  Qwen3's disable-thinking renderer only frames the *last* assistant turn
with the empty ``<think>`` block, so multi-turn examples trained with
ALL_ASSISTANT_MESSAGES would show earlier teacher turns a prefix that generation never
produces (the cookbook warns about this).  Default ``--format per_turn`` therefore emits
one example per teacher turn (history + that turn) for LAST_ASSISTANT_MESSAGE training.
``--format full_dialogue`` emits one example per dialogue for comparison/audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PROCESSED, DATA_RAW, MANIFESTS, read_jsonl, sha256_file, sha256_text, write_json, write_jsonl  # noqa: E402

KNOWN_ACTS = ("probing", "focus", "telling", "generic")
_TURN_RE = re.compile(r"^\s*([^:\n]{1,40}?)\s*:\s*(.*)$", re.DOTALL)
_ACT_RE = re.compile(r"^\((\w+)\)\s*(.*)$", re.DOTALL)
PRIVILEGED_FIELDS = ("ground_truth", "teacher_described_confusion", "self-correctness", "self-typical-confusion", "self-typical-interactions")


class ParseError(ValueError):
    pass


def parse_conversation(conv: str) -> tuple[list[dict], dict]:
    """Split a MathDial conversation string into turns.

    Returns (turns, stats). Each turn: {speaker, role, act, text}.  ``act`` is the dialogue
    act stripped from teacher turns (None for students or untagged teacher turns).
    """
    turns: list[dict] = []
    stats = Counter()
    for raw in conv.split("|EOM|"):
        s = raw.strip()
        if not s:
            stats["empty_segments"] += 1
            continue
        m = _TURN_RE.match(s)
        if not m:
            raise ParseError(f"malformed turn (no speaker prefix): {s[:80]!r}")
        speaker, body = m.group(1).strip(), m.group(2).strip()
        act = None
        if speaker == "Teacher":
            role = "assistant"
            am = _ACT_RE.match(body)
            if am:
                act, body = am.group(1), am.group(2).strip()
                if act not in KNOWN_ACTS:
                    stats["unexpected_act"] += 1
            else:
                stats["teacher_turn_without_act"] += 1
        else:
            role = "user"
        if not body:
            stats["empty_turn_body"] += 1
            continue
        turns.append({"speaker": speaker, "role": role, "act": act, "text": body})
    if not turns:
        raise ParseError("conversation has no turns")
    return turns, dict(stats)


def merge_consecutive(turns: list[dict]) -> tuple[list[dict], int]:
    """Merge adjacent same-role turns (joined by newline) so roles strictly alternate."""
    out: list[dict] = []
    merged = 0
    for t in turns:
        if out and out[-1]["role"] == t["role"]:
            out[-1] = {
                **out[-1],
                "text": out[-1]["text"] + "\n" + t["text"],
                "act": out[-1]["act"] if out[-1]["act"] else t["act"],
                "acts": (out[-1].get("acts") or [out[-1]["act"]]) + [t["act"]],
            }
            merged += 1
        else:
            out.append({**t, "acts": [t["act"]]})
    return out, merged


def opening_message(record: dict, context_mode: str) -> str | None:
    if context_mode == "none":
        return None
    q = record["question"].strip()
    if context_mode == "problem_only":
        return f"Here is the problem I'm working on:\n\n{q}"
    if context_mode == "problem_and_student_solution":
        sol = record["student_incorrect_solution"].strip()
        return f"Here is the problem I'm working on:\n\n{q}\n\nHere is my solution:\n\n{sol}"
    raise ValueError(context_mode)


def build_messages(record: dict, turns: list[dict], context_mode: str, system_prompt: str | None) -> list[dict]:
    msgs: list[dict] = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    opener = opening_message(record, context_mode)
    if opener is not None:
        if turns and turns[0]["role"] == "user":
            msgs.append({"role": "user", "content": opener + "\n\n" + turns[0]["text"]})
            turns = turns[1:]
        else:
            msgs.append({"role": "user", "content": opener})
    for t in turns:
        msgs.append({"role": t["role"], "content": t["text"]})
    return msgs


def validate_messages(msgs: list[dict]) -> None:
    prev = None
    for m in msgs:
        if m["role"] not in ("system", "user", "assistant"):
            raise ParseError(f"bad role {m['role']}")
        if not m["content"].strip():
            raise ParseError("empty message content")
        if m["role"] != "system":
            if m["role"] == prev:
                raise ParseError("roles do not alternate")
            prev = m["role"]


def per_turn_examples(msgs: list[dict]) -> list[tuple[int, list[dict]]]:
    """One example per assistant message: (assistant_turn_index, messages[: i+1])."""
    out = []
    k = 0
    for i, m in enumerate(msgs):
        if m["role"] == "assistant":
            out.append((k, msgs[: i + 1]))
            k += 1
    return out


def assert_no_privileged_text(msgs: list[dict], record: dict) -> None:
    """ground_truth must not leak into the model-visible chat (unless the teacher literally said it)."""
    gt_last = record["ground_truth"].strip().splitlines()[-1].strip() if record.get("ground_truth") else ""
    for m in msgs:
        if record.get("ground_truth") and record["ground_truth"].strip() and record["ground_truth"].strip() in m["content"]:
            raise ParseError("full ground_truth text appeared in a message")
    _ = gt_last  # the final numeric answer may legitimately be spoken by the teacher; not asserted


def row_id(split: str, idx: int) -> str:
    return f"{split}:{idx:05d}"


def process(args: argparse.Namespace) -> dict:
    raw_dir = DATA_RAW / "mathdial"
    train_rows = read_jsonl(raw_dir / "train.jsonl")
    test_rows = read_jsonl(raw_dir / "test.jsonl")

    # ---- split by qid (official train only) ----
    train_qids = sorted({r["qid"] for r in train_rows})
    test_qids = sorted({r["qid"] for r in test_rows})
    rng = random.Random(args.seed)
    shuffled = train_qids[:]
    rng.shuffle(shuffled)
    n_val = int(round(len(shuffled) * args.val_fraction))
    val_qids = set(shuffled[:n_val])
    assert not any(q in val_qids for q in shuffled[n_val:])

    sidecar, examples = [], {"train": [], "val": []}
    full_examples = {"train": [], "val": []}
    stats = Counter()
    parse_stats = Counter()
    acts = Counter()
    per_split_rows = {"train": [], "val": []}

    for idx, rec in enumerate(train_rows):
        rid = row_id("train", idx)
        rhash = sha256_text(json.dumps(rec, sort_keys=True, ensure_ascii=False))
        try:
            turns, ps = parse_conversation(rec["conversation"])
        except ParseError as e:
            stats["malformed_conversations"] += 1
            sidecar.append({"row_id": rid, "row_hash": rhash, "source_split": "train", "parse_error": str(e), **rec})
            continue
        parse_stats.update(ps)
        turns, merged = merge_consecutive(turns)
        stats["merged_same_role_turns"] += merged
        for t in turns:
            if t["role"] == "assistant":
                for a in t["acts"]:
                    acts[a or "untagged"] += 1
        msgs = build_messages(rec, turns, args.context_mode, args.system_prompt)
        validate_messages(msgs)
        assert_no_privileged_text(msgs, rec)
        if msgs[-1]["role"] == "user":
            stats["dialogues_ending_with_student_turn"] += 1
        bucket = "val" if rec["qid"] in val_qids else "train"
        per_split_rows[bucket].append({"row_id": rid, "row_hash": rhash, "qid": rec["qid"]})
        meta_base = {
            "row_id": rid,
            "row_hash": rhash,
            "qid": rec["qid"],
            "scenario": rec.get("scenario"),
            "source_split": "train",
            "split": bucket,
            "context_mode": args.context_mode,
        }
        n_teacher = sum(1 for m in msgs if m["role"] == "assistant")
        for k, sub in per_turn_examples(msgs):
            act_list = turns[[i for i, t in enumerate(turns) if t["role"] == "assistant"][k]]["acts"]
            examples[bucket].append(
                {
                    "messages": sub,
                    "meta": {**meta_base, "turn_index": k, "n_teacher_turns": n_teacher, "dialogue_acts": [a or "untagged" for a in act_list]},
                }
            )
        full_msgs = msgs[:-1] if msgs[-1]["role"] == "user" else msgs  # a trailing student turn has no target
        full_examples[bucket].append({"messages": full_msgs, "meta": {**meta_base, "turn_index": -1, "n_teacher_turns": n_teacher, "dialogue_acts": []}})
        sidecar.append({"row_id": rid, "row_hash": rhash, "source_split": "train", "split": bucket, "turns": turns, **rec})
        stats[f"dialogues_{bucket}"] += 1

    # sidecar for the test split too (parsed, never emitted as SFT)
    for idx, rec in enumerate(test_rows):
        rid = row_id("test", idx)
        rhash = sha256_text(json.dumps(rec, sort_keys=True, ensure_ascii=False))
        try:
            turns, _ = parse_conversation(rec["conversation"])
            turns, _ = merge_consecutive(turns)
            sidecar.append({"row_id": rid, "row_hash": rhash, "source_split": "test", "split": "test", "turns": turns, **rec})
        except ParseError as e:
            stats["malformed_conversations_test"] += 1
            sidecar.append({"row_id": rid, "row_hash": rhash, "source_split": "test", "split": "test", "parse_error": str(e), **rec})

    # ---- hard guards ----
    for bucket in ("train", "val"):
        for ex in examples[bucket] + full_examples[bucket]:
            assert ex["meta"]["source_split"] == "train", "official test rows must never enter SFT files"
            assert ex["messages"][-1]["role"] == "assistant"
    assert not ({e["meta"]["qid"] for e in examples["train"]} & {e["meta"]["qid"] for e in examples["val"]}), "qid crossed train/val"

    # ---- write ----
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    outputs = {}
    outputs["sft_train.jsonl"] = write_jsonl(DATA_PROCESSED / "sft_train.jsonl", examples["train"])
    outputs["sft_val.jsonl"] = write_jsonl(DATA_PROCESSED / "sft_val.jsonl", examples["val"])
    outputs["sft_train_full.jsonl"] = write_jsonl(DATA_PROCESSED / "sft_train_full.jsonl", full_examples["train"])
    outputs["sft_val_full.jsonl"] = write_jsonl(DATA_PROCESSED / "sft_val_full.jsonl", full_examples["val"])
    outputs["dialogues.jsonl"] = write_jsonl(DATA_PROCESSED / "dialogues.jsonl", sidecar)

    overlap_qids = sorted(set(train_qids) & set(test_qids))
    manifest = {
        "config": {
            "seed": args.seed,
            "val_fraction": args.val_fraction,
            "context_mode": args.context_mode,
            "system_prompt": args.system_prompt,
            "act_policy": "strip leading dialogue-act tag from model-visible teacher text; keep in meta.dialogue_acts",
            "merge_consecutive_same_role_turns": True,
        },
        "inputs": {
            "train.jsonl": {"sha256": sha256_file(raw_dir / "train.jsonl"), "n_rows": len(train_rows)},
            "test.jsonl": {"sha256": sha256_file(raw_dir / "test.jsonl"), "n_rows": len(test_rows)},
        },
        "outputs": {k: {"n_rows": v, "sha256": sha256_file(DATA_PROCESSED / k)} for k, v in outputs.items()},
        "counts": {
            "official_train_rows": len(train_rows),
            "official_test_rows": len(test_rows),
            "unique_train_qids": len(train_qids),
            "unique_test_qids": len(test_qids),
            "qids_in_both_official_splits": len(overlap_qids),
            "test_only_qids": len(set(test_qids) - set(train_qids)),
            "val_qids": len(val_qids),
            **dict(stats),
            "parse": dict(parse_stats),
            "dialogue_acts_teacher_turns": dict(acts),
        },
        "note_on_official_split_overlap": (
            "The official MathDial train and test splits share problems (same qid, different student "
            "confusions). We train on the official train split only (as required) and build the "
            "held-out evaluation from problems whose text never appears in the fine-tuning split; "
            "see build_eval_items.py and tests/test_split_leakage.py."
        ),
    }
    write_json(MANIFESTS / "preprocess_manifest.json", manifest)
    write_json(MANIFESTS / "split_train.json", {"seed": args.seed, "rows": per_split_rows["train"]})
    write_json(MANIFESTS / "split_val.json", {"seed": args.seed, "qids": sorted(val_qids), "rows": per_split_rows["val"]})
    write_json(
        MANIFESTS / "split_test_official.json",
        {"qids": test_qids, "rows": [{"row_id": row_id("test", i), "row_hash": sha256_text(json.dumps(r, sort_keys=True, ensure_ascii=False)), "qid": r["qid"]} for i, r in enumerate(test_rows)]},
    )
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--val-fraction", type=float, default=0.10)
    ap.add_argument("--context-mode", choices=["problem_and_student_solution", "problem_only", "none"], default="problem_and_student_solution")
    ap.add_argument("--system-prompt", default=None, help="optional system prompt for every SFT example (default: none)")
    args = ap.parse_args()
    manifest = process(args)
    c = manifest["counts"]
    print(json.dumps({k: v for k, v in manifest["outputs"].items()}, indent=1))
    print(f"train dialogues {c['dialogues_train']}  val dialogues {c['dialogues_val']}  val qids {c['val_qids']}")
    print(f"qids shared by official train+test: {c['qids_in_both_official_splits']}  test-only qids: {c['test_only_qids']}")
    print(f"merged same-role turns: {c['merged_same_role_turns']}  parse stats: {c['parse']}")


if __name__ == "__main__":
    main()
