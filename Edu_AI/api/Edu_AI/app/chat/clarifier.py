from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


CLARIFIER_PROMPT = """你是教学对话助手中的“澄清判断器”。
任务：判断用户输入是否信息不足、语义模糊、无法直接高质量回答。

输出要求：严格 JSON，字段如下：
{
  "needs_clarification": true/false,
  "reason": "简短原因",
  "follow_up_question": "当 needs_clarification=true 时给出一句自然追问，否则为空字符串"
}

规则：
1) 当用户输入过短、指代不清、目标不明确时，needs_clarification=true。
2) 追问要具体、单轮可答，优先询问最关键缺失信息。
3) 如果用户问题已明确，可直接回答，则 needs_clarification=false。
4) 不要输出任何 JSON 以外内容。
"""


class Clarifier:
    """澄清追问模块：LLM判定 + 规则回退。"""

    _SHORT_BUT_INFORMATIVE_MARKERS = [
        "基础", "基础知识", "原理", "工作原理", "应用", "应用场景", "常见问题", "配置", "排错", "优化",
        "tcp", "udp", "http", "https", "dns", "ip", "api", "sql", "python", "java", "算法",
    ]

    def __init__(self, model_gateway):
        self.model_gateway = model_gateway

    @classmethod
    def _is_short_but_informative(cls, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False
        return any(marker in t for marker in cls._SHORT_BUT_INFORMATIVE_MARKERS)

    @classmethod
    def _fallback(cls, question: str) -> Tuple[bool, str, str, str]:
        text = (question or "").strip()
        if len(text) <= 6 and not cls._is_short_but_informative(text):
            return True, "too_short", "你可以再具体一点吗？比如课程主题、年级或你希望我帮你解决的具体问题。", "fallback_too_short"

        ambiguous_markers = ["这个", "那个", "怎么弄", "咋办", "帮我看看", "不会", "不太懂"]
        if any(m in text for m in ambiguous_markers):
            return True, "ambiguous_reference", "我可以帮你。为了更准确，你具体是指哪一部分内容？也可以补充课程主题和年级。", "fallback_ambiguous"

        return False, "clear_enough", "", "fallback_clear"

    def assess(self, question: str) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": CLARIFIER_PROMPT},
            {"role": "user", "content": question},
        ]

        try:
            content = self.model_gateway.chat(messages=messages, temperature=0.0, max_tokens=120)
            payload: Dict[str, Any] = json.loads(content)
            needs = bool(payload.get("needs_clarification", False))
            reason = str(payload.get("reason") or "")
            follow_up = str(payload.get("follow_up_question") or "")

            if needs and self._is_short_but_informative(question):
                fallback_needs, fallback_reason, _, _ = self._fallback(question)
                if not fallback_needs:
                    return {
                        "needs_clarification": False,
                        "reason": "short_but_informative",
                        "follow_up_question": "",
                        "source": "heuristic_short_but_informative",
                    }

            if needs and not follow_up.strip():
                # 追问缺失时，回退兜底
                needs, reason, follow_up, source = self._fallback(question)
                return {
                    "needs_clarification": needs,
                    "reason": reason,
                    "follow_up_question": follow_up,
                    "source": source,
                }
            return {
                "needs_clarification": needs,
                "reason": reason or ("clear_enough" if not needs else "insufficient_context"),
                "follow_up_question": follow_up,
                "source": "llm_json",
            }
        except Exception:
            needs, reason, follow_up, source = self._fallback(question)
            return {
                "needs_clarification": needs,
                "reason": reason,
                "follow_up_question": follow_up,
                "source": source,
            }
