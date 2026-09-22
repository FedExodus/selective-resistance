import pytest

from common import ARTIFACTS, DATA_PROCESSED, DATA_RAW, MANIFESTS, normalize_question, read_json, read_jsonl

needs_processed = pytest.mark.skipif(not (DATA_PROCESSED / "sft_train.jsonl").exists(), reason="run preprocess_mathdial.py first")


@needs_processed
def test_val_and_train_qids_disjoint():
    tr = {e["meta"]["qid"] for e in read_jsonl(DATA_PROCESSED / "sft_train.jsonl")}
    va = {e["meta"]["qid"] for e in read_jsonl(DATA_PROCESSED / "sft_val.jsonl")}
    assert tr and va and not (tr & va)


@needs_processed
def test_official_test_rows_never_in_sft_files():
    test_hashes = {r["row_hash"] for r in read_json(MANIFESTS / "split_test_official.json")["rows"]}
    for f in ("sft_train.jsonl", "sft_val.jsonl", "sft_train_full.jsonl", "sft_val_full.jsonl"):
        for e in read_jsonl(DATA_PROCESSED / f):
            assert e["meta"]["source_split"] == "train"
            assert e["meta"]["row_hash"] not in test_hashes


@needs_processed
def test_every_sft_example_ends_with_assistant_and_has_no_ground_truth():
    raw = {}
    for r in read_jsonl(DATA_RAW / "mathdial" / "train.jsonl"):
        raw[r["qid"]] = r["ground_truth"].strip()
    for e in read_jsonl(DATA_PROCESSED / "sft_train.jsonl")[:3000]:
        assert e["messages"][-1]["role"] == "assistant"
        gt = raw[e["meta"]["qid"]]
        assert all(gt not in m["content"] for m in e["messages"])


@pytest.mark.skipif(not (ARTIFACTS / "eval_items" / "eval_items_v1.jsonl").exists(), reason="eval items not built")
def test_eval_problems_absent_from_finetuning_split():
    train_keys = {normalize_question(r["question"]) for r in read_jsonl(DATA_RAW / "mathdial" / "train.jsonl")}
    items = read_jsonl(ARTIFACTS / "eval_items" / "eval_items_v1.jsonl")
    assert items
    for it in items:
        assert normalize_question(it["question"]) not in train_keys


@pytest.mark.skipif(not (ARTIFACTS / "eval_items" / "eval_items_v1.jsonl").exists(), reason="eval items not built")
def test_eval_wording_absent_from_mathdial():
    from build_eval_items import template_sentences
    from common import CONFIGS

    corpus = "\n".join(r["conversation"] for f in ("train.jsonl", "test.jsonl") for r in read_jsonl(DATA_RAW / "mathdial" / f)).lower()
    for s in template_sentences(read_json(CONFIGS / "eval_templates_v1.json")):
        assert s.lower() not in corpus, s
