# MathDial data audit

## Official train split (raw)
- rows 2262, unique qids 1035, qids with >1 dialogue 755, exact duplicate conversations 0
- missing fields: {'teacher_described_confusion': 9, 'self-correctness': 9, 'self-typical-confusion': 9, 'self-typical-interactions': 9}; malformed conversations: 1
- turns per dialogue: {'p50': 11.0, 'p90': 20.0, 'p95': 22.0, 'p99': 29.0, 'min': 4.0, 'max': 54.0, 'mean': 12.497125165855817}
- teacher dialogue acts: {'probing': 3289, 'generic': 3539, 'telling': 2487, 'focus': 5535}
- self-correctness: {'Yes': 1696, 'No': 254, 'Yes, but I had to reveal the answer': 303, 'None': 9}

## Official test split (raw)
- rows 599, unique qids 394, qids with >1 dialogue 90, exact duplicate conversations 0
- missing fields: {'teacher_described_confusion': 4, 'self-correctness': 4, 'self-typical-confusion': 4, 'self-typical-interactions': 4}; malformed conversations: 0
- turns per dialogue: {'p50': 11.0, 'p90': 20.0, 'p95': 20.0, 'p99': 26.0, 'min': 4.0, 'max': 46.0, 'mean': 11.71118530884808}
- teacher dialogue acts: {'generic': 890, 'focus': 1252, 'telling': 597, 'probing': 947}
- self-correctness: {'Yes': 433, 'Yes, but I had to reveal the answer': 94, 'No': 68, 'None': 4}

## Processed SFT files
- dialogues.jsonl: {'n_rows': 2861, 'sha256': '6d3237c6d28d1bdb72772da5cb397a3a782ca52bf16279a78884b30bfa3c5772'}
- sft_train.jsonl: {'n_rows': 13076, 'sha256': '4dfcb7686b1dff783e7bd568775697e9845c568cbb57ddcb8c46b97ed863f56e'}
- sft_train_full.jsonl: {'n_rows': 2042, 'sha256': 'ba5eb1393fd4b6241268c60be3ae8673a3708b1eb9fff6e0215ee1a47b2d4722'}
- sft_val.jsonl: {'n_rows': 1367, 'sha256': '8331038ed4343bf71fee0e22ef4931bcaec2e1f29e50a04357949c64437d04ab'}
- sft_val_full.jsonl: {'n_rows': 219, 'sha256': 'e3e0f593005a95c5457d5c2c1e88f4958810a15da5c74ed012aeb4d1d7805f58'}

## Token lengths (Qwen/Qwen3-8B, renderer qwen3_disable_thinking)
- **sft_train.jsonl** (last_assistant_message): n 13076, sequence tokens {'p50': 478.0, 'p90': 892.0, 'p95': 1058.0, 'p99': 1462.0, 'min': 149.0, 'max': 2495.0, 'mean': 535.7737075558275}, loss tokens {'p50': 17.0, 'p90': 41.0, 'p95': 50.0, 'p99': 77.0, 'min': 2.0, 'max': 380.0, 'mean': 21.541832364637504}, total 7,005,777, >2048: 9, >4096: 0
- **sft_val.jsonl** (last_assistant_message): n 1367, sequence tokens {'p50': 486.0, 'p90': 869.0, 'p95': 1022.0, 'p99': 1350.0, 'min': 155.0, 'max': 1839.0, 'mean': 534.037307973665}, loss tokens {'p50': 18.0, 'p90': 39.0, 'p95': 47.0, 'p99': 65.0, 'min': 2.0, 'max': 185.0, 'mean': 21.174103877103146}, total 730,029, >2048: 0, >4096: 0
- **sft_train_full.jsonl** (all_assistant_messages): n 2042, sequence tokens {'p50': 648.0, 'p90': 1096.0, 'p95': 1268.0, 'p99': 1665.0, 'min': 229.0, 'max': 2495.0, 'mean': 708.3192948090108}, loss tokens {'p50': 123.0, 'p90': 253.0, 'p95': 304.0, 'p99': 413.0, 'min': 17.0, 'max': 847.0, 'mean': 141.94368266405485}, total 1,446,388, >2048: 2, >4096: 0

## Exclusion checks
- train_val_qid_overlap: 0
- official_test_rows_in_sft_files: 0
- sft_examples_not_from_official_train: 0
- train_qids_also_in_official_test_split (allowed; different dialogues): 280
- val_qids_also_in_official_test_split (allowed): 38
- eval_items_v1.jsonl: items whose problem text appears in the fine-tuning split: 0
- eval_items_v1.jsonl: n_items: 900
- privileged_fields_checked: ['ground_truth', 'teacher_described_confusion', 'self-correctness', 'self-typical-confusion', 'self-typical-interactions']
- ground_truth_text_in_sft_messages: 0

## Preprocess counts
```json
{
 "dialogue_acts_teacher_turns": {
  "focus": 5535,
  "generic": 3539,
  "probing": 3289,
  "telling": 2487
 },
 "dialogues_ending_with_student_turn": 1220,
 "dialogues_train": 2042,
 "dialogues_val": 219,
 "malformed_conversations": 1,
 "merged_same_role_turns": 411,
 "official_test_rows": 599,
 "official_train_rows": 2262,
 "parse": {
  "empty_turn_body": 55,
  "teacher_turn_without_act": 2
 },
 "qids_in_both_official_splits": 318,
 "test_only_qids": 76,
 "unique_test_qids": 394,
 "unique_train_qids": 1035,
 "val_qids": 104
}
```

## Parsed examples (per-turn format; model-visible text only)
### train:00001 turn 0 acts ['probing']
- **user**: Here is the problem I'm working on: /  / John is very unfit and decides to work up to doing a push-up.  He trains 5 days a week for them and starts with wall push-ups.  He adds 1 rep a day and once he gets to 15 reps he will start training high elevation push-ups. and then low elevation push-ups, and finally floor push-ups.  How many weeks will it take him to get to floor push-ups? /  / Here is my solutio
- **assistant**: Stephanie, How many days will it take to do one step, if John adds one pushup per day?

### train:00589 turn 0 acts ['probing']
- **user**: Here is the problem I'm working on: /  / Kathryn moved to a new city for the new job she had landed two weeks ago. Her rent was $1200, 1/2 of what she spent on food and travel expenses in a month. Luckily, she found a new friend Shelby, who moved in with her to share the rent. If her salary was $5000 per month, how much money remained after her expenses? /  / Here is my solution: /  / Kathryn spent 2 x $1200 
- **assistant**: Does Shelby share Kathryn's food and travel expenses?

### train:01133 turn 3 acts ['telling']
- **user**: Here is the problem I'm working on: /  / The gauge on a water tank shows that the tank is 1/3 full of water. To fill the tank, 16 gallons of water are added. How many gallons of water does the tank hold when full? /  / Here is my solution: /  / Let's first find out how much water was already in the tank before 16 gallons were added.  /  / If the tank was 1/3 full before, that means it was already filled with 2/3 
- **assistant**: Hey Luca, talk me through this part of your solution If the tank was 1/3 full before, that means it was already filled with 2/3 of its capacity.
- **user**: Sure. Since the tank was 1/3 full before, that means it was already filled with 2/3 of its capacity. So if the tank was 2/3 full, then the full capacity of the tank would be 3 times the amount of water that was already in the tank. That's why I set up the equation 2/3x + 16 = x. I was trying to find out how much water was in the tank before 16 gallons were added, which would be the full capacity o
- **assistant**: How can the tank be both 1/3 full and 2/3 of it's full capacity? how many parts would is there needed to fill the tank?
- **user**: Oh, I see what you mean. The tank can be both 1/3 full and 2/3 of its full capacity because 1/3 of the tank is the same as 2/3 of the full capacity. So, to fill the tank, there would be 3 parts needed: 1/3 of the tank already filled with water, 1/3 of the tank to be filled with 16 gallons of water, and the remaining 1/3 of the tank to be filled with the remaining amount of water to reach the full 
- **assistant**: 16 gallons fills the tank completely, so 16 gallons is 2/3rds
- **user**: Yes, that's right. 16 gallons fills the tank completely, so 16 gallons is 2/3rds of the full capacity of the tank. That's why I set up the equation 2/3x + 16 = x. I was trying to find out how much water was in the tank before 16 gallons were added, which would be the full capacity of the tank.
- **assistant**: So if 2/3rds = 16 gallons how much does 1/3rd equal?

### train:01705 turn 3 acts ['probing']
- **user**: Here is the problem I'm working on: /  / On March 1st the sun sets at 6 PM.  Every day after the sun sets 1.2 minutes later.  It is 6:10 PM and 40 days after March 1st.  How many minutes until the sun sets? /  / Here is my solution: /  / Since the sun sets 1.2 minutes later every day, in 40 days it will set 40 x 1.2 = 48 minutes later. / Since the sun set on March 1st at 6 PM, it will set today at 6:10 PM + 48 
- **assistant**: yo Michael tell me what you have done here?
- **user**: I started by calculating how many minutes the sun would set later after 40 days. I multiplied 1.2 minutes by 40 days, which gave me 48 minutes. Then I added 48 minutes to 6 PM and got 6:58 PM. Finally, I subtracted 6 PM from 6:58 PM and got 2 minutes.
- **assistant**: this is a fab start - i want to take it back a step or 2 to check our understanding of the problem is that ok?
- **user**: Yes, that's fine.
- **assistant**: you have correctly identified 48minutes later than it does on the 1st of March. the time we are now starting with is what?
- **user**: The time we are starting with is 6:10 PM.
- **assistant**: that is good so with 6.10pm and the 48minutes (you already have worked out correctly) - what do you think the answer would now be?

