"""
o_agent 对外导出。

注意：`base_agent` 依赖较多（jinja2/langgraph 等），为了让仅使用 LLM 的脚本
（如 `test_config.py`）更轻量，这里对 `get_agent` 做惰性导入。
"""

from .llm import get_llm_by_type, get_llm_from_config


def get_agent(*args, **kwargs):
    from .base_agent import get_agent as _get_agent
    return _get_agent(*args, **kwargs)


__all__ = ['get_agent', 'get_llm_by_type', 'get_llm_from_config']