"""Thin, deterministic sampling wrapper over the Tinker SDK used by every evaluation script.

Base and LoRA conditions go through exactly this code path with exactly the same renderer,
decoding parameters, stop sequences and parsing.  Only ``model_path`` differs.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
from dataclasses import dataclass

from tinker_cookbook.renderers import get_renderer, get_text_content
from tinker_cookbook.tokenizer_utils import get_tokenizer


def versions() -> dict:
    out = {}
    for pkg in ("tinker", "tinker-cookbook", "transformers", "datasets"):
        try:
            out[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            out[pkg] = None
    return out


@dataclass
class DecodingConfig:
    base_model: str
    renderer_name: str
    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = -1
    max_tokens: int = 768
    seed: int = 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class PromptBuilder:
    """Tokenizer + renderer only; no network beyond the HF tokenizer download."""

    def __init__(self, cfg: DecodingConfig):
        self.cfg = cfg
        self.tokenizer = get_tokenizer(cfg.base_model)
        self.renderer = get_renderer(cfg.renderer_name, self.tokenizer)

    def build(self, messages: list[dict]):
        return self.renderer.build_generation_prompt(messages)

    def prompt_text(self, messages: list[dict]) -> str:
        return self.tokenizer.decode(self.build(messages).to_ints())


class Sampler(PromptBuilder):
    def __init__(self, cfg: DecodingConfig, model_path: str | None = None, max_retries: int = 4):
        super().__init__(cfg)
        import tinker

        if not os.environ.get("TINKER_API_KEY"):
            raise SystemExit("TINKER_API_KEY is not set (never put it in a config file).")
        self.tinker = tinker
        self.model_path = model_path
        self.service = tinker.ServiceClient()
        if model_path:
            self.client = self.service.create_sampling_client(model_path=model_path)
        else:
            self.client = self.service.create_sampling_client(base_model=cfg.base_model)
        self.max_retries = max_retries
        self.stop = self.renderer.get_stop_sequences()

    def sampling_params(self):
        c = self.cfg
        return self.tinker.SamplingParams(
            temperature=c.temperature, top_p=c.top_p, top_k=c.top_k, max_tokens=c.max_tokens, seed=c.seed, stop=self.stop
        )

    async def complete(self, messages: list[dict]) -> dict:
        prompt = self.build(messages)
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self.client.sample_async(prompt=prompt, num_samples=1, sampling_params=self.sampling_params())
                break
            except Exception as e:  # noqa: BLE001 - surface after retries
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        seq = resp.sequences[0]
        msg, termination = self.renderer.parse_response(list(seq.tokens))
        text = get_text_content(msg)
        parts = msg.get("content")
        thinking = None
        if isinstance(parts, list):
            thinking = "".join(p.get("thinking", "") for p in parts if isinstance(p, dict) and p.get("type") == "thinking") or None
        return {
            "text": text,
            "thinking": thinking,
            "raw_decoded": self.tokenizer.decode(list(seq.tokens)),
            "n_prompt_tokens": prompt.length,
            "n_output_tokens": len(seq.tokens),
            "stop_reason": str(getattr(seq, "stop_reason", "")),
            "termination": str(termination),
        }
