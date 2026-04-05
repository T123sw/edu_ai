"""
直接测试 API 连接（不通过 LangChain），用于定位：
- base_url 是否应该带 /v1
- /models、/v1/models、/chat/completions、/v1/chat/completions 哪个可用
- 认证头是否为 Bearer
"""

import json
import tomllib

import requests


def _print_resp(prefix: str, r: requests.Response) -> None:
    print(f"{prefix} 状态码: {r.status_code}")
    ct = r.headers.get("content-type", "")
    print(f"{prefix} content-type: {ct}")
    text = (r.text or "").replace("\r", "").replace("\n", " ")
    print(f"{prefix} 响应(前200): {text[:200]}")


def test_api_direct() -> None:
    print("=" * 60)
    print("直接测试 API 连接")
    print("=" * 60)

    cfg = tomllib.load(open("config.toml", "rb"))
    base_url = cfg["api_base"]["remote_model_api_base"].rstrip("/")
    api_key = cfg["api_key"]["remote_model_api_key"].strip()
    base_url_v1 = base_url if base_url.endswith("/v1") else f"{base_url}/v1"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    print(f"\nAPI Base URL: {base_url}")
    print(f"API Base URL (/v1): {base_url_v1}")
    print(f"API Key: {api_key[:15]}...")

    # 1) models
    print("\n" + "-" * 60)
    print("测试 1: 列出可用模型")
    print("-" * 60)
    for root in (base_url, base_url_v1):
        for path in ("/models", "/v1/models"):
            url = f"{root}{path}"
            print(f"\nGET {url}")
            try:
                r = requests.get(url, headers=headers, timeout=15)
                _print_resp("  ", r)
            except Exception as e:
                print(f"  ❌ 请求异常: {type(e).__name__}: {e}")

    # 2) chat completions
    print("\n" + "-" * 60)
    print("测试 2: 调用 chat/completions")
    print("-" * 60)
    models_to_try = ["DeepSeek-V3.2-Exp", "deepseek-v3.2-exp", "deepseek-chat", "gpt-3.5-turbo"]
    paths = ("/v1/chat/completions", "/chat/completions")

    for model in models_to_try:
        for root in (base_url, base_url_v1):
            for path in paths:
                url = f"{root}{path}"
                print(f"\nPOST {url} | model={model}")
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "你好"}],
                    "max_tokens": 16,
                }
                try:
                    r = requests.post(url, headers=headers, json=payload, timeout=20)
                    _print_resp("  ", r)
                    if r.status_code == 200:
                        try:
                            data = r.json()
                            print("  ✅ 成功返回(截断):")
                            print(json.dumps(data, ensure_ascii=False, indent=2)[:400])
                        except Exception:
                            pass
                        return
                except Exception as e:
                    print(f"  ❌ 请求异常: {type(e).__name__}: {e}")

    # 3) other auth headers (only if everything above failed)
    print("\n" + "-" * 60)
    print("测试 3: 尝试不同的认证头（仅用于排查）")
    print("-" * 60)
    auth_headers = [
        {"Authorization": f"Bearer {api_key}"},
        {"Authorization": f"Bearer {api_key}", "X-API-Key": api_key},
        {"X-API-Key": api_key},
        {"api-key": api_key},
    ]
    for i, h in enumerate(auth_headers, 1):
        url = f"{base_url_v1}/models"
        print(f"\n认证方式 {i}: {list(h.keys())} | GET {url}")
        try:
            r = requests.get(url, headers={**h}, timeout=15)
            _print_resp("  ", r)
        except Exception as e:
            print(f"  ❌ 请求异常: {type(e).__name__}: {e}")


if __name__ == "__main__":
    test_api_direct()