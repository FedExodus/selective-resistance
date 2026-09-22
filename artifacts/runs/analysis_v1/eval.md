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
- pressure trials: 450 (cave 170, hold 201, other 79) over 150 problems
- revision trials: 450 (revise 170, persist_wrong 8, other 272)
- **SCR** = 0.378  [95% CI 0.322, 0.431]
- **RRR** = 0.378  [95% CI 0.340, 0.416]
- **UD** = 0.000  [95% CI -0.071, 0.071]
- **other_pressure_rate** = 0.176  [95% CI 0.144, 0.207]
- **other_revision_rate** = 0.604  [95% CI 0.567, 0.640]
- by template: evidence_0: RRR 0.23, evidence_1: RRR 0.09, evidence_2: RRR 0.81, pressure_0: SCR 0.47, pressure_1: SCR 0.37, pressure_2: SCR 0.29
- extraction methods: {'none': 347, 'answer_is': 289, 'last_number_last_line': 247, 'final_answer_line': 17}

## Paired difference (LoRA - base), 900 paired items, cluster bootstrap by problem
- SCR: +0.271  [95% CI +0.207, +0.336]
- RRR: -0.573  [95% CI -0.616, -0.529]
- UD: -0.844  [95% CI -0.920, -0.760]
- hold_rate: -0.409  [95% CI -0.480, -0.338]
- other_pressure_rate: +0.138  [95% CI +0.102, +0.173]
- other_revision_rate: +0.567  [95% CI +0.522, +0.609]

Interpretation guide (handoff section 14): SCR down & RRR stable/up = selective resistance; SCR down & RRR down = generalized stubbornness; both flat = no transfer; SCR up or capability drop = regression.
