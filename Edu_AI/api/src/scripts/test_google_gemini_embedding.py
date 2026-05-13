"""
测试 Google 官方 API Key 是否可用 gemini-embedding-2-preview。

用法（PowerShell）：
  cd Edu_AI/api/src
  $env:GOOGLE_API_KEY="你的key"
  python scripts/test_google_gemini_embedding.py

可选环境变量：
  - GEMINI_EMBED_MODEL（默认: gemini-embedding-2-preview）
  - GEMINI_OPENAI_BASE（默认: https://generativelanguage.googleapis.com/v1beta/openai）
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

import requests


def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return "(empty)"
    if len(s) <= keep * 2:
        return "*" * len(s)
    return f"{s[:keep]}...{s[-keep:]}"


def _print_json_safe(obj: Any, limit: int = 4000) -> None:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        text = str(obj)
    print(text[:limit])


def _test_openai_compatible(api_key: str, model: str, base: str) -> int:
    url = base.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model,
        "input": [
            "hello world",
            "测试 Google Gemini Embedding 接口",
        ],
    }

    print("\n[1/1] 调用 Google OpenAI-compatible embeddings")
    print(f"POST {url}")
    print(f"model={model}")

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return 1

    print(f"HTTP {resp.status_code} {resp.reason}")
    ct = resp.headers.get("content-type", "")

    if resp.status_code != 200:
        print("❌ 调用失败，返回内容：")
        if "application/json" in ct:
            try:
                _print_json_safe(resp.json())
            except Exception:
                print(resp.text[:4000])
        else:
            print(resp.text[:4000])
        return 1

    try:
        data = resp.json()
    except Exception:
        print("❌ 返回不是 JSON：")
        print(resp.text[:2000])
        return 1

    items: List[Dict[str, Any]] = data.get("data") or []
    if not items:
        print("❌ 返回 data 为空：")
        _print_json_safe(data)
        return 1

    first = items[0].get("embedding") if isinstance(items[0], dict) else None
    if not isinstance(first, list) or not first:
        print("❌ embedding 向量为空或格式异常：")
        _print_json_safe(data)
        return 1

    print("✅ 调用成功")
    print(f"- 向量条数: {len(items)}")
    print(f"- 向量维度: {len(first)}")
    print(f"- 首条前5项: {first[:5]}")
    usage = data.get("usage")
    if usage:
        print(f"- usage: {usage}")

    return 0


def main() -> int:
    api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    model = (os.getenv("GEMINI_EMBED_MODEL") or "gemini-embedding-2-preview").strip()
    base = (os.getenv("GEMINI_OPENAI_BASE") or "https://generativelanguage.googleapis.com/v1beta/openai").strip()

    print("=== Google Gemini Embedding Key 测试 ===")
    print(f"GOOGLE_API_KEY: {_mask(api_key)}")
    print(f"GEMINI_EMBED_MODEL: {model}")
    print(f"GEMINI_OPENAI_BASE: {base}")

    if not api_key:
        print("\n❌ 未设置 GOOGLE_API_KEY")
        return 2

    code = _test_openai_compatible(api_key, model, base)
    if code == 0:
        return 0

    print("\n排查建议：")
    print("1) 401/403：API Key 无效或无权限")
    print("2) 404：base 地址不对（确认是 v1beta/openai）")
    print("3) 400 model not found：当前 key/区域未开通 gemini-embedding-2-preview")
    print("4) 429：限流，稍后重试")
    return code


if __name__ == "__main__":
    sys.exit(main())
