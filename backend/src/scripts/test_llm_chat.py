"""\
测试大模型对话能力（用于排查 token 过期 / api_base 配置错误）

特点：
- 自动加载同目录下的 .env / config_openai.env（若安装了 python-dotenv）
- 同时兼容两套环境变量命名：
    1) REMOTE_MODEL_API_BASE / REMOTE_MODEL_API_KEY
    2) REMOTE_MODEL_API_BASE / REMOTE_MODEL_API_KEY
  （你的项目 .env 当前使用的是第 2 套）

用法：
  cd backend/src
  python scripts/test_llm_chat.py

脚本会依次尝试（OpenAI 兼容）：
  1) GET  {api_base}/v1/models
  2) POST {api_base}/v1/chat/completions

注意：不会打印完整 token，只显示前后各 4 位用于确认读取成功。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests


def _try_load_dotenv() -> None:
    """尽力加载 .env/config_openai.env，不强依赖 python-dotenv。"""
    try:
        from dotenv import load_dotenv  # type: ignore

        base_dir = Path(__file__).resolve().parents[1]  # .../backend/src
        candidates = [
            base_dir / ".env",
            base_dir / "config_openai.env",
            Path.cwd() / ".env",
        ]
        for p in candidates:
            if p.exists():
                load_dotenv(p, override=True)
    except Exception:
        # 不影响主流程：没有 dotenv 就只能靠系统环境变量
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


def try_openai_compatible(api_base: str, api_key: str, model: Optional[str]) -> Tuple[bool, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    base = api_base.rstrip("/")
    has_v1 = base.endswith("/v1")

    # 1) models
    models_url = _join(base, "/models" if has_v1 else "/v1/models")
    print(f"\n[1/2] GET {models_url}")
    try:
        r = requests.get(models_url, headers=headers, timeout=20)
    except Exception as e:
        return False, f"请求 models 失败：{e}"

    if r.status_code != 200:
        print("models 响应异常：")
        _print_resp(r)
        return False, "models 接口不可用或鉴权失败"

    data = r.json()
    items = data.get("data") or []
    model_ids = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
    print(f"models 数量: {len(model_ids)}")
    if model_ids:
        print("示例 models:", model_ids[:10])

    chosen = model or (model_ids[0] if model_ids else None)
    if not chosen:
        return False, "未能从 /v1/models 获取模型列表，也未指定 LLM_MODEL"

    # 2) chat
    chat_url = _join(base, "/chat/completions" if has_v1 else "/v1/chat/completions")
    payload: Dict[str, Any] = {
        "model": chosen,
        "messages": [
            {"role": "system", "content": "你是一个简洁的助手。"},
            {"role": "user", "content": "请用一句话回答：计算思维是什么？"},
        ],
        "temperature": 0.2,
        "max_tokens": 128,
    }

    print(f"\n[2/2] POST {chat_url} (model={chosen})")
    try:
        r2 = requests.post(chat_url, headers=headers, json=payload, timeout=60)
    except Exception as e:
        return False, f"请求 chat/completions 失败：{e}"

    if r2.status_code != 200:
        print("chat/completions 响应异常：")
        _print_resp(r2)
        return False, "chat/completions 调用失败（可能 token 过期/模型名不对/权限不足）"

    j = r2.json()
    try:
        answer = j["choices"][0]["message"]["content"]
    except Exception:
        print("chat/completions 原始响应：")
        print(json.dumps(j, ensure_ascii=False, indent=2)[:4000])
        return False, "chat/completions 返回结构非预期"

    print("\n✅ 对话成功，模型回复：")
    print(answer)
    return True, "OK"


def main() -> int:
    _try_load_dotenv()

    # 兼容多套命名（含 Qwen 直连）
    api_base = _get_env_any("REMOTE_MODEL_API_BASE", "QWEN_BASE_URL").strip()
    api_key = _get_env_any("REMOTE_MODEL_API_KEY", "QWEN_API_KEY").strip()
    model = _get_env_any("LLM_MODEL", "DEFAULT_LLM_MODEL_ID", "VISION_MODEL_ID").strip() or None

    print("=== LLM 对话连通性测试 ===")
    print("API_BASE:", api_base or "(empty)")
    print("API_KEY:", _mask(api_key))
    print("LLM_MODEL:", model or "(auto from /v1/models)")

    if not api_base:
        print("\n❌ 未设置 API_BASE（REMOTE_MODEL_API_BASE 或 QWEN_BASE_URL）")
        return 2
    if not api_key:
        print("\n❌ 未设置 API_KEY（REMOTE_MODEL_API_KEY 或 QWEN_API_KEY）")
        return 2

    ok, msg = try_openai_compatible(api_base, api_key, model)
    if ok:
        return 0

    print("\n❌ 测试失败：", msg)
    print("\n排查建议：")
    print("1) 如果返回 401/403：token 过期或无权限；更新 REMOTE_MODEL_API_KEY")
    print("2) 如果返回 404：api_base 可能不是 OpenAI 兼容地址（检查是否需要带 /v1）")
    print("3) 如果返回 model not found：设置正确的 LLM_MODEL")
    print("4) 如果是网关：确认 REMOTE_MODEL_API_BASE 可从当前机器访问")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
