# Pilot run report (train_pilot, 2026-09-08)

Purpose: go/no-go check before the full run. NOT a result.

## Config

- Qwen/Qwen3-8B, `qwen3_disable_thinking`, LoRA rank 32, LR 4.7e-4 linear decay, batch 32, max_length 3072
- 150 seeded training dialogues -> 924 per-turn examples; val = 15 dialogues / 99 examples
- steps run: 28 (28 full batches; 28 leftover examples not used); checkpoints at 10, 20, final

## Loss

| step | lr | train NLL | val NLL |
|---|---|---|---|
| 0 | 4.70e-04 | 6.522 | 6.006 |
| 1 | 4.53e-04 | 3.524 | |
| 2 | 4.36e-04 | 2.603 | |
| 3 | 4.20e-04 | 2.175 | |
| 5 | 3.86e-04 | 1.892 | 1.906 |
| 10 | 3.02e-04 | 1.899 | 1.755 |
| 15 | 2.18e-04 | 1.975 | 1.717 |
| 20 | 1.34e-04 | 1.702 | 1.683 |
| 25 | 5.04e-05 | 1.731 | 1.674 |
| 27 | 1.68e-05 | 1.627 | |

Val NLL 6.006 -> 1.906 -> 1.755 -> 1.717 -> 1.683 -> 1.674: falls at every eval, no rise (the LR-revisit trigger did not fire).
Train NLL noisy step-to-step (tiny batches of short teacher turns) but 6.5 -> ~1.6 overall.

## Truncation

- examples over max_length: train 0, val 0 (longest 1,715 / 1,042 tokens)

## Cost

- train tokens processed (from checkpoint record): 450,346 vs 465,120 planned
- training cost at $0.44/M: **$0.198** vs estimate $0.205
- val NLL evals: 6 x 48,110 tokens = 288,660 forward-only tokens; if billed at the train rate that is up to $0.127 more (not in the original estimate)
- sampling for the qualitative check (12 completions, <= 256 tokens each): negligible
- **Check the Tinker billing page for the actual charge; the numbers above are computed from token counts, not read from the account.**

## Sampled turns (6 held-out val turns, greedy, same decoding as the eval)

`samples_lora_final.jsonl` vs `samples_base.jsonl`. LoRA outputs are 3-24 tokens, single tutoring moves
(questions, short corrections, 'good job'), no formatting artifacts, no think blocks, all stop on <|im_end|>.
The base model on the same turns writes 93-256 token explanations with markdown, two hitting the 256-token cap.
Two LoRA turns are mildly off-target ('What is the correct answer?' on a student who has not yet started;
'Hi, can you walk me through your solution?' when the student already wrote the solution out), which is
consistent with 28 steps on 150 dialogues rather than a formatting or data problem.

## Go/no-go (pilot criteria from PLAN.md)

- [x] val NLL falls
- [x] sampled turns look like short tutoring moves
- [x] no formatting artifacts
- [x] nothing truncates
- [x] cost matches estimate (training tokens within 3%; val-eval cost was not in the estimate)

Recommendation: proceed with `configs/train_full.yaml` hyperparameters unchanged (rank 32, LR 4.7e-4, batch 64,
1 epoch, 204 steps, ~$3.08 training). One cost decision for Nathan first: with `eval_every: 25` the full run
does 9 val-NLL passes over the full val set (1,367 examples, 730,029 tokens each) = 6.57M forward tokens,
up to **$2.89** if forward passes are billed at the $0.44/M train rate. Options: keep as is (~$6 total),
`eval_every: 50` (5 passes, ~$1.6), or a fixed seeded val subset (e.g. 300 examples, ~$0.6 for 9 passes).
The pilot's val curve was smooth enough that fewer passes lose little.
