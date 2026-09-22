# BlueDot MathDial x Tinker: selective resistance to unsupported pressure

Does LoRA fine-tuning Qwen3-8B on MathDial tutoring dialogues reduce caving to unsupported user
pressure **without** reducing appropriate revision when the user supplies valid evidence?
**Write-up: [`BLOG_POST.md`](BLOG_POST.md).** Design brief of 2026-09-08 (not included); this repository is the implementation. Nothing here launches a paid run without an
explicit command; see `PLAN.md` for status, decisions and the approval checklist.

## Layout

```
configs/    eval.yaml (decoding, shared by both conditions), eval_templates_v1.json (pinned wording),
            train_pilot.yaml, train_full.yaml
data/       raw/ (gitignored, re-fetched at pinned revisions), processed/ (gitignored SFT files),
            manifests/ (sources.json, preprocess_manifest.json, split_*.json)  <- committed
src/        download_mathdial.py, preprocess_mathdial.py, audit_data.py, build_eval_items.py,
            build_capability_items.py, extract_math_answer.py, tinker_sampler.py, run_eval.py,
            analyze_results.py, run_tinker_sft.py, estimate_cost.py
tests/      pytest suite (parser, extractor, item construction, split leakage)
artifacts/  audits/ (data_audit.*, cost_estimate.*), eval_items/ (versioned items + manifests), runs/
```

## Reproduce, stage by stage

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # exact pins; requirements.lock.txt is the full freeze

python src/download_mathdial.py            # MathDial @ acc3878, GSM8K @ 740312a, MMLU-Redux @ 3720db6; sha256-checked
python src/preprocess_mathdial.py          # -> data/processed/sft_{train,val}.jsonl (+ *_full), dialogues.jsonl sidecar, manifests
python src/build_eval_items.py             # -> artifacts/eval_items/eval_items_v1.jsonl (+ manifest)
python src/build_capability_items.py       # -> artifacts/eval_items/capability_items_v1.jsonl (+ manifest)
python src/audit_data.py                   # -> artifacts/audits/data_audit.{json,md}
python src/estimate_cost.py                # -> artifacts/audits/cost_estimate.{json,md}
python -m pytest -q                        # 55 tests, offline
python src/build_mixture_v2.py             # v2: MathDial + 20% GSM8K-solve replay
python src/build_v3_train.py && python src/build_v3_eval_items.py   # v3: behaviour vs practice arms + mid/far evals

# Everything above is offline (only the Qwen3 tokenizer is fetched from HF). The rest needs TINKER_API_KEY.
export TINKER_API_KEY=...                  # env var only; never in a config or commit
python src/preflight.py                    # one raw request: key accepted? account funded? Qwen3-8B served? (the SDK hangs on a 402)
python src/run_eval.py --items artifacts/eval_items/eval_items_v1.jsonl       --condition base   # baseline, before training
python src/run_eval.py --items artifacts/eval_items/capability_items_v1.jsonl --condition base
python src/run_tinker_sft.py --config configs/train_pilot.yaml --dry-run       # tokenise, count steps, cost; no API
python src/run_tinker_sft.py --config configs/train_pilot.yaml                 # pilot (needs approval)
python src/run_tinker_sft.py --config configs/train_full.yaml                  # the single full run (needs approval)
python src/run_eval.py --items artifacts/eval_items/eval_items_v1.jsonl --condition lora --model-path tinker://.../sampler_weights/final
python src/analyze_results.py --items artifacts/eval_items/eval_items_v1.jsonl \
    --base artifacts/runs/eval_items_v1__base/responses.jsonl --lora artifacts/runs/eval_items_v1__lora/responses.jsonl \
    --out artifacts/runs/analysis_v1
```

`run_eval.py --dry-run` renders every prompt locally and prints the first one exactly as the model
sees it (chat template, empty think block and all) without touching the API.

## What the pipeline does

**Data.** MathDial's `|EOM|` conversations are parsed deterministically; Teacher -> assistant,
Student -> user; the leading dialogue-act tag (`(focus)` etc.) is removed from model-visible text
and kept in `meta.dialogue_acts`; adjacent same-role turns are merged so roles alternate. Because
every MathDial dialogue opens with the teacher reacting to the student's written attempt, a
synthetic opening **user** message carries the problem and the student's own (incorrect) solution
(`--context-mode`, see the approval checklist). `ground_truth` and the teacher annotations never
enter the chat. Validation is a seeded 10% of official-train **qids**; the official test split is
never written to an SFT file (asserted in code and tests).

**Training format.** One example per teacher turn (history + that turn), trained with
`LAST_ASSISTANT_MESSAGE`. This is the cookbook's recommended shape for Qwen3's disable-thinking
renderer, whose empty `<think>` block only frames the final assistant turn; multi-turn
`ALL_ASSISTANT_MESSAGES` examples would show earlier teacher turns a prefix generation never
produces. 2,042 dialogues -> 13,076 examples, 7.0M tokens per epoch, max 2,495 tokens.

**Held-out evaluation.** All MathDial problems are GSM8K problems. The pool is (a) the 76
official-test problems whose qid never occurs in official train, which carry a real student
misconception answer, and (b) GSM8K test problems that appear nowhere in MathDial (1,268 after
verification). Every item's problem text is asserted absent from the fine-tuning split. Arm A seeds
a correct GSM8K solution and applies unsupported pressure toward a false target; Arm B seeds a wrong
solution (the student's real misconception where available) and supplies GSM8K's worked solution
as evidence. Evidence is verified by re-executing GSM8K's `<<a*b=c>>` calculator annotations.
Three pinned wording templates per arm, hashed into the manifest; a test asserts no template
sentence occurs in MathDial. Scoring is a deterministic extractor keyed on `FINAL ANSWER:` with
audited fallbacks; `other` is always reported with its denominator.

**Capability alarm.** 200 MMLU-Redux items (business_ethics, high_school_us_history, philosophy,
professional_law, anatomy; 40 each; `error_type == ok`; deterministic selection), same prompt format
as the Tinker cookbook's `mmlu_redux` benchmark.

**Analysis.** SCR, RRR, UD = RRR - SCR, other rates, per-template and per-source breakdowns, paired
LoRA-minus-base differences with bootstrap CIs clustered by problem.

## Licenses

MathDial is CC BY-SA 4.0 (official repo README; the HF card says CC BY 4.0, we follow the stricter
reading). Processed SFT files are gitignored and not redistributed until share-alike obligations are
documented. GSM8K is MIT. MMLU-Redux is CC BY 4.0. Cite Macina et al. 2023, Cobbe et al. 2021,
Gema et al. 2024.

## Limitations to carry into the write-up

Simulated (LLM) students, not children; tutoring is a pedagogical not therapeutic setting; narrow
math domain; the capability check is a 200-item alarm, not a capability claim; the false targets for
GSM8K-only problems are perturbations rather than real misconceptions (reported separately).
