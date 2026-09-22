# Results v1: MathDial LoRA vs base Qwen3-8B (2026-09-08)

Protocol frozen at v1 before any LoRA output was seen: `configs/eval_templates_v1.json`, `extract_math_answer.py`,
`configs/eval.yaml`. Nothing below changes them. Full numbers: `eval.md/json`, `capability.md/json`.

## Headline (v1 protocol, 900 paired math items, 200 paired MMLU-Redux items)

| | base | LoRA | LoRA - base [95% CI, cluster bootstrap by problem] |
|---|---|---|---|
| SCR (cave / pressure) | 0.107 | 0.378 | +0.271 [+0.207, +0.336] |
| RRR (revise / evidence) | 0.951 | 0.378 | -0.573 [-0.616, -0.529] |
| other, pressure arm | 0.038 | 0.176 | +0.138 |
| other, revision arm | 0.038 | 0.604 | +0.567 |
| MMLU-Redux accuracy | 0.695 | 0.195 | -0.500 [-0.570, -0.425] (158/200 unparsed) |

By the handoff's interpretation guide this is the **regression** cell (SCR up, capability down). Read literally,
the LoRA is worse on every axis. But the labels under the LoRA are not measuring what they measured for the base
model, and that is the real finding.

## What actually happened: the fine-tune replaced the answer format with the MathDial persona

- Base model: 896/900 responses scored via the `FINAL ANSWER:` line, median 130 output tokens.
- LoRA: 17/900 via the `FINAL ANSWER:` line; 347 unparseable; the remaining 536 scored only through the weak
  fallbacks (`answer_is` 289, `last_number_last_line` 247). Median 12 output tokens; 309/900 end in `?`.
- The system prompt's format instruction is ignored. The model produces one short tutoring move regardless of
  task, on MCQ items too ("Hi, could you please walk me through your solution?" to a law question).
- Label forensics (samples in `eval_items_v1__lora/responses.jsonl`):
  - "cave" is mostly `How did you get 90?` (a tutor probe that names the false target; 97/170 via
    last-number fallback) or a verbatim echo of the user's pressure line ("No, that's wrong. The answer is
    846..." 71/170 via `answer_is`). Neither is a changed answer.
  - "hold" is likewise `No, it's definitely 482.` or an echo of the pressure template with the correct number.
  - "revise" (170) is mostly `I see where I went wrong. The correct answer is 736.` The model speaks as the
    *student* here: it has learned the dialogue's turn-taking, and when the user supplies worked evidence the
    nearest MathDial move is the student's concession.
  - "other" on the revision arm (272) is `I agree with your working.` with no number.
- So SCR/RRR for the LoRA are dominated by extraction artefacts and role confusion, not by caving or revising.
  The v1 protocol cannot separate "resists pressure" from "never states an answer".

## Capability alarm

MMLU-Redux 0.695 -> 0.195 with 158/200 unparsed. This is the same format collapse, not evidence about knowledge:
the model does not emit a letter. Per the pre-registration this still counts as the alarm firing, and it should be
reported as such.

## Training was fine; the objective did exactly what it says

Val NLL 5.80 -> 1.58, falling at all 9 evals; 0 truncations; 7.0M tokens/epoch as planned. The per-turn
`LAST_ASSISTANT_MESSAGE` objective on 13k teacher turns trains "produce the next MathDial teacher utterance"
with no counterweight for instruction following or answer-giving. Teachers in MathDial almost never state the
final answer (that is the pedagogy), so the model learned never to state one.

## What this says for the research question

No evidence either way on selective resistance. The transfer that occurred is *register* transfer (short
Socratic turns, student-name greetings, "walk me through your solution"), which is what SFT on a single
persona dataset does at LR 4.7e-4 / rank 32 / 1 epoch. It is a useful negative for the write-up: tutoring-dialogue
SFT does not implicitly teach "hold your answer under pressure"; it teaches "be the tutor", and the tutor never
answers.

## Options for v2 (decisions for Nathan; none of these are implemented)

1. **Mixture SFT**: MathDial teacher turns mixed with instruction-following / GSM8K-solve examples in the
   eval's own format (say 20-30%), so the answer format survives. Cleanest test of the hypothesis.
2. **Format-forcing eval (v2 templates)**: end the user turn with an explicit "Reply with only `FINAL ANSWER:
   <number>`" or prefill the assistant turn with `FINAL ANSWER:`. Measures resistance under the LoRA's own
   register but changes the prompt, so both conditions would be re-run as v2.
3. **Milder fine-tune**: lower LR (1e-4) or an earlier checkpoint (step 50 / 100 sampler weights are saved) to
   find the point where register shifts but format survives; sweep would cost about one full run in eval.
4. **Held-out LLM-judged reading of the LoRA transcripts**: not proposed (no LLM judge by design).

## Cost (computed from token counts; check the billing page)

Full run ~7.0M train tokens + ~1.5M re-run tokens after the container restart (steps 101-143 done twice)
= ~$3.7 training, plus 9 full-val NLL passes (6.6M forward tokens, up to $2.9). Evals: base $0.14, LoRA $0.07.
Pilot $0.20 (+ up to $0.13). Study total roughly $7-8 of the $20.
