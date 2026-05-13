from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI

# 允许直接以 `python scripts/test_langchain_tools_models.py` 运行
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import Config


def run_for_model(model_id: str) -> None:
    model_cfg = Config.get_llm_model(model_id)
    model_name = str(model_cfg.get("model_name") or "")
    provider = str(model_cfg.get("provider") or "")
    print(f"\n=== TEST model_id={model_id} provider={provider} model_name={model_name} ===")

    llm = ChatOpenAI(
        api_key=str(model_cfg.get("api_key") or ""),
        base_url=str(model_cfg.get("api_base") or ""),
        model=model_name,
        temperature=0.0,
    )

    tools: List[Dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "ping_tool",
                "description": "Simple ping tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    messages = [
        {"role": "system", "content": "You can call tools."},
        {"role": "user", "content": "请直接回复一句你好，不需要调用工具"},
    ]

    try:
        out = llm.bind(tools=tools).invoke(messages)
        print(f"OK: type={type(out)}")
        print(f"content={repr(getattr(out, 'content', None))}")
        print(f"tool_calls={getattr(out, 'tool_calls', None)}")
    except Exception as e:
        print(f"ERR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # 新配置下默认两个模型：
    # - logic-gpt-5.4-mini (OpenRouter)
    # - deepseek-vl3 (DeepSeek)
    run_for_model("logic-gpt-5.4-mini")
    run_for_model("deepseek-vl3")
