from __future__ import annotations

from app.chat.runtime.reflection.base import BaseReflector, ReflectVerdict


class ContentRelevanceReflector(BaseReflector):
    """LLM-based check: are search results relevant to the plan topic?
    Only activates when step_constraints contains check_relevance=True."""

    priority = 10
    _APPLIES_TO = {"rag_search", "web_search"}

    def __init__(self, llm_gateway):
        self._gateway = llm_gateway

    def applies_to(self, tool_name: str) -> bool:
        return tool_name in self._APPLIES_TO

    def evaluate(self, tool_name, result, state, step_constraints) -> ReflectVerdict:
        if not result.get("ok"):
            return ReflectVerdict(verdict="pass")
        if not step_constraints.get("check_relevance", False):
            return ReflectVerdict(verdict="pass")

        topic = (state.get("current_plan") or {}).get("subject", "")
        if not topic:
            return ReflectVerdict(verdict="pass")

        payload = result.get("payload") or {}
        content = str(payload.get("answer") or payload.get("summary") or "").strip()
        if len(content) < 30:
            return ReflectVerdict(verdict="pass")  # too short to judge relevance

        verdict_text = self._call_llm(topic, content[:600])
        if "不相关" in verdict_text:
            return ReflectVerdict(
                verdict="retry",
                hint=f"搜索结果与主题「{topic}」相关性不足，建议换关键词重试",
                severity="warning",
            )
        return ReflectVerdict(verdict="pass")

    def _call_llm(self, topic: str, content: str) -> str:
        stream_fn = getattr(self._gateway, "stream_chat_with_tools", None)
        if not callable(stream_fn):
            return "相关"
        messages = [
            {
                "role": "system",
                "content": "你是内容审查助手。只回答「相关」或「不相关」加一句理由，不超过30字。",
            },
            {
                "role": "user",
                "content": f"主题：{topic}\n\n内容摘要：{content}\n\n这段内容与主题是否直接相关？",
            },
        ]
        chunks: list[str] = []
        try:
            for e in stream_fn(messages, [], tool_choice="auto", temperature=0.0, max_tokens=50):
                if e.get("type") == "text_delta":
                    chunks.append(e.get("content", ""))
        except Exception:
            return "相关"
        return "".join(chunks)


class OutlineCoherenceReflector(BaseReflector):
    """LLM-based check: is the draft_outline coherent and complete?
    Only activates when step_constraints contains check_coherence=True."""

    priority = 10

    def __init__(self, llm_gateway):
        self._gateway = llm_gateway

    def applies_to(self, tool_name: str) -> bool:
        return tool_name == "draft_outline"

    def evaluate(self, tool_name, result, state, step_constraints) -> ReflectVerdict:
        if not result.get("ok"):
            return ReflectVerdict(verdict="pass")
        if not step_constraints.get("check_coherence", False):
            return ReflectVerdict(verdict="pass")

        topic = (state.get("current_plan") or {}).get("subject", "")
        payload = result.get("payload") or {}
        outline = str(payload.get("outline_markdown", "")).strip()
        if not outline or not topic:
            return ReflectVerdict(verdict="pass")

        verdict_text = self._call_llm(topic, outline[:800])
        if "不合格" in verdict_text or "不完整" in verdict_text:
            return ReflectVerdict(
                verdict="retry",
                hint="大纲结构不完整或与主题匹配度不足，建议重新生成",
                severity="warning",
            )
        return ReflectVerdict(verdict="pass")

    def _call_llm(self, topic: str, outline: str) -> str:
        stream_fn = getattr(self._gateway, "stream_chat_with_tools", None)
        if not callable(stream_fn):
            return "合格"
        messages = [
            {
                "role": "system",
                "content": "你是内容审查助手。只回答「合格」或「不合格」加一句理由，不超过30字。",
            },
            {
                "role": "user",
                "content": f"主题：{topic}\n\n大纲：{outline}\n\n这个大纲是否完整、逻辑清晰且与主题匹配？",
            },
        ]
        chunks: list[str] = []
        try:
            for e in stream_fn(messages, [], tool_choice="auto", temperature=0.0, max_tokens=50):
                if e.get("type") == "text_delta":
                    chunks.append(e.get("content", ""))
        except Exception:
            return "合格"
        return "".join(chunks)
