"""Report service configuration management."""
from __future__ import annotations

import os
from typing import Optional


class ReportConfig:
    """Configuration for report generation service."""

    def __init__(
        self,
        llm_model: Optional[str] = None,
        llm_base_url: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        max_ask_limit: Optional[int] = None,
        max_replans: Optional[int] = None,
    ):
        self.llm_model = llm_model or os.getenv(
            "REPORT_LLM_MODEL",
            os.getenv("ANSWER_LLM_MODEL", os.getenv("VISION_MODEL_ID", "qwen3.5-plus")),
        )
        self.llm_base_url = llm_base_url or os.getenv(
            "REPORT_LLM_BASE_URL",
            os.getenv(
                "ANSWER_LLM_API_BASE",
                os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ),
        )
        self.llm_api_key = llm_api_key or os.getenv(
            "REPORT_LLM_API_KEY",
            os.getenv("ANSWER_LLM_API_KEY", os.getenv("QWEN_API_KEY", "")),
        )
        self.max_ask_limit = max_ask_limit or int(os.getenv("REPORT_MAX_ASK_LIMIT", "2"))
        self.max_replans = max_replans or int(os.getenv("REPORT_MAX_REPLANS", "3"))
