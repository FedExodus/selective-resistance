# Cost estimate (USD)

Prices per 1M tokens (checked 2026-09-08): prefill 0.195, sample 0.6, train 0.44.

| run | dialogues | examples | tokens/epoch | steps | train tokens | est. cost |
|---|---|---|---|---|---|---|
| train_pilot | 150 | 924 | 465,120 | 28 | 465,120 | $0.20 |
| train_full | 2042 | 13076 | 7,005,777 | 204 | 7,005,777 | $3.08 |

| eval set | items | prompt tokens | per condition (typical) | per condition (upper) |
|---|---|---|---|---|
| capability_items_v1 | 200 | 34,160 | $0.05 | $0.10 |
| eval_items_v1 | 900 | 271,097 | $0.24 | $0.47 |

**Study total (typical): $3.87**  = pilot $0.20 + full $3.08 + eval x2 $0.58 (eval upper bound $1.13)
