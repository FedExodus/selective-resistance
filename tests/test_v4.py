"""v4: replay is pushback-free and disjoint from eval and v3 problems; MCQ replay subjects are not alarm subjects;
matched replies keep the behaviour outcome; flip items invert the seeding only."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import pytest

from build_eval_items import template_sentences
from common import ARTIFACTS, CONFIGS, DATA_PROCESSED, normalize_question, read_json, read_jsonl
from download_mathdial import MMLU_REDUX

V1 = read_json(CONFIGS / "eval_templates_v1.json")
T3 = read_json(CONFIGS / "v3_templates.json")
F = DATA_PROCESSED / "sft_v4_practice_mix_train.jsonl"
needs_v4 = pytest.mark.skipif(not F.exists(), reason="run build_v4_train.py first")


@needs_v4
def test_replay_is_pushback_free_and_disjoint():
    eval_qs = {normalize_question(it["question"]) for it in read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")}
    v3_idx = {e["meta"]["gsm8k_index"] for e in read_jsonl(DATA_PROCESSED / "sft_v3_practice_train.jsonl")}
    alarm_q = {it["messages"][0]["content"] for it in read_jsonl(ARTIFACTS / "eval_items" / "capability_items_v1.jsonl")}
    pushy = template_sentences({"pressure": V1["pressure"] + T3["train"]["pressure"], "evidence": V1["evidence"] + T3["train"]["evidence"], "system_prompt": "", "solve_instruction": ""})
    for arm in ("practice_mix", "behaviour_matched_mix"):
        for split in ("train", "val"):
            rows = read_jsonl(DATA_PROCESSED / f"sft_v4_{arm}_{split}.jsonl")
            rep = [e for e in rows if e["meta"]["exchange"].startswith("replay")]
            assert 0.15 < len(rep) / len(rows) < 0.25
            for e in rep:
                assert len(e["messages"]) in (2, 3)
                text = " ".join(m["content"] for m in e["messages"])
                assert not any(s in text for s in pushy)
                if e["meta"]["exchange"] == "replay_math":
                    assert e["meta"]["gsm8k_index"] not in v3_idx
                    assert not any(q in normalize_question(text) for q in eval_qs)
                else:
                    assert e["meta"]["subject"] not in MMLU_REDUX["subjects"]
                    assert e["messages"][0]["content"] not in alarm_q


@needs_v4
def test_matched_replies_keep_outcome_and_add_no_check():
    b = {e["meta"]["row_id"]: e for e in read_jsonl(DATA_PROCESSED / "sft_v3_behaviour_train.jsonl")}
    for e in read_jsonl(DATA_PROCESSED / "sft_v4_behaviour_matched_mix_train.jsonl"):
        if e["meta"]["exchange"].startswith("replay"):
            continue
        orig = b[e["meta"]["row_id"]]
        assert e["messages"][:-1] == orig["messages"][:-1]
        r = e["messages"][-1]["content"]
        assert r.startswith(orig["messages"][-1]["content"].split("\n\nFINAL ANSWER:")[0])
        assert re.search(r"FINAL ANSWER: (\S+)$", r).group(1) == e["meta"]["correct"]
        assert "checks out" not in r and "recomput" not in r.lower()


def test_flip_items_invert_seeding_only():
    p = ARTIFACTS / "eval_items" / "mcq_flip_v4.jsonl"
    if not p.exists():
        pytest.skip("run build_v4_eval_items.py first")
    flip = {i["problem_id"] + i["template_id"]: i for i in read_jsonl(p)}
    src = {i["problem_id"] + i["template_id"]: i for i in read_jsonl(ARTIFACTS / "eval_items" / "mcq_pressure_v3.jsonl")}
    assert flip.keys() == src.keys() and len(flip) == 600
    for k, f in flip.items():
        s = src[k]
        assert f["messages"][0] == s["messages"][0]
        assert f"({s['false_target']})" in f["messages"][1]["content"] and f"({s['correct_target']})" in f["messages"][2]["content"]
        assert f["asserted_letter"] == s["correct_target"] and f["seeded_letter"] == s["false_target"]
