# Analysis (mcq)

## base
- n 200  accuracy **0.695** [95% CI 0.630, 0.755]  (other/unparsed 5)
- by subject: anatomy: 0.62, business_ethics: 0.80, high_school_us_history: 0.93, philosophy: 0.75, professional_law: 0.38
- extraction methods: {'n/a': 200}

## lora
- n 200  accuracy **0.340** [95% CI 0.275, 0.410]  (other/unparsed 67)
- by subject: anatomy: 0.50, business_ethics: 0.42, high_school_us_history: 0.33, philosophy: 0.35, professional_law: 0.10
- extraction methods: {'n/a': 200}

## Paired difference (LoRA - base), 200 paired items, cluster bootstrap by problem
- accuracy: -0.355  [95% CI -0.430, -0.275]

Interpretation guide (handoff section 14): SCR down & RRR stable/up = selective resistance; SCR down & RRR down = generalized stubbornness; both flat = no transfer; SCR up or capability drop = regression.
