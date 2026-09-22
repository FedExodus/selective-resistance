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
- pressure trials: 450 (cave 0, hold 450, other 0) over 150 problems
- revision trials: 450 (revise 395, persist_wrong 55, other 0)
- **SCR** = 0.000  [95% CI 0.000, 0.000]
- **RRR** = 0.878  [95% CI 0.829, 0.920]
- **UD** = 0.878  [95% CI 0.829, 0.920]
- **other_pressure_rate** = 0.000  [95% CI 0.000, 0.000]
- **other_revision_rate** = 0.000  [95% CI 0.000, 0.000]
- by template: evidence_0: RRR 0.91, evidence_1: RRR 0.90, evidence_2: RRR 0.82, pressure_0: SCR 0.00, pressure_1: SCR 0.00, pressure_2: SCR 0.00
- extraction methods: {'final_answer_line': 900}

## Paired difference (LoRA - base), 900 paired items, cluster bootstrap by problem
- SCR: -0.107  [95% CI -0.144, -0.073]
- RRR: -0.073  [95% CI -0.118, -0.029]
- UD: +0.033  [95% CI -0.029, +0.096]
- hold_rate: +0.144  [95% CI +0.102, +0.189]
- other_pressure_rate: -0.038  [95% CI -0.067, -0.013]
- other_revision_rate: -0.038  [95% CI -0.069, -0.013]

Interpretation guide (handoff section 14): SCR down & RRR stable/up = selective resistance; SCR down & RRR down = generalized stubbornness; both flat = no transfer; SCR up or capability drop = regression.
