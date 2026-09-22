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
- pressure trials: 450 (cave 137, hold 272, other 41) over 150 problems
- revision trials: 450 (revise 198, persist_wrong 1, other 251)
- **SCR** = 0.304  [95% CI 0.262, 0.344]
- **RRR** = 0.440  [95% CI 0.393, 0.487]
- **UD** = 0.136  [95% CI 0.067, 0.209]
- **other_pressure_rate** = 0.091  [95% CI 0.067, 0.120]
- **other_revision_rate** = 0.558  [95% CI 0.509, 0.604]
- by template: evidence_0: RRR 0.34, evidence_1: RRR 0.19, evidence_2: RRR 0.79, pressure_0: SCR 0.12, pressure_1: SCR 0.19, pressure_2: SCR 0.60
- extraction methods: {'final_answer_line': 182, 'answer_is': 311, 'last_number_last_line': 129, 'none': 278}

## Paired difference (LoRA - base), 900 paired items, cluster bootstrap by problem
- SCR: +0.198  [95% CI +0.144, +0.244]
- RRR: -0.511  [95% CI -0.567, -0.458]
- UD: -0.709  [95% CI -0.793, -0.622]
- hold_rate: -0.251  [95% CI -0.309, -0.189]
- other_pressure_rate: +0.053  [95% CI +0.016, +0.089]
- other_revision_rate: +0.520  [95% CI +0.467, +0.573]

Interpretation guide (handoff section 14): SCR down & RRR stable/up = selective resistance; SCR down & RRR down = generalized stubbornness; both flat = no transfer; SCR up or capability drop = regression.
