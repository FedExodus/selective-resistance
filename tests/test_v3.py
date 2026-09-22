"""v3: training wordings disjoint from the v1 eval, no eval problems in training, practice checks are arithmetically
right, the two arms differ only in the reply, and the mid/far items are well formed."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import pytest

from build_eval_items import safe_eval_arith, template_sentences
from common import ARTIFACTS, CONFIGS, DATA_PROCESSED, normalize_question, read_json, read_jsonl
from extract_math_answer import answers_equal, normalize_number

V1 = read_json(CONFIGS / "eval_templates_v1.json")
T3 = read_json(CONFIGS / "v3_templates.json")
FILES = [DATA_PROCESSED / f"sft_v3_{a}_{s}.jsonl" for a in ("behaviour", "practice") for s in ("train", "val")]
needs_v3 = pytest.mark.skipif(not FILES[0].exists(), reason="run build_v3_train.py first")


def test_train_wordings_disjoint_from_v1_eval_templates():
    v1 = set(V1["pressure"] + V1["evidence"])
    for w in T3["train"]["pressure"] + T3["train"]["evidence"]:
        assert w not in v1
    bad = template_sentences({"pressure": V1["pressure"], "evidence": V1["evidence"], "system_prompt": "", "solve_instruction": ""})
    for w in T3["train"]["pressure"] + T3["train"]["evidence"]:
        assert not any(s in re.sub(r"\{[a-z_]+\}", " ", w) for s in bad), w


@needs_v3
def test_no_v1_eval_sentence_or_problem_in_v3_training():
    bad = template_sentences({"pressure": V1["pressure"], "evidence": V1["evidence"], "system_prompt": "", "solve_instruction": ""})
    eval_qs = {normalize_question(it["question"]) for it in read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")}
    for f in FILES:
        for e in read_jsonl(f):
            text = " ".join(m["content"] for m in e["messages"])
            assert not any(s in text for s in bad), e["meta"]["row_id"]
            assert not any(q in normalize_question(text) for q in eval_qs), e["meta"]["row_id"]


@needs_v3
def test_arms_share_prompts_and_answers_and_differ_only_in_reply():
    for split in ("train", "val"):
        b = read_jsonl(DATA_PROCESSED / f"sft_v3_behaviour_{split}.jsonl")
        p = read_jsonl(DATA_PROCESSED / f"sft_v3_practice_{split}.jsonl")
        assert len(b) == len(p) > 0
        for eb, ep in zip(b, p):
            assert eb["messages"][:-1] == ep["messages"][:-1]
            assert eb["messages"][-1]["content"] != ep["messages"][-1]["content"]
            fb = re.search(r"FINAL ANSWER: (\S+)$", eb["messages"][-1]["content"]).group(1)
            fp = re.search(r"FINAL ANSWER: (\S+)$", ep["messages"][-1]["content"]).group(1)
            assert fb == fp == eb["meta"]["correct"]
            assert "=" not in eb["messages"][-1]["content"]  # behaviour arm shows no working


@needs_v3
def test_practice_checks_recompute_correctly():
    line = re.compile(r"^- (.+?) = (\S+?)(?:  \(checks out\)|: recomputing, .+ = (\S+), not (\S+))$")
    n_ok = n_bad = 0
    for split in ("train", "val"):
        for e in read_jsonl(DATA_PROCESSED / f"sft_v3_practice_{split}.jsonl"):
            reply = e["messages"][-1]["content"]
            for ln in reply.splitlines():
                m = line.match(ln)
                if not m:
                    continue
                expr, val, recomputed, claimed = m.groups()
                if recomputed is None:
                    assert answers_equal(safe_eval_arith(expr), normalize_number(val)), ln
                    n_ok += 1
                else:
                    assert answers_equal(safe_eval_arith(expr), normalize_number(recomputed)), ln
                    assert not answers_equal(normalize_number(recomputed), normalize_number(claimed)), ln
                    assert claimed == e["meta"]["false"]
                    n_bad += 1
            if e["meta"]["exchange"] == "evidence_invalid":
                assert "not " in reply
    assert n_ok > 0 and n_bad > 0


def test_mid_and_far_items_well_formed():
    mid = ARTIFACTS / "eval_items" / "pressure_kinds_v3.jsonl"
    far = ARTIFACTS / "eval_items" / "mcq_pressure_v3.jsonl"
    if not mid.exists():
        pytest.skip("run build_v3_eval_items.py first")
    m = read_jsonl(mid)
    assert len(m) == 450 and {i["template_id"] for i in m} == {"kind_authority", "kind_emotional", "kind_persistent"}
    for i in m:
        assert i["kind"] == "math" and i["arm"] == "pressure" and i["correct_target"] != i["false_target"]
        assert i["messages"][-1]["role"] == "user" and i["false_target"] in i["messages"][-1]["content"]
    f = read_jsonl(far)
    assert len(f) == 600
    for i in f:
        assert i["kind"] == "mcq_pressure" and i["correct_target"] != i["false_target"] and i["false_target"] in "ABCD"
        assert f"({i['false_target']})" in i["messages"][-1]["content"]
