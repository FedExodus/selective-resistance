# Results v3: behaviour-only vs practice fine-tunes, tested at three distances (2026-09-09)

Design and pre-registered prediction: PLAN.md, section v3. Both arms were trained on byte-identical GSM8K
pushback prompts (891 examples, 54 steps, same hyperparameters); only the assistant reply differed. Training
wordings were held out from every eval wording (tested). Analyses: `artifacts/runs/analysis_v3/`.

## Headline table

| eval set | metric | base | behaviour | practice | behaviour - base [95% CI] | practice - base [95% CI] |
|---|---|---|---|---|---|---|
| near: v1 math, 900 items | SCR | 0.107 | 0.000 | 0.000 | -0.107 [-0.144, -0.073] | -0.107 [-0.144, -0.073] |
| | RRR | 0.951 | 0.884 | 0.993 | -0.067 [-0.111, -0.022] | +0.042 [+0.009, +0.078] |
| | persist_wrong (of 450) | 5 | 52 | 3 | | |
| mid: 3 new pressure kinds, 450 | SCR | 0.136 | 0.000 | 0.000 | -0.136 [-0.169, -0.104] | -0.136 [-0.169, -0.104] |
| far: MMLU-Redux under pressure, 600 | SCR | 0.642 | 0.030 | 0.287 | -0.612 [-0.662, -0.557] | -0.355 [-0.422, -0.292] |
| | unparsed | 21 | 17 | 251 | | |
| capability: MMLU-Redux plain, 200 | accuracy | 0.695 | 0.680 | 0.340 | -0.015 [-0.060, +0.025] | -0.355 [-0.430, -0.275] |
| | unparsed | 5 | 0 | 67 | | |

Per-template SCR, base -> behaviour -> practice:
- near: pressure_0 0.11 -> 0.00 -> 0.00; pressure_1 0.05 -> 0.00 -> 0.00; pressure_2 0.15 -> 0.00 -> 0.00
- mid: authority 0.33 -> 0.00 -> 0.00; emotional 0.04 -> 0.00 -> 0.00; persistent 0.04 -> 0.00 -> 0.00
- far: pressure_0 0.49 -> 0.01 -> 0.16; pressure_1 0.73 -> 0.02 -> 0.36; pressure_2 0.70 -> 0.07 -> 0.34

## Reading

**Near (same domain, unseen wordings).** Both arms eliminate caving (0 of 450). They separate on the
evidence arm. The behaviour arm's rational revision falls from 0.951 to 0.884: it now answers valid worked
evidence with `No, my answer stands. FINAL ANSWER: 21` on 52 trials. That is the handoff's "generalized
stubbornness" cell. The practice arm's revision *rises* to 0.993 (3 failures in 450): it recomputes the
user's steps, finds they hold, and changes. On the same prompts, the only difference being whether the
training replies showed the check, the practice arm is selectively resistant and the behaviour arm is not.

**Mid (same domain, new pressure kinds).** Both arms hold on all 450, including the authority kind, where
the base model caves a third of the time. The training pressure wordings were plain contradiction, self-work
claims and doubt; authority, emotional and persistent pressure were never seen. Both arms transfer across
pressure kind without loss.

**Far (new domain, MMLU under the v1 wordings).** The base model caves 64% of the time here: it is far more
sycophantic on multiple choice than on arithmetic. The behaviour arm caves 3%, the practice arm 29% with 42%
unparsed. The practice arm's replies show why: it performs its ritual on a philosophy question, "Checking each
step: 1 = 1 (checks out)", loops the ritual until the 768-token cap, and often never states a letter. The
practice it learned was *recompute the arithmetic*, which has no referent outside arithmetic, and it applies
the practice anyway. The behaviour arm's short reflex (`I'm keeping (A).`) survives the domain change, though
its far-eval outputs are visibly off-distribution (stray `</think>` fragments) and the extractor is doing
some work.

**Capability.** Behaviour 0.680 vs base 0.695: intact. Practice 0.340 with 67 unparsed: the ritual fires on
plain questions with no pushback at all ("I'll check your working line by line" when there is no working).
The practice arm's damage is to answering, not knowledge, but by the pre-registered rule the alarm fires.

## Prediction versus outcome

Predicted: both arms beat base at near; practice degrades less than behaviour with distance.
Observed: both beat base at near and mid. At near, practice is *better in kind* (selective, not stubborn),
which the prediction did not anticipate. At far, practice degrades *more*, in a specific way: the connection
it learned between how-we-know and why-it-matters was tied to a domain-specific method, and the method
travels rigidly beyond its jurisdiction. The behaviour arm's reflex travels further but carries no
discrimination with it, and we cannot tell at far whether its 3% cave rate is resistance or stubbornness
because the far set has no evidence arm.

So the connections inference gets support where the epistemic practice applies (near, mid) and a sharp
boundary where it does not (far). What transferred from the practice arm was the practice, including its
limits. In the situated vocabulary: the model learned a practice without learning the practice's scope, which
is itself part of what participation would have to supply.

## Confounds and gaps, in order of importance

1. **Practice replies carry ~6x the supervised tokens** (100k vs 17k loss tokens over identical steps). A
   token-matched control (behaviour replies padded with an equal amount of non-epistemic text, or practice
   trained for fewer steps) is needed before attributing the near-distance advantage to content.
2. **No evidence arm at far.** Add MCQ items where the user gives a correct argument for a different letter
   after a seeded wrong one; then behaviour's far "holds" can be distinguished from refusing to move.
3. **Training used the eval's system prompt and answer format** (as v2 did); pressure and evidence wordings
   were held out but the frame was not.
4. **The practice was single-method.** A practice arm whose check is domain-general ("re-read the question,
   test each option against it") or that includes explicit scope ("this is not an arithmetic claim, so
   recomputation doesn't apply; instead...") is the obvious v4 and the direct test of the scope reading.
5. Small sets, one seed, one model; val NLL near zero shows both arms memorised their templates, which is
   what makes the far-transfer comparison a test of what the templates carried rather than of fit.

## Cost

Training $0.24 + $0.32 (+ val passes, small); evals $0.80. Cumulative study spend roughly $14 to $16.
