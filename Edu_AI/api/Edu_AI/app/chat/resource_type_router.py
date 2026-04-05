from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

RESOURCE_TYPES: List[str] = [
    "report",
    "lesson_plan",
    "quiz",
    "flashcard",
    "blog",
    "ppt",
    "video",
    "podcast",
]

RESOURCE_TYPE_ROUTER_PROMPT = """你是“资源类型分类器”，只负责将用户的生成请求分类为具体资源类型。

可选类型（只能选一个）：
- report
- lesson_plan
- quiz
- flashcard
- blog
- ppt
- video
- podcast

输出要求（必须严格遵守）：
- 仅输出 JSON
- 仅包含一个字段：resource_type
- 字段值必须是上述 8 个合法枚举之一
- 不要输出任何解释、注释或额外文本
"""

RESOURCE_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "report": ["报告", "调研报告", "研究报告", "report"],
    "lesson_plan": ["教案", "教学设计", "课程设计", "lesson plan"],
    "quiz": ["试题", "题目", "测验", "quiz", "题库"],
    "flashcard": ["闪卡", "记忆卡", "卡片", "flashcard", "flash card"],
    "blog": ["博客", "公众号", "文章", "blog", "推文"],
    "ppt": ["ppt", "课件", "幻灯片", "slides", "slide deck"],
    "video": ["视频", "视频脚本", "短视频", "video", "script"],
    "podcast": ["播客", "音频脚本", "podcast", "播客稿"],
}


class ResourceTypeRouter:
    """二级资源类型路由器（LLM + 关键词兜底）。"""

    def __init__(self, model_gateway: Optional[Any]):
        self.model_gateway = model_gateway

    @staticmethod
    def _extract_json_payload(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw

        text = str(raw or "").strip()
        if not text:
            return {}

        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _fallback_keyword(question: str) -> Tuple[str, str]:
        text = (question or "").lower()
        for resource_type, keywords in RESOURCE_TYPE_KEYWORDS.items():
            matched = [kw for kw in keywords if kw.lower() in text]
            if matched:
                return resource_type, f"keyword:{resource_type}:{'|'.join(matched[:3])}"
        return "report", "fallback:default_report"

    def classify(self, question: str) -> Tuple[str, str]:
        """返回 (resource_type, source)。source: llm/keyword/fallback。"""

        if not self.model_gateway:
            r, meta = self._fallback_keyword(question)
            source = "keyword" if meta.startswith("keyword") else "fallback"
            return r, f"{source}:{meta}"

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": RESOURCE_TYPE_ROUTER_PROMPT},
            {"role": "user", "content": question},
        ]

        try:
            raw = self.model_gateway.chat(messages=messages, temperature=0.0, max_tokens=40)
            payload = self._extract_json_payload(raw)
            value = payload.get("resource_type")
            if value in RESOURCE_TYPES:
                return value, "llm:json"
        except Exception as exc:
            print(f"[resource_type_router_error] type={type(exc)} detail={exc}")

        r, meta = self._fallback_keyword(question)
        source = "keyword" if meta.startswith("keyword") else "fallback"
        return r, f"{source}:{meta}"
