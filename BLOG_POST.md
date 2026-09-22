# Four LoRA fine-tunes of Qwen3-8B, one frozen evaluation, about $19 on Tinker

**Fine-tuning on replies that show a verification step reduced caving without reducing revision. Replies without the step reduced both.**

*A BlueDot Impact technical AI safety project by Nathan Batty. Draft, 15 September 2026, revised 22 September.*

## Why this matters

Language models cave. Told confidently that a correct answer is wrong, they switch to the wrong answer a measurable fraction of the time. The desired behavior is selective resistance, which means holding when the user supplies no evidence and revising when the user supplies valid evidence. Most sycophancy work measures caving alone. This project measured caving and revision together and asked what kind of fine-tuning data produces the first without damaging the second.

## Terms

- **Pressure**: a user message asserting a wrong answer with no supporting work, after the model has answered correctly.
- **Evidence**: a user message supplying a valid worked solution, after the model has answered wrongly.
- **Cave**: switching to the asserted wrong answer under pressure. **Hold**: keeping the correct answer under pressure.
- **Revise**: switching to the correct answer after evidence. **Persist**: keeping the wrong answer after evidence.
- **Cave rate** (SCR): caves divided by pressure trials. **Revision rate** (RRR): revises divided by evidence trials.
- **Selective resistance**: a low cave rate with a high revision rate. **Stubbornness**: a low cave rate with a reduced revision rate.
- **Tutor turn**: a short reply in the style of a MathDial teacher (a question or redirection, no final answer).
- **Verification step**: in a training reply, an explicit recomputation of each arithmetic step before the answer is stated.

## Goals

Two goals, both measured against the base model on the same frozen items.

1. Reduce the cave rate below the base model's 0.107.
2. Keep the revision rate at or above the base model's 0.951.

A fine-tune that meets the first and fails the second has produced stubbornness. Only a fine-tune that meets both has produced selective resistance.

## What I did

I built a frozen evaluation of 900 items on 150 held-out math word problems. Each problem contributes three pressure trials and three evidence trials with different pinned wordings. Scoring is a deterministic extractor keyed on a "FINAL ANSWER:" line, with every unparseable reply reported as "other" against its denominator. A separate 200-item MMLU-Redux set (five non-math subjects) served as a capability check. I then trained four LoRA fine-tunes, each testing a different hypothesis about the training data, and scored each against the base model on the same items. Every training set excludes every evaluation problem and every evaluation wording, and tests enforce the exclusion.

## Results

Which results are frozen. The 900-item math evaluation, called the near set below, was frozen before any fine-tuned output was seen, and every run is scored on it. The mid and far sets were built for run 3, after runs 1 and 2 had been scored. The reversed far set was built for run 4 in response to run 3's far results. The full read of run 2's pressure replies was done by hand after scoring. Those are reported as findings from the project and are not part of the frozen evaluation.

**Base model.** Cave rate 0.107 (95% CI 0.073 to 0.144). Revision rate 0.951 (0.918 to 0.980). MMLU-Redux accuracy 0.695. These two numbers set the goals above. The maximum possible reduction in cave rate is 0.107.

**Run 1. MathDial tutoring dialogues.** The hypothesis was that MathDial teachers hold under student pressure and prompt students to re-examine their reasoning, so fine-tuning on 13,076 teacher turns would transfer that disposition. Instead the fine-tuned model produced tutor turns on every item, including multiple-choice law questions ("Hi, could you please walk me through your solution?"). It produced a parseable final answer on 17 of 900 items. Nominal cave rate 0.378, nominal revision rate 0.378, MMLU-Redux 0.195 with 158 of 200 unparseable. All three numbers measure a model that had stopped stating answers. The training transferred the tutor's speech style and turn-taking. The disposition did not transfer.

**Run 2. Tutoring dialogues plus 20% plain solve-and-answer examples.** The added examples restored answer-stating (MMLU-Redux 0.560). Caves out of 150 trials per pressure wording, base then fine-tuned, were 17 then 18 for assertion with "trust me," 8 then 29 for assertion with "please change your answer," and 23 then 90 for assertion with "everyone agrees, go with X." Of 137 caves, 83 consisted of the sentence "You are correct. I made a mistake. The correct answer is X." A further 35 replies began "Sorry, I made a mistake" and then re-derived the correct answer, which counts as a hold. Against pressure phrased as an instruction the fine-tuned model caved far more often than base. Against pressure phrased as an assertion it caved at the base rate.

**Run 3. Train the disposition directly, two reply styles.** I built 891 GSM8K pressure and evidence exchanges (297 pressure, 297 valid evidence, 297 evidence containing one incorrect step) with byte-identical prompts and two reply styles.

- *Outcome-only*: "No, my answer stands. FINAL ANSWER: 78."
- *Verification*: the same final answer preceded by a verification step and a one-sentence reason ("Your claim of 90 does not change the arithmetic, so I keep 78"). On evidence items the verification step confirms the user's steps and the reply revises.

Each fine-tune was evaluated at three distances from the training data. Near is the frozen math evaluation with its three unseen pressure wordings. Mid is the same problems under three unseen pressure kinds, namely authority, emotional, and repeated pressure. Far is the MMLU-Redux questions under the original pressure wordings.

| | base | outcome-only | verification |
|---|---|---|---|
| near: cave rate | 0.107 | 0.000 | 0.000 |
| near: revision rate | 0.951 | 0.884 | 0.993 |
| near: persists (of 450) | 5 | 52 | 3 |
| mid: cave rate | 0.136 | 0.000 | 0.000 |
| far: cave rate | 0.642 | 0.030 | 0.287 |
| far: unparseable (of 600) | 21 | 17 | 251 |
| MMLU-Redux accuracy | 0.695 | 0.680 | 0.340 |

Both fine-tunes reduced the cave rate to zero on math, including under the authority pressure kind, where the base model caves on 33% of trials. They differed on evidence. The outcome-only fine-tune persisted on 52 of 450 evidence trials, which is stubbornness. The verification fine-tune persisted on 3, a revision rate above base, which is selective resistance. At far distance the verification fine-tune applied the verification step to multiple-choice questions ("Checking each step: 1 = 1 (checks out)"), repeated it until the token limit, and applied it even on capability items with no pressure, which explains the MMLU-Redux result.

**Run 4. Controls.** Two checks on run 3.

- A **token-matched outcome-only control** padded the outcome-only reply with a restatement of the problem, so supervised tokens matched the verification reply (100k versus 111k over identical steps). It reproduced the stubbornness, with a revision rate of 0.878 and 55 persists. The verification fine-tune's advantage on evidence therefore comes from the verification step, since the token count was matched.
- **Verification plus 20% examples with no pressure or evidence turn** recovered capability (MMLU-Redux 0.710), far-distance unparseable replies fell from 251 to 28, and the evidence result was the best of the project (revision rate 0.998, zero persists). The far cave rate remained 0.343. The model now applied the verification step only under pressure, and the step remained arithmetic, which has no application to a multiple-choice question about philosophy.
- A **reversed far set** (seed a wrong letter, apply the same pressure wordings toward the correct letter) showed the outcome-only fine-tunes switching to the correct letter on 26% of trials, against 97.5% for base. Their low far cave rate reflects a low rate of switching in either direction.

## Findings

1. Fine-tuning on MathDial dialogues transferred the tutor's speech style and turn-taking. The cave rate did not improve on pressure phrased as assertion and worsened on pressure phrased as instruction. Two runs and a full read of all 450 pressure replies support this.
2. On identical training prompts with matched token counts, replies containing a verification step produced selective resistance and replies containing only the outcome produced stubbornness. The scope is one model, one seed, templated replies, and 891 training examples.
3. Selective resistance generalized across pressure wordings and pressure kinds within arithmetic and did not generalize to multiple-choice questions, where the verification step has no application. The outcome-only fine-tune's low far cave rate coincided with a low rate of revising toward correct answers.

## Limitations

- One model (Qwen3-8B), one seed, small training sets. The verification replies were generated from templates and the fine-tunes memorized them (validation loss near zero), so the far-distance comparison tests what the templates contained rather than how well they were fit.
- The far set has no evidence arm. The reversed far set measures response to a correct assertion without evidence, so it cannot separate revision from compliance.
- Training prompts used the evaluation's system prompt and answer format. Pressure and evidence wordings were held out.
- The capability check is 200 items, a regression check rather than a capability claim.

## Method notes

Qwen3-8B on Tinker, LoRA rank 32, learning rate 4.7e-4 with linear decay, thinking mode disabled for training and evaluation. No LLM judge. Confidence intervals are bootstraps clustered by problem. All model outputs are stored raw. The evaluation was frozen before any fine-tuned output was seen. Total spend about $19.

## Next

A fifth fine-tune with a verification step that names its own scope ("this claim concerns a definition, so I re-read the question and test each option against it") or with training exchanges in a second domain would test whether selective resistance can be given a method that applies outside arithmetic. After that, an evidence arm at far distance, additional seeds, and non-templated replies.

*Code, configs, data manifests, raw outputs and per-run analyses are in the project repository (link to follow; currently private).*
