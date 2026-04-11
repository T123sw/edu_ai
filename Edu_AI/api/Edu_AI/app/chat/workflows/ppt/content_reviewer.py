from __future__ import annotations

import json
import re
from typing import Any

from .placeholder_detector import PptPlaceholderDetector


class PptContentReviewer:
    _PROTOCOL_ROLE_VALUES = {"cover", "toc", "section", "content", "thanks"}

    def __init__(
        self,
        *,
        llm=None,
        placeholder_detector: PptPlaceholderDetector | None = None,
        max_text_chars: int = 90,
    ) -> None:
        self.llm = llm
        self.placeholder_detector = placeholder_detector or PptPlaceholderDetector()
        self.max_text_chars = max(int(max_text_chars or 0), 40)

    @staticmethod
    def _clean(value: object, default: str = "") -> str:
        text = str(value or "").strip()
        return text or default

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        raw_text = getattr(response, "content", response)
        if isinstance(raw_text, str):
            return raw_text.strip()
        if isinstance(raw_text, list):
            parts: list[str] = []
            for item in raw_text:
                if isinstance(item, dict):
                    text = str(item.get("text") or "").strip()
                else:
                    text = str(item or "").strip()
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        return str(raw_text or "").strip()

    @staticmethod
    def _extract_json_object(text: str) -> str:
        normalized = str(text or "").strip()
        normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.I)
        normalized = re.sub(r"\s*```$", "", normalized)
        match = re.search(r"\{.*\}", normalized, re.S)
        return match.group(0) if match else normalized

    def _iter_slide_texts(self, *, slide_plan) -> list[tuple[int | None, str, str]]:
        items: list[tuple[int | None, str, str]] = []
        for slide in list(getattr(slide_plan, "slides", []) or []):
            slide_index = getattr(slide, "slide_index", None)
            if getattr(slide, "lead", None):
                items.append((slide_index, "lead", str(slide.lead)))
            for index, bullet in enumerate(list(getattr(slide, "bullets", []) or []), start=1):
                items.append((slide_index, f"bullets[{index}]", str(bullet)))
            for index, card in enumerate(list(getattr(slide, "cards", []) or []), start=1):
                items.append((slide_index, f"cards[{index}].title", str(getattr(card, "title", ""))))
                items.append((slide_index, f"cards[{index}].text", str(getattr(card, "text", ""))))
            for index, step in enumerate(list(getattr(slide, "process_steps", []) or []), start=1):
                items.append((slide_index, f"process_steps[{index}].title", str(getattr(step, "title", ""))))
                items.append((slide_index, f"process_steps[{index}].text", str(getattr(step, "text", ""))))
            comparison = getattr(slide, "comparison", None)
            if comparison is not None:
                items.append((slide_index, "comparison.left.title", str(getattr(comparison.left, "title", ""))))
                items.append((slide_index, "comparison.right.title", str(getattr(comparison.right, "title", ""))))
                for index, item in enumerate(list(getattr(comparison.left, "items", []) or []), start=1):
                    items.append((slide_index, f"comparison.left.items[{index}]", str(item)))
                for index, item in enumerate(list(getattr(comparison.right, "items", []) or []), start=1):
                    items.append((slide_index, f"comparison.right.items[{index}]", str(item)))
        return items

    def _build_review_prompt(self, *, outline, slide_plan, content_markdown: str, preparation) -> str:
        constraints = [
            "Reject placeholder phrases or generic filler.",
            "Reject repeated adjacent-slide explanations.",
            "Reject sentences that are obviously too long for PPT reading.",
            "Reject slides that are too sparse for a substantial teaching deck.",
            "Reject content that only restates the slide title without adding detail.",
            "Preserve the provided JSON-compatible slide structure.",
            "Prefer concise, teachable Chinese content with specific points.",
            "Follow the content protocol: Role + Blocks determine layout.",
            "Do not allow layout_hint, template names, or placement instructions.",
            "Only allow protocol roles: cover, toc, section, content, thanks.",
            "Interpret layouts as protocol blocks: bullets -> Lead/Bullets/Meta; cards -> Cards; process -> Process; comparison -> Comparison.",
        ]
        example = (
            "Example of acceptable slide copy:\n"
            "- lead: Use one classroom question to open the concept.\n"
            "- bullets: concept definition | core mechanism | one memorable example\n"
            "- cards.text: Write a specific conclusion or fact, not placeholder filler.\n"
        )
        return (
            "Review this PPT slide plan for quality and format.\n"
            "Return JSON only in the shape "
            "{\"ok\": true|false, \"issues\": [\"...\"], \"feedback\": \"...\"}.\n"
            "If it fails, feedback should be short, actionable, and suitable for regeneration.\n"
            f"Deck title: {self._clean(getattr(outline, 'deck_title', ''))}\n"
            f"Audience: {self._clean(getattr(preparation, 'audience', ''), 'general learners')}\n"
            f"Objective: {self._clean(getattr(preparation, 'objective', ''), 'teaching')}\n"
            "Constraints:\n"
            + "\n".join(f"- {item}" for item in constraints)
            + "\n"
            + example
            + "\nSlide plan JSON:\n"
            + json.dumps(slide_plan.model_dump(exclude_none=True), ensure_ascii=False)
            + "\nContent markdown:\n"
            + str(content_markdown or "")
        )

    def _parse_review_response(self, response: Any) -> dict[str, Any] | None:
        text = self._extract_response_text(response)
        if not text:
            return None
        try:
            payload = json.loads(self._extract_json_object(text))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return {
            "ok": bool(payload.get("ok")),
            "issues": [self._clean(item) for item in list(payload.get("issues") or []) if self._clean(item)],
            "feedback": self._clean(payload.get("feedback")),
            "mode": "llm",
        }

    def _prefers_substantial_deck(self, *, slide_plan, preparation) -> bool:
        preferred_slide_count = self._clean(getattr(preparation, "slide_count", ""))
        try:
            if preferred_slide_count and int(preferred_slide_count) >= 12:
                return True
        except Exception:
            pass
        return len(list(getattr(slide_plan, "slides", []) or [])) >= 8

    def _is_sparse_content_slide(self, slide) -> bool:
        if self._clean(getattr(slide, "role", "")).lower() != "content":
            return False
        layout = self._clean(getattr(slide, "layout_intent", "")).lower()
        if layout == "bullets":
            return len(list(getattr(slide, "bullets", []) or [])) < 3
        if layout == "cards":
            return len(list(getattr(slide, "cards", []) or [])) < 2
        if layout == "process":
            return len(list(getattr(slide, "process_steps", []) or [])) < 2
        if layout == "comparison":
            comparison = getattr(slide, "comparison", None)
            if comparison is None:
                return True
            total_items = len(list(getattr(comparison.left, "items", []) or [])) + len(
                list(getattr(comparison.right, "items", []) or [])
            )
            return total_items < 4
        return not self._clean(getattr(slide, "lead", ""))

    def _fallback_review(self, *, slide_plan, preparation) -> dict[str, Any]:
        issues = [str(item.get("message") or "").strip() for item in self.placeholder_detector.detect(slide_plan=slide_plan)]
        previous_signature = None
        prefers_substantial_deck = self._prefers_substantial_deck(
            slide_plan=slide_plan,
            preparation=preparation,
        )
        for slide in list(getattr(slide_plan, "slides", []) or []):
            role = self._clean(getattr(slide, "role", "")).lower()
            if role and role not in self._PROTOCOL_ROLE_VALUES:
                issues.append(
                    f"Slide {getattr(slide, 'slide_index', None)} uses an invalid role '{role}'."
                )
            serialized_slide = json.dumps(
                slide.model_dump(exclude_none=True) if hasattr(slide, "model_dump") else dict(slide),
                ensure_ascii=False,
            ).lower()
            if "layout_hint" in serialized_slide:
                issues.append(
                    f"Slide {getattr(slide, 'slide_index', None)} includes layout_hint, which is not allowed by the content protocol."
                )
            signature = (
                role,
                self._clean(getattr(slide, "layout_intent", "")).lower(),
                self._clean(getattr(slide, "lead", "")).lower(),
            )
            if previous_signature is not None and previous_signature == signature:
                issues.append(
                    f"Slide {getattr(slide, 'slide_index', None)} repeats the same adjacent-slide framing."
                )
            if prefers_substantial_deck and self._is_sparse_content_slide(slide):
                issues.append(
                    f"Slide {getattr(slide, 'slide_index', None)} is too sparse for a substantial teaching deck."
                )
            previous_signature = signature
        for slide_index, field_path, text in self._iter_slide_texts(slide_plan=slide_plan):
            if len(text.strip()) > self.max_text_chars:
                issues.append(
                    f"Slide {slide_index} {field_path} is too long for PPT reading; shorten it."
                )
        deduped_issues: list[str] = []
        seen: set[str] = set()
        for issue in issues:
            if not issue or issue in seen:
                continue
            seen.add(issue)
            deduped_issues.append(issue)
        if not deduped_issues:
            return {"ok": True, "issues": [], "feedback": "", "mode": "heuristic"}
        return {
            "ok": False,
            "issues": deduped_issues,
            "feedback": "Increase the teaching substance, remove placeholders, and keep each point concise.",
            "mode": "heuristic",
        }

    def review(self, *, outline, slide_plan, content_markdown: str, preparation) -> dict[str, Any]:
        if self.llm is not None:
            try:
                response = self.llm.invoke(
                    self._build_review_prompt(
                        outline=outline,
                        slide_plan=slide_plan,
                        content_markdown=content_markdown,
                        preparation=preparation,
                    )
                )
                parsed = self._parse_review_response(response)
                if parsed is not None:
                    return parsed
            except Exception:
                pass
        return self._fallback_review(slide_plan=slide_plan, preparation=preparation)
