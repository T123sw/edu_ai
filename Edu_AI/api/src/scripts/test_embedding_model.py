"""
测试 EMBEDDING_MODEL 是否可用（OpenAI-compatible /v1/embeddings）

用法：
  cd Edu_AI/api/Edu_AI
  python scripts/test_embedding_model.py

环境变量：
  - EMBEDDING_API_BASE（必填）
  - EMBEDDING_API_KEY（必填）
  - EMBEDDING_MODEL（可选，不填则尝试从 /v1/models 自动选）
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple

import requests


def _try_load_dotenv() -> None:
    """尽力加载 .env/config_openai.env，不强依赖 python-dotenv。"""
    try:
        from dotenv import load_dotenv  # type: ignore

        base_dir = Path(__file__).resolve().parents[1]  # .../api/Edu_AI
        candidates = [
            base_dir / ".env",
            base_dir / "config_openai.env",
            Path.cwd() / ".env",
        ]
        for p in candidates:
            if p.exists():
                load_dotenv(p, override=True)
    except Exception:
        return


def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return "(empty)"
    if len(s) <= keep * 2:
        return "*" * len(s)
    return f"{s[:keep]}...{s[-keep:]}"


def _join(base: str, path: str) -> str:
    return base.rstrip("/") + path


def _print_resp(resp: requests.Response) -> None:
    print(f"HTTP {resp.status_code} {resp.reason}")
    ct = resp.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            print(json.dumps(resp.json(), ensure_ascii=False, indent=2)[:4000])
        except Exception:
            print(resp.text[:4000])
    else:
        print(resp.text[:4000])


def _get_env_any(*keys: str) -> str:
    for k in keys:
        v = os.getenv(k)
        if v and v.strip():
            return v.strip()
    return ""


def _pick_model_from_models(api_base: str, api_key: str) -> Optional[str]:
    """可选步骤：调用 /v1/models 选一个 embedding 相关模型。"""
    url = _join(api_base, "/v1/models")
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        r = requests.get(url, headers=headers, timeout=20)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    try:
        data = r.json().get("data", [])
    except Exception:
        return None

    model_ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
    if not model_ids:
        return None

    # 优先选包含 embedding 字样的模型
    for mid in model_ids:
        low = str(mid).lower()
        if "embedding" in low or "embed" in low:
            return str(mid)

    # 找不到就返回第一个
    return str(model_ids[0])


def try_embeddings(api_base: str, api_key: str, model: str) -> Tuple[bool, str]:
    url = _join(api_base, "/v1/embeddings")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": [
            "hello world",
            "测试 embedding 模型是否可用",
        ],
    }

    print(f"\n[请求] POST {url} (model={model})")
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
    except Exception as e:
        return False, f"请求 embeddings 失败：{e}"

    if r.status_code != 200:
        print("embeddings 响应异常：")
        _print_resp(r)
        return False, "embeddings 调用失败（可能 token 无效/模型名不对/权限不足）"

    try:
        j = r.json()
    except Exception:
        print("返回非 JSON：")
        print(r.text[:2000])
        return False, "响应不是 JSON"

    data = j.get("data") or []
    if not data:
        print("响应内容：")
        print(json.dumps(j, ensure_ascii=False, indent=2)[:4000])
        return False, "响应中没有 data"

    first_emb = data[0].get("embedding") if isinstance(data[0], dict) else None
    if not isinstance(first_emb, list) or not first_emb:
        print("响应内容：")
        print(json.dumps(j, ensure_ascii=False, indent=2)[:4000])
        return False, "embedding 向量为空或格式异常"

    dim = len(first_emb)
    usage = j.get("usage", {})

    print("\n✅ EMBEDDING_MODEL 可用")
    print(f"- 向量维度: {dim}")
    print(f"- 返回向量条数: {len(data)}")
    if usage:
        print(f"- usage: {usage}")
    print(f"- 首条向量前 5 项: {first_emb[:5]}")

    return True, "OK"


def main() -> int:
    _try_load_dotenv()

    api_base = _get_env_any("EMBEDDING_API_BASE", "REMOTE_MODEL_API_BASE")
    api_key = _get_env_any("EMBEDDING_API_KEY", "REMOTE_MODEL_API_KEY")
    model = _get_env_any("EMBEDDING_MODEL")

    print("=== Embedding 连通性测试 ===")
    print("EMBEDDING_API_BASE:", api_base or "(empty)")
    print("EMBEDDING_API_KEY:", _mask(api_key))
    print("EMBEDDING_MODEL:", model or "(auto from /v1/models)")

    if not api_base:
        print("\n❌ 未设置 EMBEDDING_API_BASE")
        return 2
    if not api_key:
        print("\n❌ 未设置 EMBEDDING_API_KEY")
        return 2

    if not model:
        guessed = _pick_model_from_models(api_base, api_key)
        if guessed:
            model = guessed
            print(f"自动选择模型: {model}")
        else:
            print("\n❌ 未设置 EMBEDDING_MODEL，且无法从 /v1/models 自动选择")
            return 2

    ok, msg = try_embeddings(api_base, api_key, model)
    if ok:
        return 0

    print("\n❌ 测试失败：", msg)
    print("\n排查建议：")
    print("1) 401/403：检查 EMBEDDING_API_KEY 是否过期或权限不足")
    print("2) 404：检查 EMBEDDING_API_BASE 是否正确（是否需要 /v1）")
    print("3) model not found：替换 EMBEDDING_MODEL 为服务商支持的模型名")
    print("4) 连接超时：检查网络、代理、防火墙和网关可达性")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
