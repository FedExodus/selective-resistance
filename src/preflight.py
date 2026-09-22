"""Fail-fast Tinker preflight: is the key accepted, is the account funded, is the base model served?

    python src/preflight.py                 # exit 0 only if Qwen/Qwen3-8B is served and the account is not billing-blocked

The SDK's ``get_server_capabilities()`` retries a 402 (billing block) forever, which looks like a
hang.  This script makes one raw request with a timeout and reports the HTTP status and message
instead.  The key is read from ``TINKER_API_KEY`` and never printed.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

BASE = os.environ.get("TINKER_BASE_URL") or "https://tinker.thinkingmachines.dev/services/tinker-prod"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()
    key = os.environ.get("TINKER_API_KEY")
    if not key:
        print("TINKER_API_KEY is not set")
        return 2
    try:
        r = httpx.get(f"{BASE}/api/v1/get_server_capabilities", headers={"X-Api-Key": key}, timeout=args.timeout)
    except httpx.HTTPError as e:
        print(f"network error: {type(e).__name__}: {e}".replace(key, "<REDACTED>"))
        return 3
    body = r.text.replace(key, "<REDACTED>")
    if r.status_code == 402:
        print(f"HTTP 402 Payment Required: {body}")
        return 4
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {body[:500]}")
        return 5
    models = [m.get("model_name") for m in r.json().get("supported_models", [])]
    served = args.model in models
    print(f"{len(models)} models served; {args.model} served: {served}")
    print("Qwen3 family:", [m for m in models if m and "Qwen3" in m])
    return 0 if served else 6


if __name__ == "__main__":
    sys.exit(main())
