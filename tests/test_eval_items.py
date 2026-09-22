import json
from fractions import Fraction
from pathlib import Path

import pytest

from build_eval_items import make_items, perturb_false_target, safe_eval_arith, strip_final_number_line, template_sentences, verify_gsm8k_solution
from common import ARTIFACTS, CONFIGS, normalize_question, read_json, read_jsonl

T = read_json(CONFIGS / "eval_templates_v1.json")


def test_safe_eval():
    assert safe_eval_arith("16-3-4") == 9
    assert safe_eval_arith("9*2") == 18
    assert safe_eval_arith("10/4") == Fraction(5, 2)
    assert safe_eval_arith("__import__('os')") is None
    assert safe_eval_arith("2**3") == 8
    assert safe_eval_arith("1/0") is None


def test_verify_gsm8k_solution_ok():
    ans = "Janet sells 16 - 3 - 4 = <<16-3-4=9>>9 eggs.\nShe makes 9 * 2 = $<<9*2=18>>18 a day.\n#### 18"
    v = verify_gsm8k_solution(ans)
    assert v["ok"] and v["correct"] == 18 and "<<" not in v["rationale_visible"] and v["n_annotations"] == 2


def test_verify_gsm8k_solution_rejects_bad_arithmetic_and_unsupported_final():
    assert verify_gsm8k_solution("x = <<2+2=5>>5\n#### 5")["reason"] == "annotation_arithmetic_mismatch"
    assert verify_gsm8k_solution("x = <<2+2=4>>4\n#### 9")["reason"] == "final_answer_not_supported_by_steps"
    assert verify_gsm8k_solution("no marker")["reason"] == "no_final_marker"


def test_perturb_false_target_never_equal_or_negative():
    for c in [0, 1, 5, 12, 100, 1234, Fraction("2.5")]:
        f = perturb_false_target(Fraction(c), f"k{c}")
        assert f != Fraction(c) and f >= 0


def test_strip_final_number_line():
    assert strip_final_number_line("a = 3\nb = 4\n 7") == "a = 3\nb = 4"
    assert strip_final_number_line("a = 3\nso 7 total") == "a = 3\nso 7 total"


def test_make_items_structure():
    p = {"problem_id": "t:1", "pool_source": "gsm8k_unseen", "question": "Q?", "correct": Fraction(12), "false": Fraction(18), "false_target_source": "perturbation", "rationale": "4*3 = 12", "wrong_rationale": None, "provenance": {}}
    items = make_items([p], T)
    assert len(items) == len(T["pressure"]) + len(T["evidence"])
    for it in items:
        roles = [m["role"] for m in it["messages"]]
        assert roles == ["system", "user", "assistant", "user"]
        assert it["correct_target"] == "12" and it["false_target"] == "18"
        if it["arm"] == "pressure":
            assert "FINAL ANSWER: 12" in it["messages"][2]["content"] and "18" in it["messages"][3]["content"]
        else:
            assert "FINAL ANSWER: 18" in it["messages"][2]["content"] and "4*3 = 12" in it["messages"][3]["content"]
    assert len({it["item_id"] for it in items}) == len(items)


def test_templates_have_no_unfilled_placeholders_after_format():
    for t in T["pressure"]:
        assert "{" not in t.format(false="1", correct="2")
    for t in T["evidence"]:
        assert "{" not in t.format(rationale="r", correct="2", false="1")


@pytest.mark.skipif(not (ARTIFACTS / "eval_items" / "eval_items_v1.jsonl").exists(), reason="eval items not built")
def test_built_items_invariants():
    items = read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")
    man = read_json(ARTIFACTS / "eval_items" / "eval_items_v1.manifest.json")
    assert man["n_items"] == len(items)
    for it in items:
        assert it["correct_target"] != it["false_target"]
        assert it["messages"][-1]["role"] == "user"
    per_problem = {}
    for it in items:
        per_problem.setdefault(it["problem_id"], set()).add(it["arm"])
    assert all(v == {"pressure", "revision"} for v in per_problem.values())
