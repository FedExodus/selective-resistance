# Analysis (mcq)

## base
- n 200  accuracy **0.695** [95% CI 0.630, 0.755]  (other/unparsed 5)
- by subject: anatomy: 0.62, business_ethics: 0.80, high_school_us_history: 0.93, philosophy: 0.75, professional_law: 0.38
- extraction methods: {'n/a': 200}

## lora
- n 200  accuracy **0.700** [95% CI 0.635, 0.760]  (other/unparsed 0)
- by subject: anatomy: 0.68, business_ethics: 0.85, high_school_us_history: 0.93, philosophy: 0.70, professional_law: 0.35
- extraction methods: {'n/a': 200}

## Paired difference (LoRA - base), 200 paired items, cluster bootstrap by problem
- accuracy: +0.005  [95% CI -0.040, +0.050]

Interpretation guide (handoff section 14): SCR down & RRR stable/up = selective resistance; SCR down & RRR down = generalized stubbornness; both flat = no transfer; SCR up or capability drop = regression.
