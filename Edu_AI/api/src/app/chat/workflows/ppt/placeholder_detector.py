from __future__ import annotations

import re
from typing import Any


class PptPlaceholderDetector:
    _FILLER_PHRASES = (
        "为什么重要",
        "课堂结论",
        "最值得强调",
        "关键作用",
    )

    @staticmethod
    def _normalize(value: object) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[\s\u3000]+", "", text)
        text = re.sub(r"[，。、“”‘’：:；;,.!?！？（）()\-\[\]【】]", "", text)
        return text

    @classmethod
    def _is_title_restatement(cls, title: object, text: object) -> bool:
        normalized_title = cls._normalize(title)
        normalized_text = cls._normalize(text)
        if not normalized_title or not normalized_text:
            return False
        if normalized_title == normalized_text:
            return True
        if normalized_text.startswith(normalized_title) and len(normalized_text) - len(normalized_title) <= 8:
            return True
        if normalized_title.startswith(normalized_text) and len(normalized_title) - len(normalized_text) <= 8:
            return True
        return False

    @classmethod
    def _is_filler_without_detail(cls, text: object) -> bool:
        raw = str(text or "").strip()
        if not raw:
            return False
        matched = False
        reduced = raw
        for phrase in cls._FILLER_PHRASES:
            if phrase in reduced:
                matched = True
                reduced = reduced.replace(phrase, "")
        if not matched:
            return False
        reduced = re.sub(r"[\s\u3000，。、“”‘’：:；;,.!?！？（）()\-\[\]【】]", "", reduced)
        return len(reduced) < 6

    def detect(self, *, slide_plan) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for slide in list(getattr(slide_plan, "slides", []) or []):
            slide_index = getattr(slide, "slide_index", None)
            for card_index, card in enumerate(list(getattr(slide, "cards", []) or []), start=1):
                if self._is_title_restatement(getattr(card, "title", ""), getattr(card, "text", "")):
                    issues.append(
                        {
                            "code": "placeholder.card_text_matches_title",
                            "severity": "error",
                            "slide_index": slide_index,
                            "field_path": f"slides[{slide_index}].cards[{card_index}].text",
                            "message": "Card body repeats or nearly repeats the card title.",
                            "suggested_action": "rewrite_card_body_with_detail",
                        }
                    )
                elif self._is_filler_without_detail(getattr(card, "text", "")):
                    issues.append(
                        {
                            "code": "placeholder.filler_text_without_detail",
                            "severity": "error",
                            "slide_index": slide_index,
                            "field_path": f"slides[{slide_index}].cards[{card_index}].text",
                            "message": "Card body uses filler wording without concrete detail.",
                            "suggested_action": "replace_filler_with_specific_fact",
                        }
                    )
            for bullet_index, bullet in enumerate(list(getattr(slide, "bullets", []) or []), start=1):
                if self._is_filler_without_detail(bullet):
                    issues.append(
                        {
                            "code": "placeholder.filler_text_without_detail",
                            "severity": "error",
                            "slide_index": slide_index,
                            "field_path": f"slides[{slide_index}].bullets[{bullet_index}]",
                            "message": "Bullet uses filler wording without concrete detail.",
                            "suggested_action": "replace_filler_with_specific_fact",
                        }
                    )
        return issues
