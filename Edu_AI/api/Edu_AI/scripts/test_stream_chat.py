r"""Simple streaming chat test script.

Usage (PowerShell):
  $env:API_BASE="https://api.deepseek.com"  # base, without /v1
  $env:API_KEY="your-key"
  $env:MODEL_NAME="your-model"
  python .\scripts\test_stream_chat.py "你好，介绍一下你自己"

Fallback envs used if API_BASE/MODEL_NAME are not set:
  REMOTE_MODEL_API_BASE, REMOTE_MODEL_API_KEY, LLM_MODEL

This script prints tokens as they arrive to verify streaming support.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import Config


def build_api_base(raw_base: str) -> str:
    base = (raw_base or "").rstrip("/")
    if not base:
        raise RuntimeError("API_BASE is required")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def stream_chat(
    api_base: str,
    api_key: str | None,
    model_name: str,
    messages: List[Dict[str, str]],
) -> None:
    url = f"{api_base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 800,
        "stream": True,
    }

    resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

    print("\n--- streaming start ---\n")
    start_time = time.time()
    first_token_time = None
    token_count = 0

    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if line.startswith("data:"):
            line = line[len("data:") :].strip()
        if line == "[DONE]":
            break
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        choices = data.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if not content:
            continue
        if first_token_time is None:
            first_token_time = time.time()
        token_count += 1
        elapsed_ms = (time.time() - start_time) * 1000
        print(f"\n[{elapsed_ms:8.1f}ms] raw_len={len(raw_line)}", flush=True)
        print(content, end="", flush=True)

    total_time = time.time() - start_time
    ttfb = (first_token_time - start_time) if first_token_time else None
    print("\n\n--- streaming end ---")
    print(f"tokens: {token_count}")
    print(f"total_time: {total_time:.2f}s")
    if ttfb is not None:
        print(f"time_to_first_token: {ttfb:.2f}s")


def main() -> None:
    model_cfg = Config.get_llm_model(Config.DEFAULT_LLM_MODEL_ID)
    api_base_env = str(model_cfg.get("api_base") or Config.REMOTE_MODEL_API_BASE or "").strip()
    api_key = model_cfg.get("api_key") or Config.REMOTE_MODEL_API_KEY
    model_name = str(model_cfg.get("model_name") or Config.LLM_MODEL or "").strip()

    if not api_base_env or not model_name:
        raise RuntimeError("Config is missing api_base/model_name for the default model")

    question = " ".join(sys.argv[1:]).strip() or "请用三句话介绍一下你自己。"
    api_base = build_api_base(api_base_env)

    print("\n--- using model config ---")
    print(f"api_base: {api_base}")
    print(f"model_name: {model_name}")
    print(f"api_key: {'set' if api_key else 'not set'}")
    print(f"model_id: {Config.DEFAULT_LLM_MODEL_ID}")
    print("--------------------------\n")

    messages = [
        {"role": "system", "content": "你是一个友好的助手。"},
        {"role": "user", "content": question},
    ]

    stream_chat(api_base=api_base, api_key=api_key, model_name=model_name, messages=messages)


if __name__ == "__main__":
    main()
