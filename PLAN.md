# Implementation plan, status and approval checklist

Date: 2026-09-08. Handoff brief: `BlueDot_MathDial_Tinker_Claude_Code_Handoff.docx`.

## Status against the brief's instructions

| Step | Status |
|---|---|
| 1. Implementation plan + blockers | this file |
| 2. Pin dataset and dependency versions | done: `data/manifests/sources.json`, `requirements*.txt` (tinker 0.27.1, tinker-cookbook 0.5.7) |
| 3. Preprocessing implemented and tested | done: 47 tests pass; audit in `artifacts/audits/data_audit.md` |
| 4. Evaluation harness + base-model baseline | harness done and dry-run; **baseline blocked on `TINKER_API_KEY`** |
| 5. Token and cost estimate | done: `artifacts/audits/cost_estimate.md` |
| 6. Small training pilot | config ready (`configs/train_pilot.yaml`); **not launched** |

## Blockers

1. **No Tinker API key in this environment.** Cannot call `get_server_capabilities()` to confirm
   `Qwen/Qwen3-8B` is served, cannot collect the baseline, cannot pilot. The catalog page listed
   Qwen3-8B (32K, hybrid, $0.44/M train, $0.60/M sample, $0.195/M prefill) on 2026-09-08.
2. **Decisions below need a yes** before any paid run (the brief, section 13).

## Decisions approved by Nathan (2026-09-08)

1. Thinking disabled (`qwen3_disable_thinking`) for training and evaluation.
2. Opening user turn = problem + the student's incorrect attempt (`problem_and_student_solution`).
3. Per-teacher-turn training examples, `LAST_ASSISTANT_MESSAGE`.
4. Full run: rank 32, LR 4.7e-4, batch 64, 1 epoch, linear decay, max_length 3072; pilot first, LR revisited only if the pilot's val NLL rises.
5. Eval set v1 = 150 problems (76 MathDial-test-only w/ real misconceptions + 74 GSM8K-unseen w/ perturbations), reported by source; scale to ~300 as v2 if CIs are wide.
6. Capability alarm = MMLU-Redux, 5 subjects x 40 as built.
7. MathDial treated as CC BY-SA 4.0; eval items carry attribution + BY-SA if ever published.

## Live status (2026-09-08, second session)

- Environment rebuilt from scratch: `download_mathdial.py` (sha256 OK), `preprocess_mathdial.py`
  reproduced every hash in `data/manifests/preprocess_manifest.json` (no git diff), 47 tests pass.
- `TINKER_API_KEY` is set and **accepted** (`/api/v1/client/config` and `/api/v1/auth/token` return 200).
- **Blocked at gate 1: HTTP 402 Payment Required** on `get_server_capabilities` and every other
  endpoint: "Access ... is blocked due to billing status. Please add payment at
  https://tinker.thinkingmachines.ai/billing/balance". No paid call was made; nothing was spent.
- Gotcha: the SDK retries a 402 every 5 s forever, so `ServiceClient().get_server_capabilities()`
  (and therefore `run_eval.py` / `run_tinker_sft.py`) *hangs* rather than failing. Run
  `python src/preflight.py` first; it makes one raw request with a timeout and prints the status.
- Next: add payment, `python src/preflight.py` (expect exit 0 and `Qwen/Qwen3-8B served: True`),
  then resume at gate 2 (`run_eval.py --limit 2 --condition smoke`).

## Live status (2026-09-08, after payment)

| Gate | Result |
|---|---|
| 1 capabilities | `Qwen/Qwen3-8B` served (35 models). `src/preflight.py` exit 0. |
| 2 smoke | 2/2 items parsed via `FINAL ANSWER` line; both `hold`. |
| 3 baseline | `artifacts/runs/analysis_v1_baseline/`: SCR 0.107 [0.073, 0.144], RRR 0.951 [0.918, 0.980], other 3.8% / 3.8%; MMLU-Redux 0.695 [0.630, 0.755]. Templates, scoring, decoding frozen at v1. Cost $0.14. |
| 4 pilot | `artifacts/runs/train_pilot/pilot_report.md`: val NLL 6.01 -> 1.67 falling at every eval, 0 truncations, short tutoring-move samples, $0.20 training (+ up to $0.13 val evals). Go. |
| 5 full run | Approved and run (cost accepted as is). 204 steps, val NLL 5.80 -> 1.58 at all 9 evals, 0 truncation. Container restarted mid-run at step 143; resumed from the step-100 checkpoint with the new `--resume` flag (seeded batch order, LR by step; replayed step-100 val NLL matched to 4 dp). Final weights `tinker://e7a5b02a-efb5-52e7-b882-daf82a332ada:train:0/sampler_weights/final`. |
| 6 LoRA eval + paired analysis | `artifacts/runs/analysis_v1/RESULTS.md`. v1 protocol: SCR 0.107 -> 0.378, RRR 0.951 -> 0.378, MMLU-Redux 0.695 -> 0.195 (158 unparsed). **Format/persona collapse**: the LoRA answers everything with a short MathDial tutor turn and ignores the FINAL ANSWER instruction, so the labels are extraction artefacts and role echoes, not caving/revising. No evidence either way on selective resistance. v2 options listed in RESULTS.md, none implemented. |

Baseline notes: the base model already holds under pressure 85% of the time and revises on evidence 95%
of the time, so headroom on SCR is ~0.11 and the study's power question is whether a real drop is
detectable inside the CI width (~0.07). All 34 "other" math trials are genuine third answers (parsed
fine), 26 of them on one ambiguous "three times more points" problem. MathDial-test-only problems with real
misconceptions are harder than GSM8K perturbations (SCR 0.132 vs 0.081).

## v2 (set up 2026-09-08, not launched)

- **Checkpoint check** (`artifacts/runs/ckpt_check/`, 48 items = 8 problems x 6 templates): the answer-line
  rate is 48/48 for base, 0/48 at step 50, 1/48 at step 100, 0/48 at step 204. The format collapse is
  complete within the first 50 steps (1.7M tokens), so "train less" is not a fix. Mixture it is.
- **Data**: `src/build_mixture_v2.py` -> `data/processed/sft_{train,val}_v2_mix.jsonl` (gitignored; manifest
  with sha256s in `data/manifests/mixture_v2_manifest.json`). 13,076 MathDial turns + 3,269 GSM8K-train solve
  examples (20% of rows) written with the v1 system prompt / solve instruction / answer format verbatim.
  Excluded: the 32 GSM8K-train problems whose text is in eval_items_v1 and 20 unverifiable solutions; the
  other 118 eval problems have <50% word overlap with anything in GSM8K train. Pressure/evidence templates
  never appear (tests/test_mixture_v2.py, 3 tests; suite now 50).
- **Known property**: replay is 20% of examples but ~50% of loss tokens (588k vs 290k), because a worked
  solution is ~90 tokens and a tutor turn ~22. With token-mean loss, half the gradient is "solve and answer".
  Kept at ratio 0.25 for v2; if tutoring register looks diluted, ratio 0.10-0.15 is the next knob.
- **Config**: `configs/train_full_v2.yaml` = train_full.yaml with the data swapped and `eval_every: 50`
  (cost only). Hyperparameters unchanged on purpose: one variable. 255 steps, 7.75M tokens, ~$3.4 training
  + up to ~$2.1 val passes; LoRA eval ~$0.2. Fits the ~$12 remaining.
- **Eval**: unchanged, v1. Limitation to record: the LoRA sees the eval's system prompt and solve wording
  in training (that is the point), the base model does not; the pressure/evidence turns stay unseen.
- **Launch**: `python src/run_tinker_sft.py --config configs/train_full_v2.yaml` (detached; use `--resume` if
  the container restarts), then `run_eval.py --condition lora_v2 --model-path ...` on both item sets and
  `analyze_results.py` paired against the same base responses.

### v2 outcome (run 2026-09-08, `artifacts/runs/analysis_v2/RESULTS_v2.md`)

Val NLL 4.95 -> 1.34, 0 truncation. Replay restored single-turn answering (MMLU-Redux 0.195 -> 0.560; answer
lines 17 -> 182 of 900) but not the second-turn pushback context, where the model still speaks MathDial
dialogue (echoes the user, "Yes, that's correct.", asks a question). Per template: holds like base against plain assertion (18 vs 17 caves), obeys an explicit "go with X"
directive 60% of the time (90 vs 23), almost always as a bare "You are correct, I made a mistake" reflex. Same conclusion as v1, now with the format confound partly removed:
tutoring-dialogue SFT transfers register and dialogue reflexes, not selective resistance. Study spend ~$12-14.

## v3 (set up 2026-09-09, not launched): train the disposition directly, test at increasing distance

Question reframed after v1/v2: can resistance to unsupported pressure, trained in ONE narrow context, hold in
contexts the model never saw, and does HOW it is trained matter? The situated-learning inference under test:
what generalises is the connection between elements (how-we-know tied to why-it-matters), not the behaviour
alone.

- **Two arms, same prompts, different replies** (`src/build_v3_train.py`, `configs/v3_templates.json`):
  - *behaviour*: `No, my answer stands. FINAL ANSWER: 78` / `You're right, I made an error. ... FINAL ANSWER: 115`
  - *practice*: the same outcome reached through a visible recomputation of every step, framed by why
    ("a claim on its own isn't evidence"; "working I can check is different from a bare claim").
  Three exchange types, one per problem: pressure (hold), valid evidence (revise), invalid evidence with one
  corrupted step (hold). 891 train / 99 val per arm from GSM8K train, eval problems excluded. Prompts are
  byte-identical across arms (tested); practice checks are recomputed and asserted correct (tested).
- **Training wordings are held out from every eval wording** (tested; two collisions found and fixed).
- **Evals at three distances** (`src/build_v3_eval_items.py`):
  - near: `eval_items_v1` unchanged (its 3 pressure + 3 evidence wordings never seen in training)
  - mid: `pressure_kinds_v3` = same 150 problems, 3 NEW pressure kinds (authority, emotional, persistent two-round), 450 items
  - far: `mcq_pressure_v3` = 200 MMLU-Redux items with a seeded correct letter and the v1 pressure wordings pushing to a wrong letter, 600 items; new `kind=mcq_pressure` labelled cave/hold/other by letter (`run_eval.py`), analysed with the math rate function (`analyze_results.py`)
  - plus `capability_items_v1` as the alarm
- **Configs**: `train_v3_behaviour.yaml`, `train_v3_practice.yaml`: batch 32, 2 epochs, 54 steps, LR 4.7e-4,
  rank 32. Behaviour 550k train tokens (~$0.24), practice 717k (~$0.32). Known confound: practice replies
  carry ~6x the loss tokens (100k vs 17k); same steps and examples, more supervised text.
- **Run plan**: base on mid + far (~$0.25) -> two trainings -> each LoRA on near, mid, far, capability
  (~$0.4 per LoRA) -> paired analyses vs base and vs each other. Total ~$1.5.
- **Prediction** (written before running): both arms beat base at near; practice degrades less than
  behaviour from near to mid to far. If the arms are indistinguishable at far, the connections inference
  gets no support from this test.

### v3 outcome (run 2026-09-09, `artifacts/runs/analysis_v3/RESULTS_v3.md`)

Near: both arms SCR 0.107 -> 0.000; RRR behaviour 0.951 -> 0.884 (52 persist_wrong: generalized
stubbornness), practice 0.951 -> 0.993 (selective). Mid: both 0 caves of 450 (base 0.136, authority 0.33).
Far (MMLU under pressure; base caves 0.642!): behaviour 0.030, practice 0.287 with 251 unparsed, because the
practice model runs its "recompute each step: 1 = 1" ritual on non-arithmetic questions until the token cap.
Capability: behaviour 0.680 (intact), practice 0.340 (ritual fires on plain questions; alarm).
Reading: the practice arm transfers selectivity where its epistemic method applies and carries the method
rigidly where it does not; the behaviour arm's reflex travels further but with no discrimination. Confounds:
6x loss tokens in practice; no far evidence arm. v4 candidates: token-matched control, far evidence arm,
domain-general or scope-aware practice.

### v4 outcome (run 2026-09-09, `artifacts/runs/analysis_v4/RESULTS_v4.md`)

Token-matched behaviour control reproduces v3 behaviour (RRR 0.878, persist_wrong 55): the practice
advantage at near is content, not token count. Practice + 20% replay: capability 0.710 (fixed), far unparsed
28 (fixed), near RRR 0.998 / persist_wrong 0 (best of all runs), but far SCR 0.343 (pseudo-checks on MCQ);
behaviour-matched + mix far SCR 0.005 but moves toward a correct assertion only 26% of the time (rigid).
Mixing fixed the ritual misfiring, not the missing method. Budget nearly spent (~$17-19 of $20).

Remaining blocker: none. Next: write up v1-v4, or v5 with a portable check (needs more budget).

## Approval checklist (brief section 13)

1. **MathDial revision and license.** HF `eth-nlped/mathdial` @ `acc3878459e0bd8c04ab840056572f0b8b1abe1f`
   (2025-02-26), sha256 of both files in `sources.json`. License read as CC BY-SA 4.0 (official repo
   README) despite the HF card's CC BY 4.0. The GitHub repo has no LICENSE file. Processed SFT data is
   gitignored. Note: `artifacts/eval_items/eval_items_v1.jsonl` embeds the question text and student
   solutions of the 76 MathDial-test-only problems (a BY-SA derivative) inside this private repo; if the
   items are ever published, they must carry MathDial attribution and the BY-SA licence.
2. **Tinker versions and model.** tinker 0.27.1, tinker-cookbook 0.5.7. `Qwen/Qwen3-8B` present in the
   docs catalog; live check pending the key.
3. **Renderer and thinking mode: `qwen3_disable_thinking` for training AND evaluation.** MathDial has
   no reasoning traces, so training in thinking mode would teach the model to emit empty think
   blocks; disabling keeps train and eval consistent and decoding cheap/deterministic. The base
   condition uses the identical renderer.
4. **Dialogue-act policy.** Tags stripped from model-visible text, kept in metadata. Counts: focus 5,535,
   generic 3,539, probing 3,289, telling 2,487; 2 untagged teacher turns. Samples in the audit.
   Also: 411 adjacent same-role turns merged; 55 empty turn bodies dropped; 1 malformed dialogue
   (stray unprefixed segment) dropped and recorded in the sidecar.
5. **Opening context (new decision, not in the brief).** MathDial dialogues start mid-stream: the
   teacher's first turn reacts to the student's written attempt. Default `--context-mode
   problem_and_student_solution` puts the problem and the student's incorrect solution in a synthetic
   opening user turn. The student's solution is the student's own work (what the human teacher saw),
   not a label; `ground_truth` never enters. Alternative `problem_only` is one flag away.
6. **Validation split.** 10% of official-train qids, seed 0: 104 val qids / 219 dialogues; 931 train
   qids / 2,042 dialogues. Zero qid overlap (asserted). Note the official train and test splits share
   318 problems; we train on official train as instructed and build the eval from problems whose text
   never appears in it (asserted per item).
7. **Example format.** Per-teacher-turn examples with `LAST_ASSISTANT_MESSAGE` (13,076 train / 1,367
   val). Full-dialogue files are also written for comparison only.
8. **Hyperparameters (proposed, conservative).**
   - LoRA rank 32 (cookbook default; "LR matters more than rank").
   - LR 4.7e-4 = `hyperparam_utils.get_lr("Qwen/Qwen3-8B", is_lora=True)`; linear decay; Adam defaults.
   - Batch 64 examples (~34k tokens/step), 1 epoch = 204 steps; checkpoint every 50, val NLL every 25.
   - max_length 3072, `allow_truncation: false` (longest example 2,495 tokens; nothing truncates).
   - Pilot: 150 dialogues (924 examples), batch 32, 28 steps, ~$0.20. Go/no-go on: val NLL falls,
     sampled turns look like short tutoring moves, no formatting artifacts, cost matches estimate.
   - Full run: ~$3.08 per epoch. A second epoch is cheap but not proposed until val NLL says so.
9. **Evaluation set.** 150 problems (76 MathDial-test-only + 74 GSM8K-unseen, seed 20260908), 3
   pressure + 3 evidence templates -> 900 items. False targets: real student misconception for the 76,
   deterministic perturbation for the 74 (reported separately). 6 GSM8K problems excluded because
   their final answer was not supported by re-executed steps. Templates hashed in the manifest;
   **the manual audit of a subset of items is still to do before the baseline is frozen.**
10. **Capability benchmark.** MMLU-Redux (not plain MMLU), 5 non-math subjects x 40 = 200 pinned
    items, revision `3720db6a`. Subjects: business_ethics, high_school_us_history, philosophy,
    professional_law, anatomy (MMLU-Redux has no psychology/biology config; anatomy stands in).
11. **Decoding.** temperature 0, top_p 1, top_k -1, max_tokens 768, seed 0, stop on `<|im_end|>`,
    system prompt pinned in the templates file. Identical for both conditions.
12. **Cost.** Study total ~$3.9 typical (pilot $0.20 + full $3.08 + eval both conditions $0.58; eval
    upper bound $1.13). Recheck the price page on the day.

## Order of operations once the key is available

1. `python -c "import tinker; print(tinker.ServiceClient().get_server_capabilities())"` and confirm Qwen3-8B.
2. Manually audit ~20 eval items (both arms) and, if wording changes, bump to `eval_templates_v2`.
3. Baseline: `run_eval.py --condition base` on eval and capability items; `analyze_results.py` baseline-only.
   Freeze prompts/scoring here (templates + extractor are versioned).
4. Pilot: `run_tinker_sft.py --config configs/train_pilot.yaml`; inspect loss, samples, truncation, cost.
5. Full run on approval; then `run_eval.py --condition lora --model-path ...` on both item sets;
   paired analysis.

## Out of scope (kept out on purpose)

Three-way LoRA comparisons, other datasets, memory experiments, broad capability claims, attachment
claims. See the brief, section 2.
