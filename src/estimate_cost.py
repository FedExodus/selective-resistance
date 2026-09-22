"""Token and cost estimate for the whole study (training + evaluation), from real tokenisation.

Prices: Qwen/Qwen3-8B on Tinker, USD per 1M tokens, from tinker-docs.thinkingmachines.ai/tinker/models/
(checked 2026-09-08): prefill 0.195, cached 0.039, sample 0.60, train 0.44.  Re-check before running.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, CONFIGS, ROOT, read_jsonl, write_json  # noqa: E402
from run_tinker_sft import load_cfg, token_audit  # noqa: E402
from tinker_sampler import DecodingConfig, PromptBuilder  # noqa: E402

PRICES = {"prefill": 0.195, "cached": 0.039, "sample": 0.60, "train": 0.44, "checked": "2026-09-08"}


def eval_estimate(items_path: Path, pb: PromptBuilder, max_tokens: int, assumed_output_tokens: int) -> dict:
    items = read_jsonl(items_path)
    prompt_tokens = sum(pb.build(it["messages"]).length for it in items)
    upper = prompt_tokens / 1e6 * PRICES["prefill"] + len(items) * max_tokens / 1e6 * PRICES["sample"]
    typical = prompt_tokens / 1e6 * PRICES["prefill"] + len(items) * assumed_output_tokens / 1e6 * PRICES["sample"]
    return {"items": len(items), "prompt_tokens": prompt_tokens, "per_condition_usd_upper_bound": round(upper, 3), "per_condition_usd_typical": round(typical, 3), "assumed_output_tokens": assumed_output_tokens, "max_tokens": max_tokens}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assumed-output-tokens", type=int, default=350)
    args = ap.parse_args()
    ev = yaml.safe_load(open(CONFIGS / "eval.yaml"))
    pb = PromptBuilder(DecodingConfig(**{k: ev[k] for k in DecodingConfig.__dataclass_fields__ if k in ev}))
    out = {"prices_usd_per_M": PRICES, "training": {}, "evaluation": {}}
    for name in ("train_pilot", "train_full"):
        cfg = load_cfg(str(CONFIGS / f"{name}.yaml"))
        a = token_audit(cfg)
        out["training"][name] = {"train_examples": a["train"]["n_examples"], "train_dialogues": a["train"]["n_dialogues"], "tokens_per_epoch": a["train"]["tokens_total"], "max_example_tokens": a["train"]["tokens_max"], **a["plan"]}
    for f in sorted((ARTIFACTS / "eval_items").glob("*_items_v*.jsonl")):
        out["evaluation"][f.stem] = eval_estimate(f, pb, ev["max_tokens"], args.assumed_output_tokens)
    per_cond = sum(v["per_condition_usd_typical"] for v in out["evaluation"].values())
    out["totals_usd"] = {
        "pilot_training": out["training"]["train_pilot"]["est_train_cost_usd"],
        "full_training": out["training"]["train_full"]["est_train_cost_usd"],
        "evaluation_two_conditions_typical": round(2 * per_cond, 3),
        "evaluation_two_conditions_upper_bound": round(2 * sum(v["per_condition_usd_upper_bound"] for v in out["evaluation"].values()), 3),
    }
    out["totals_usd"]["study_typical"] = round(out["totals_usd"]["pilot_training"] + out["totals_usd"]["full_training"] + out["totals_usd"]["evaluation_two_conditions_typical"], 2)
    write_json(ARTIFACTS / "audits" / "cost_estimate.json", out)
    md = ["# Cost estimate (USD)", "", f"Prices per 1M tokens (checked {PRICES['checked']}): prefill {PRICES['prefill']}, sample {PRICES['sample']}, train {PRICES['train']}.", ""]
    md.append("| run | dialogues | examples | tokens/epoch | steps | train tokens | est. cost |")
    md.append("|---|---|---|---|---|---|---|")
    for k, v in out["training"].items():
        md.append(f"| {k} | {v['train_dialogues']} | {v['train_examples']} | {v['tokens_per_epoch']:,} | {v['total_steps']} | {v['train_tokens_processed']:,} | ${v['est_train_cost_usd']:.2f} |")
    md += ["", "| eval set | items | prompt tokens | per condition (typical) | per condition (upper) |", "|---|---|---|---|---|"]
    for k, v in out["evaluation"].items():
        md.append(f"| {k} | {v['items']} | {v['prompt_tokens']:,} | ${v['per_condition_usd_typical']:.2f} | ${v['per_condition_usd_upper_bound']:.2f} |")
    t = out["totals_usd"]
    md += ["", f"**Study total (typical): ${t['study_typical']:.2f}**  = pilot ${t['pilot_training']:.2f} + full ${t['full_training']:.2f} + eval x2 ${t['evaluation_two_conditions_typical']:.2f} (eval upper bound ${t['evaluation_two_conditions_upper_bound']:.2f})", ""]
    (ARTIFACTS / "audits" / "cost_estimate.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
