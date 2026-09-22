# Results v4: controls for v3 (2026-09-09)

Two controls on the v3 result, both trained from the v3 prompts plus a 20% pushback-free replay (plain GSM8K
solves and plain MMLU-Redux multiple choice from four subjects the alarm never uses):

- **practice + mix**: the v3 practice replies (visible recomputation) + replay
- **behaviour, token-matched, + mix**: the v3 behaviour replies padded with a restatement of the problem, so the
  supervised-token budget matches practice (100k vs 111k loss tokens over identical steps) + replay

Plus a far-distance rigidity check, `mcq_flip_v4`: the far MCQ items with the seeding flipped (assistant seeded
with a WRONG letter, the same wordings push toward the CORRECT one). Analyses in `artifacts/runs/analysis_v4/`.

## Cross-version table

| | base | v3 behaviour | v3 practice | v4 behaviour matched + mix | v4 practice + mix |
|---|---|---|---|---|---|
| near SCR (900 math items, unseen wordings) | 0.107 | 0.000 | 0.000 | 0.000 | 0.004 |
| near RRR | 0.951 | 0.884 | 0.993 | 0.878 | **0.998** |
| near persist_wrong (of 450) | 5 | 52 | 3 | 55 | **0** |
| mid SCR (new pressure kinds) | 0.136 | 0.000 | 0.000 | 0.000 | 0.007 |
| far SCR (MMLU, seed correct, push false) | 0.642 | 0.030 | 0.287 | **0.005** | 0.343 |
| far unparsed (of 600) | 21 | 17 | 251 | 73 | 28 |
| capability accuracy (plain MMLU) | 0.695 | 0.680 | 0.340 | 0.700 | **0.710** |
| capability unparsed | 5 | 0 | 67 | 0 | 0 |

Paired differences vs base, v4 arms: behaviour-matched RRR -0.073 [-0.118, -0.029], practice+mix RRR
+0.047 [+0.018, +0.080]; far SCR behaviour-matched -0.637 [-0.687, -0.583], practice+mix -0.298 [-0.355, -0.240];
capability both within noise of base.

## Far rigidity, 2 x 2: P(move to the asserted letter)

| model | assertion is FALSE (mcq_pressure_v3) | assertion is CORRECT (mcq_flip_v4) | difference |
|---|---|---|---|
| base | 0.642 | 0.975 | +0.33 |
| v3 behaviour | 0.030 | 0.392 | +0.36 |
| v3 practice | 0.287 (251 unparsed) | 0.318 (409 unparsed) | +0.03 |
| v4 behaviour matched + mix | 0.005 | 0.257 | +0.25 |
| v4 practice + mix | 0.343 | 0.657 | +0.31 |

On the flip set the behaviour arms' non-moves are `No, the answer is (C).` with the seeded wrong letter: they
keep whatever they were given. All non-broken models discriminate content by roughly the same margin (they
move more when the assertion happens to be right, presumably from their own knowledge of the answer); what
the fine-tunes change is the overall propensity to move, and the behaviour arms push it close to zero.

## Answers to the two open questions from v3

**1. Was the practice arm's near-distance advantage a token-budget artefact?** No. The token-matched behaviour
control reproduces the v3 behaviour arm almost exactly: RRR 0.878 vs 0.884, persist_wrong 55 vs 52. Padding
the replies with an equal amount of non-epistemic text does nothing for selectivity. The practice+mix arm
reaches RRR 0.998 with zero persist_wrong. On identical prompts, at matched supervision, the *content* of the
training reply (a visible check that distinguishes assertion from checkable working) is what produces
selective rather than stubborn resistance.

**2. Was the practice arm's far-distance failure a data-mixing problem?** Half. Mixing fixed the ritual
misfiring: capability is back to 0.710 with nothing unparsed, and far unparsed drops from 251 to 28. The
model now checks only when challenged. But with the ritual under control, far SCR is 0.343: better than
base (0.642), much worse than the behaviour arm (0.005). The forensics show pseudo-checks on multiple-choice
items (`- (B) = 1`, `- 1+1 = 3: recomputing, 1+1 = 2, not 3`) that land on either side. The method the
practice arm learned (recompute the arithmetic) has no referent outside arithmetic, and no amount of replay
supplies one. What transferred at far was the *disposition to check*, without a check that applies.

## What this says

- Training on the same conversations with the check shown gives selective resistance; without it, the same
  conversations give stubbornness. This holds under a token-matched control.
- The selectivity is bounded by the domain of the check. Across pressure wordings and kinds inside that
  domain it transfers completely; across domains it degrades to a disposition without a method.
- The behaviour reflex transfers furthest and is capability-safe, but it is rigidity: it refuses to move even
  toward a correct answer three times in four.
- For the chapter's vocabulary: the connection between how-we-know and why-it-matters is what carried the
  selective disposition, and the scope of that connection is set by the practice it was learned in.

## Remaining limitations

- The far set has no *evidence* arm; the flip set measures response to a bare (correct) assertion, not to
  checkable reasons, so "moves to correct" conflates reconsideration with compliance.
- Single seed, single model, small sets; the practice replies are templated (val NLL near zero).
- Training used the eval's system prompt and answer format (pressure and evidence wordings held out).
- A v5 with a domain-general check (re-read the question, test each option against it) or an explicit scope
  step ("this is not an arithmetic claim, so recomputation does not apply; instead...") is the direct test
  of whether the disposition can be given a portable method.

## Cost

v4 training ~$0.69 + val passes; evals $0.91. Cumulative study spend roughly $17 to $19 of $20.
