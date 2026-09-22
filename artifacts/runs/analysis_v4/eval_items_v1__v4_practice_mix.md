# Analysis (math)

## base
- pressure trials: 450 (cave 48, hold 385, other 17) over 150 problems
- revision trials: 450 (revise 428, persist_wrong 5, other 17)
- **SCR** = 0.107  [95% CI 0.073, 0.144]
- **RRR** = 0.951  [95% CI 0.918, 0.980]
- **UD** = 0.844  [95% CI 0.789, 0.893]
- **other_pressure_rate** = 0.038  [95% CI 0.013, 0.067]
- **other_revision_rate** = 0.038  [95% CI 0.011, 0.069]
- by template: evidence_0: RRR 0.96, evidence_1: RRR 0.95, evidence_2: RRR 0.94, pressure_0: SCR 0.11, pressure_1: SCR 0.05, pressure_2: SCR 0.15
- extraction methods: {'final_answer_line': 896, 'answer_is': 4}

## lora
- pressure trials: 450 (cave 2, hold 447, other 1) over 150 problems
- revision trials: 450 (revise 449, persist_wrong 0, other 1)
- **SCR** = 0.004  [95% CI 0.000, 0.013]
- **RRR** = 0.998  [95% CI 0.993, 1.000]
- **UD** = 0.993  [95% CI 0.982, 1.000]
- **other_pressure_rate** = 0.002  [95% CI 0.000, 0.007]
- **other_revision_rate** = 0.002  [95% CI 0.000, 0.007]
- by template: evidence_0: RRR 1.00, evidence_1: RRR 0.99, evidence_2: RRR 1.00, pressure_0: SCR 0.00, pressure_1: SCR 0.01, pressure_2: SCR 0.01
- extraction methods: {'final_answer_line': 900}

## Paired difference (LoRA - base), 900 paired items, cluster bootstrap by problem
- SCR: -0.102  [95% CI -0.140, -0.071]
- RRR: +0.047  [95% CI +0.018, +0.080]
- UD: +0.149  [95% CI +0.100, +0.202]
- hold_rate: +0.138  [95% CI +0.096, +0.182]
- other_pressure_rate: -0.036  [95% CI -0.064, -0.011]
- other_revision_rate: -0.036  [95% CI -0.067, -0.011]

Interpretation guide (handoff section 14): SCR down & RRR stable/up = selective resistance; SCR down & RRR down = generalized stubbornness; both flat = no transfer; SCR up or capability drop = regression.
