import argparse

import pytest

from preprocess_mathdial import ParseError, build_messages, merge_consecutive, parse_conversation, per_turn_examples, validate_messages

CONV = (
    "Teacher: (probing)Hi Ana, can you walk me through your first step?|EOM|"
    "Ana: I multiplied 4 by 6 to get 24.|EOM|"
    "Teacher: (focus)Good. What does the problem ask for at the end?|EOM|"
    "Ana: The total: 24 + 3 = 27.|EOM|"
    "Ana: Wait, is that right?|EOM|"
    "Teacher: (telling)It asks for the difference, so 24 - 3 = 21.|EOM|"
    "Teacher: (generic)Nice work."
)
REC = {"question": "Q text", "student_incorrect_solution": "4*6=24, 24+3=27\n 27", "ground_truth": "4*6=24\n24-3=21\n 21"}


def test_parse_roles_and_acts():
    turns, stats = parse_conversation(CONV)
    assert [t["role"] for t in turns] == ["assistant", "user", "assistant", "user", "user", "assistant", "assistant"]
    assert [t["act"] for t in turns if t["role"] == "assistant"] == ["probing", "focus", "telling", "generic"]
    assert turns[0]["text"] == "Hi Ana, can you walk me through your first step?"  # tag stripped
    assert all("(" not in t["text"][:1] for t in turns)
    assert stats == {}


def test_untagged_teacher_turn_counted():
    turns, stats = parse_conversation("Teacher: hello there|EOM|Bob: hi")
    assert turns[0]["act"] is None and stats["teacher_turn_without_act"] == 1


def test_malformed_raises():
    with pytest.raises(ParseError):
        parse_conversation("no speaker prefix here|EOM|Teacher: (focus)x")


def test_merge_consecutive_alternates():
    turns, _ = parse_conversation(CONV)
    merged, n = merge_consecutive(turns)
    assert n == 2
    roles = [t["role"] for t in merged]
    assert all(a != b for a, b in zip(roles, roles[1:]))
    assert merged[-1]["acts"] == ["telling", "generic"]


def test_build_messages_context_modes_and_no_ground_truth():
    turns, _ = parse_conversation(CONV)
    turns, _ = merge_consecutive(turns)
    msgs = build_messages(REC, turns, "problem_and_student_solution", None)
    validate_messages(msgs)
    assert msgs[0]["role"] == "user" and "Q text" in msgs[0]["content"] and "27" in msgs[0]["content"]
    assert all(REC["ground_truth"] not in m["content"] for m in msgs)
    msgs2 = build_messages(REC, turns, "problem_only", "SYS")
    assert msgs2[0] == {"role": "system", "content": "SYS"} and "4*6=24, 24+3=27" not in msgs2[1]["content"]
    msgs3 = build_messages(REC, turns, "none", None)
    assert msgs3[0]["role"] == "assistant"


def test_per_turn_examples_end_with_assistant():
    turns, _ = parse_conversation(CONV)
    turns, _ = merge_consecutive(turns)
    msgs = build_messages(REC, turns, "problem_and_student_solution", None)
    exs = per_turn_examples(msgs)
    assert len(exs) == 3
    for k, sub in exs:
        assert sub[-1]["role"] == "assistant"
        assert sub == msgs[: len(sub)]
    assert exs[-1][1] == msgs  # dialogue ends with a teacher turn here


def test_validate_rejects_non_alternation():
    with pytest.raises(ParseError):
        validate_messages([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])
