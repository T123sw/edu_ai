from __future__ import annotations

from typing import Any


def llm_model_label(llm: Any | None) -> str:
    if llm is None:
        return ""
    for attr in ("model", "model_name", "model_id"):
        value = str(getattr(llm, attr, "") or "").strip()
        if value:
            return value
    return llm.__class__.__name__


def llm_base_url(llm: Any | None) -> str:
    if llm is None:
        return ""
    for attr in ("base_url", "openai_api_base", "api_base"):
        value = str(getattr(llm, attr, "") or "").strip()
        if value:
            return value
    return ""


def should_skip_function_calling(llm: Any | None) -> bool:
    model = llm_model_label(llm).lower()
    base_url = llm_base_url(llm).lower()
    return "qwen" in model or "dashscope.aliyuncs.com" in base_url
