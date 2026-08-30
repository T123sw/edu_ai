from __future__ import annotations

import re

from app.chat.memory.domain import MemoryCandidate
from app.chat.memory.policy import PROTECTED_FACT_MARKERS


class RuleMemoryExtractor:
    """High-precision fallback for explicit user preferences and identity facts."""

    version = "rules-v1"

    _display_name = re.compile(r"(?:以后)?请叫我\s*([^，。！？,.!?\s]{1,20})")
    _preference_triggers = (
        "我更喜欢",
        "我喜欢",
        "我偏好",
        "请用",
        "请记住我",
        "我习惯",
        "回答尽量",
        "以后课件请",
        "不要直接给答案",
    )

    @staticmethod
    def _axis(text: str) -> str:
        if any(word in text for word in ("中文", "英文", "语言")):
            return "language"
        if any(word in text for word in ("简短", "详细", "步骤", "回答")):
            return "response_detail"
        if any(word in text for word in ("课件", "表格", "风格", "资源")):
            return "resource_preference"
        return "learning_style"

    def extract(self, message: str) -> list[MemoryCandidate]:
        text = str(message or "").strip()
        if not text:
            return []
        lowered = text.lower()
        if any(marker.lower() in lowered for marker in PROTECTED_FACT_MARKERS):
            return []

        name_match = self._display_name.search(text)
        if name_match:
            name = name_match.group(1).strip()
            return [
                MemoryCandidate(
                    memory_type="profile_fact",
                    content=f"用户希望被称为{name}",
                    confidence=0.99,
                    source_span=text,
                    reason="explicit_display_name",
                    profile_axis="display_name",
                    supersedes_axis=True,
                )
            ]

        if any(trigger in text for trigger in self._preference_triggers):
            axis = self._axis(text)
            return [
                MemoryCandidate(
                    memory_type="preference",
                    content=f"用户偏好：{text}",
                    confidence=0.94,
                    source_span=text,
                    reason="explicit_preference",
                    profile_axis=axis,
                    supersedes_axis=any(
                        word in text for word in ("以后", "改为", "不要", "尽量")
                    ),
                )
            ]
        return []
