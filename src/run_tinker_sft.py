"""LoRA supervised fine-tuning on Tinker via the cookbook's ``supervised.train`` loop.

    python src/run_tinker_sft.py --config configs/train_pilot.yaml --dry-run   # tokenise, count, cost; no API
    python src/run_tinker_sft.py --config configs/train_pilot.yaml             # needs TINKER_API_KEY

The YAML is the run's source of truth and is copied into the run manifest together with the
data file hashes, package versions and every checkpoint path.  Refuses to run if any example
exceeds ``max_length`` unless ``allow_truncation: true`` (no silent truncation).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, ROOT, read_jsonl, sha256_file, write_json  # noqa: E402
from tinker_sampler import versions  # noqa: E402

PRICE_TRAIN_PER_M = 0.44  # USD per 1M tokens, Qwen/Qwen3-8B training, tinker-docs models page, checked 2026-09-08


def load_cfg(path: str) -> dict:
    cfg = yaml.safe_load(open(path))
    for k in ("train_path", "val_path", "log_path"):
        if cfg.get(k):
            cfg[k] = str((ROOT / cfg[k]).resolve()) if not Path(cfg[k]).is_absolute() else cfg[k]
    return cfg


def select_rows(rows: list[dict], pilot_n: int | None, seed: int) -> list[dict]:
    if not pilot_n:
        return rows
    dialogue_ids = sorted({r["meta"]["row_id"] for r in rows})
    rng = random.Random(seed)
    keep = set(rng.sample(dialogue_ids, min(pilot_n, len(dialogue_ids))))
    return [r for r in rows if r["meta"]["row_id"] in keep]


def make_builder(cfg: dict):
    import chz
    import datasets
    from tinker_cookbook.renderers import TrainOnWhat
    from tinker_cookbook.supervised.data import SupervisedDatasetFromHFDataset, conversation_to_datum
    from tinker_cookbook.supervised.types import ChatDatasetBuilder, ChatDatasetBuilderCommonConfig

    @chz.chz
    class JsonlSplitBuilder(ChatDatasetBuilder):
        train_path: str
        val_path: str | None
        pilot_n_dialogues: int | None
        pilot_seed: int

        def __call__(self):
            train_on_what = TrainOnWhat(self.common_config.train_on_what) if self.common_config.train_on_what else TrainOnWhat.LAST_ASSISTANT_MESSAGE
            renderer, max_len = self.renderer, self.common_config.max_length

            def map_fn(row):
                return conversation_to_datum(row["messages"], renderer, max_len, train_on_what)

            train_rows = select_rows(read_jsonl(Path(self.train_path)), self.pilot_n_dialogues, self.pilot_seed)
            train_ds = datasets.Dataset.from_list([{"messages": r["messages"]} for r in train_rows])
            train = SupervisedDatasetFromHFDataset(train_ds, batch_size=self.common_config.batch_size, map_fn=map_fn)
            val = None
            if self.val_path:
                val_rows = read_jsonl(Path(self.val_path))
                if self.pilot_n_dialogues:
                    val_rows = select_rows(val_rows, max(8, self.pilot_n_dialogues // 10), self.pilot_seed)
                val_ds = datasets.Dataset.from_list([{"messages": r["messages"]} for r in val_rows])
                val = SupervisedDatasetFromHFDataset(val_ds, batch_size=len(val_ds), map_fn=map_fn)
            return train, val

    common = ChatDatasetBuilderCommonConfig(
        model_name_for_tokenizer=cfg["model_name"],
        renderer_name=cfg["renderer_name"],
        max_length=cfg["max_length"],
        batch_size=cfg["batch_size"],
        train_on_what=TrainOnWhat(cfg["train_on_what"]),
    )
    return JsonlSplitBuilder(common_config=common, train_path=cfg["train_path"], val_path=cfg.get("val_path"), pilot_n_dialogues=cfg.get("pilot_n_dialogues"), pilot_seed=cfg.get("pilot_seed", 0))


def token_audit(cfg: dict) -> dict:
    """Tokenise every selected example with the real renderer; report lengths, overflow and steps."""
    from tinker_cookbook.renderers import TrainOnWhat, get_renderer
    from tinker_cookbook.tokenizer_utils import get_tokenizer

    tok = get_tokenizer(cfg["model_name"])
    renderer = get_renderer(cfg["renderer_name"], tok)
    tow = TrainOnWhat(cfg["train_on_what"])
    out = {}
    for split, path in (("train", cfg["train_path"]), ("val", cfg.get("val_path"))):
        if not path:
            continue
        rows = read_jsonl(Path(path))
        if cfg.get("pilot_n_dialogues"):
            rows = select_rows(rows, cfg["pilot_n_dialogues"] if split == "train" else max(8, cfg["pilot_n_dialogues"] // 10), cfg.get("pilot_seed", 0))
        lens, wsum = [], 0
        for r in rows:
            mi, w = renderer.build_supervised_example(r["messages"], train_on_what=tow)
            lens.append(mi.length)
            wsum += int(sum(1 for x in w if x > 0))
        over = sum(1 for n in lens if n > cfg["max_length"])
        out[split] = {"n_examples": len(rows), "n_dialogues": len({r["meta"]["row_id"] for r in rows}), "tokens_total": sum(lens), "tokens_max": max(lens) if lens else 0, "loss_tokens_total": wsum, "examples_over_max_length": over}
    n_batches = out["train"]["n_examples"] // cfg["batch_size"]
    steps = n_batches * cfg["num_epochs"]
    if cfg.get("max_steps"):
        steps = min(steps, cfg["max_steps"])
    train_tokens = out["train"]["tokens_total"] * cfg["num_epochs"] * (steps / max(1, n_batches * cfg["num_epochs"]))
    out["plan"] = {"batches_per_epoch": n_batches, "total_steps": steps, "train_tokens_processed": int(train_tokens), "est_train_cost_usd": round(train_tokens / 1e6 * PRICE_TRAIN_PER_M, 3), "price_train_per_M": PRICE_TRAIN_PER_M}
    return out


async def train_main(cfg: dict, run_name: str, resume: bool = False) -> None:
    import os

    from tinker_cookbook import checkpoint_utils, cli_utils
    from tinker_cookbook.supervised import train

    if not os.environ.get("TINKER_API_KEY"):
        raise SystemExit("TINKER_API_KEY is not set (never put it in a config file).")
    # "resume" picks up from the last state_path in <log_path>/checkpoints.jsonl (same seeded batch order, same LR schedule by step)
    cli_utils.check_log_dir(cfg["log_path"], behavior_if_exists="resume" if resume else "raise")
    config = train.Config(
        log_path=cfg["log_path"],
        model_name=cfg["model_name"],
        recipe_name="bluedot_mathdial_sft",
        renderer_name=cfg["renderer_name"],
        dataset_builder=make_builder(cfg),
        learning_rate=float(cfg["learning_rate"]),
        lr_schedule=cfg["lr_schedule"],
        num_epochs=int(cfg["num_epochs"]),
        lora_rank=int(cfg["lora_rank"]),
        save_every=int(cfg.get("save_every", 0)),
        eval_every=int(cfg.get("eval_every", 0)),
        max_steps=cfg.get("max_steps"),
    )
    await train.main(config)
    records = checkpoint_utils.load_checkpoints_file(cfg["log_path"])
    ckpts = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in records]
    manifest = {
        "run_name": run_name,
        "config": cfg,
        "versions": versions(),
        "data": {k: {"path": cfg[k], "sha256": sha256_file(Path(cfg[k]))} for k in ("train_path", "val_path") if cfg.get(k)},
        "checkpoints": ckpts,
        "resumed": resume,
        "finished": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    out = ARTIFACTS / "runs" / run_name / "train_manifest.json"
    write_json(out, manifest)
    final = [c for c in ckpts if c.get("sampler_path")]
    print(f"\nwrote {out}")
    if final:
        print(f"final sampler weights: {final[-1]['sampler_path']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted run from its last saved checkpoint in log_path")
    args = ap.parse_args()
    cfg = load_cfg(args.config)
    run_name = args.run_name or Path(args.config).stem
    audit = token_audit(cfg)
    print(json.dumps(audit, indent=1))
    if audit["train"]["examples_over_max_length"] and not cfg.get("allow_truncation"):
        raise SystemExit(f"{audit['train']['examples_over_max_length']} training examples exceed max_length={cfg['max_length']}; raise max_length or set allow_truncation: true explicitly.")
    write_json(ARTIFACTS / "runs" / run_name / "token_audit.json", {"config": cfg, "audit": audit, "versions": versions()})
    if args.dry_run:
        print("dry run only; no training launched")
        return
    asyncio.run(train_main(cfg, run_name, resume=args.resume))


if __name__ == "__main__":
    main()
