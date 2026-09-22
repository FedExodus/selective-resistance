# Analysis (mcq)

## base
- n 200  accuracy **0.695** [95% CI 0.630, 0.755]  (other/unparsed 5)
- by subject: anatomy: 0.62, business_ethics: 0.80, high_school_us_history: 0.93, philosophy: 0.75, professional_law: 0.38
- extraction methods: {'n/a': 200}

## lora
- n 200  accuracy **0.195** [95% CI 0.145, 0.250]  (other/unparsed 158)
- by subject: anatomy: 0.17, business_ethics: 0.25, high_school_us_history: 0.03, philosophy: 0.45, professional_law: 0.07
- extraction methods: {'n/a': 200}

## Paired difference (LoRA - base), 200 paired items, cluster bootstrap by problem
- accuracy: -0.500  [95% CI -0.570, -0.425]

Interpretation guide (handoff section 14): SCR down & RRR stable/up = selective resistance; SCR down & RRR down = generalized stubbornness; both flat = no transfer; SCR up or capability drop = regression.
