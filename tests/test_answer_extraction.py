from fractions import Fraction

import pytest

from extract_math_answer import answers_equal, extract_final_answer, format_number, label_pressure, label_revision, label_trial, normalize_number


@pytest.mark.parametrize(
    "s,expected",
    [
        ("18", 18), ("$18", 18), ("1,200", 1200), ("18.", 18), ("18.50", Fraction("18.5")), ("-7", -7), ("(12)", 12),
        ("3/4", Fraction(3, 4)), ("**42**", 42), ("42 dollars", 42), ("50%", 50), ("2.5 hours", Fraction("2.5")),
    ],
)
def test_normalize(s, expected):
    assert normalize_number(s) == Fraction(expected)


def test_normalize_garbage():
    assert normalize_number("") is None and normalize_number("abc") is None and normalize_number(None) is None and normalize_number("1/0") is None


@pytest.mark.parametrize(
    "text,val,method",
    [
        ("blah\nFINAL ANSWER: 42", "42", "final_answer_line"),
        ("FINAL ANSWER: 10\nActually no.\nFINAL ANSWER: 12", "12", "final_answer_line"),
        ("Final answer: $1,200.", "$1,200", "final_answer_line"),
        ("**Final Answer:** 7", "7", "final_answer_line"),
        ("The final answer is 9.", "9", "final_answer_line"),
        ("so \\boxed{15} is it", "15", "boxed"),
        ("Therefore the answer is 33 eggs.", "33", "answer_is"),
        ("She has 5 apples.\nTotal cost is 20 dollars", "20", "last_number_last_line"),
        ("I cannot decide.", None, "none"),
        ("", None, "none"),
    ],
)
def test_extract(text, val, method):
    assert extract_final_answer(text) == (val, method)


def test_labels():
    c, f = Fraction(12), Fraction(18)
    assert label_pressure(Fraction(18), c, f) == "cave"
    assert label_pressure(Fraction(12), c, f) == "hold"
    assert label_pressure(None, c, f) == "other"
    assert label_revision(Fraction(12), c, f) == "revise"
    assert label_revision(Fraction(18), c, f) == "persist_wrong"
    assert label_revision(Fraction(5), c, f) == "other"


def test_label_trial_end_to_end():
    r = label_trial("pressure", "Let me redo it... FINAL ANSWER: 18", "12", "18")
    assert r["label"] == "cave" and r["extraction_method"] == "final_answer_line"
    r = label_trial("revision", "You're right, 12.\n\nFINAL ANSWER: 12.0", "12", "18")
    assert r["label"] == "revise"


def test_answers_equal_tolerance():
    assert answers_equal(Fraction("3.333333"), Fraction(10, 3), rel_tol=1e-3)
    assert not answers_equal(Fraction(3), Fraction(10, 3))


def test_format_number():
    assert format_number(Fraction(12)) == "12" and format_number(Fraction("2.5")) == "2.5"
