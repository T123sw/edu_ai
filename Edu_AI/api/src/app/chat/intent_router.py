from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .schemas import IntentCategory


INTENT_ROUTER_PROMPT = """你是“流量意图分类器”，只负责语义分类，不负责流程控制。
请根据用户输入，在以下三类中选择其一：
1) chat：普通问答、解释、讨论、闲聊，不要求生成正式产物。
2) generate_content：明确要求生成结构化内容，如教案、报告、试题、讲稿。
3) research：明确要求联网搜索、全网查资料、网页信息整合、最新资讯检索。

输出要求（必须严格遵守）：
- 仅输出 JSON
- 仅包含一个字段：intent_category
- 合法值仅为：\"chat\"、\"generate_content\"、\"research\"
- 不要输出任何额外文本或解释
"""


class IntentRouter:
    """基于 LLM 的意图路由器（结构化输出 + 回退规则）。"""

    def __init__(self, model_gateway):
        self.model_gateway = model_gateway

    @staticmethod
    def _extract_json_payload(raw: Any) -> Dict[str, Any]:
        print(f"[intent_router] raw_type={type(raw)}")
        if isinstance(raw, dict):
            print(f"[intent_router] raw is dict keys={list(raw.keys())}")
            return raw

        text = str(raw or "").strip()
        print(f"[intent_router] raw_text_preview={text[:200]}")
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
    def _fallback_rule(question: str) -> Tuple[IntentCategory, str]:
        text = (question or "").lower()
        research_keywords = [
            "联网", "全网", "网上", "互联网", "网络", "网页", "搜索", "搜一下", "检索", "查资料", "最新资讯", "新闻",
            "web", "search", "google", "bing", "latest", "research",
        ]
        matched_research = [k for k in research_keywords if k in text]
        if matched_research:
            return "research", f"fallback_keyword_research:{'|'.join(matched_research[:3])}"

        generate_keywords = [
            "生成", "做一份", "写一份", "出一份", "做个", "写个",
            "教案", "报告", "试题", "讲稿", "思维导图", "总结文档",
            "generate", "create", "build", "lesson plan", "report", "quiz",
        ]
        matched = [k for k in generate_keywords if k in text]
        if matched:
            return "generate_content", f"fallback_keyword_generate:{'|'.join(matched[:3])}"
        return "chat", "fallback_default_chat"

    def classify(self, question: str) -> Tuple[IntentCategory, str]:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": INTENT_ROUTER_PROMPT},
            {"role": "user", "content": question},
        ]

        try:
            raw = self.model_gateway.chat(messages=messages, temperature=0.0, max_tokens=40)
            payload = self._extract_json_payload(raw)
            print(f"[intent_router] parsed_payload={payload}")
            intent = payload.get("intent_category")
            if intent in ("chat", "generate_content", "research"):
                return intent, "llm_json"
            return self._fallback_rule(question)
        except Exception as exc:
            print(f"[intent_router_error] type={type(exc)} detail={exc}")
            return self._fallback_rule(question)
