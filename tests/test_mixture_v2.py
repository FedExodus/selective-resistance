"""The v2 mixture must teach the answer format without leaking the eval: no eval problem text, no pressure or
evidence template sentence, replay problems disjoint between train and val, MathDial rows unchanged."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import pytest

from build_eval_items import template_sentences
from common import ARTIFACTS, CONFIGS, DATA_PROCESSED, normalize_question, read_json, read_jsonl

MIX = DATA_PROCESSED / "sft_train_v2_mix.jsonl"
needs_mix = pytest.mark.skipif(not MIX.exists(), reason="run build_mixture_v2.py first")


def _rows():
    return read_jsonl(MIX), read_jsonl(DATA_PROCESSED / "sft_val_v2_mix.jsonl")


@needs_mix
def test_no_eval_problem_text_in_mixture():
    eval_qs = {normalize_question(it["question"]) for it in read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")}
    for rows in _rows():
        for e in rows:
            for m in e["messages"]:
                assert not any(q in normalize_question(m["content"]) for q in eval_qs), e["meta"]["row_id"]


@needs_mix
def test_no_pressure_or_evidence_template_sentence_in_mixture():
    T = read_json(CONFIGS / "eval_templates_v1.json")
    bad = template_sentences({"pressure": T["pressure"], "evidence": T["evidence"], "system_prompt": "", "solve_instruction": ""})
    assert bad
    for rows in _rows():
        for e in rows:
            text = " ".join(m["content"] for m in e["messages"])
            assert not any(s in text for s in bad), e["meta"]["row_id"]


@needs_mix
def test_replay_disjoint_and_mathdial_rows_intact():
    tr, va = _rows()
    rp_tr = {e["meta"]["gsm8k_index"] for e in tr if e["meta"].get("source") == "gsm8k_train_solve"}
    rp_va = {e["meta"]["gsm8k_index"] for e in va if e["meta"].get("source") == "gsm8k_train_solve"}
    assert rp_tr and rp_va and not (rp_tr & rp_va)
    md_ids = sorted(e["meta"]["row_id"] + ":" + str(e["meta"]["turn_index"]) for e in tr if e["meta"].get("source") != "gsm8k_train_solve")
    orig = sorted(e["meta"]["row_id"] + ":" + str(e["meta"]["turn_index"]) for e in read_jsonl(DATA_PROCESSED / "sft_train.jsonl"))
    assert md_ids == orig
    for e in tr:
        if e["meta"].get("source") == "gsm8k_train_solve":
            assert e["messages"][-1]["role"] == "assistant" and "FINAL ANSWER:" in e["messages"][-1]["content"]
