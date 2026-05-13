from __future__ import annotations

from typing import Any

from app.chat.domain.ppt_slide_plan import PptSlidePlanChapter


class PptContentOptimizer:
    def __init__(self, *, max_toc_items: int = 4) -> None:
        self.max_toc_items = max(int(max_toc_items or 0), 1)

    @staticmethod
    def _dedupe_keep_order(items: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    @staticmethod
    def _issue_codes_for_slide(*, slide_index: int | None, issues: list[dict[str, Any]]) -> list[str]:
        codes: list[str] = []
        for issue in list(issues or []):
            if issue.get("slide_index") == slide_index:
                code = str(issue.get("code") or "").strip()
                if code:
                    codes.append(code)
        return codes

    def repair(self, *, slide_plan, outline, preparation, issues, slide_plan_builder) -> dict[str, Any]:
        repaired = slide_plan.model_copy(deep=True)
        transformations: list[dict[str, Any]] = []

        if any(str(item.get("code") or "") == "toc.too_many_items" for item in list(issues or [])):
            before = [
                str(getattr(chapter, "chapter_title", "") or "").strip()
                for chapter in list(getattr(repaired, "chapters", []) or [])
                if str(getattr(chapter, "chapter_title", "") or "").strip()
            ]
            after = before[: self.max_toc_items]
            if not after:
                after = self._dedupe_keep_order(
                    [
                        str(getattr(slide, "title", "") or "").strip()
                        for slide in list(getattr(repaired, "slides", []) or [])
                        if str(getattr(slide, "role", "") or "").strip() == "content"
                    ]
                )[: self.max_toc_items]
            if after and before != after:
                repaired.chapters = [
                    PptSlidePlanChapter(
                        chapter_index=index,
                        chapter_title=title,
                        chapter_goal=title,
                        slides=[],
                    )
                    for index, title in enumerate(after, start=1)
                ]
                transformations.append(
                    {
                        "strategy": "trim_toc_to_chapters",
                        "slide_index": 2,
                        "field_path": "chapters",
                        "reason": "TOC should stay at chapter level",
                        "before": before,
                        "after": after,
                    }
                )

        outline_slides = {
            int(getattr(item, "slide_index", 0) or 0): item
            for item in list(getattr(outline, "slides", []) or [])
            if int(getattr(item, "slide_index", 0) or 0) > 0
        }
        for slide in list(getattr(repaired, "slides", []) or []):
            slide_index = int(getattr(slide, "slide_index", 0) or 0)
            issue_codes = self._issue_codes_for_slide(slide_index=slide_index, issues=list(issues or []))
            if not any(code.startswith("placeholder.") for code in issue_codes):
                continue
            outline_slide = outline_slides.get(slide_index)
            if outline_slide is None:
                continue
            support_points = slide_plan_builder._collect_support_points(outline_slide, preparation=preparation)
            slide.lead = slide_plan_builder._build_default_lead(outline_slide, support_points)
            slide.presenter_notes = slide_plan_builder._build_default_presenter_notes(
                outline_slide,
                support_points,
                str(slide.lead or ""),
            )
            layout = str(getattr(slide, "layout_intent", "") or "").strip()
            if layout == "cards":
                slide.cards = slide_plan_builder._enrich_cards(outline_slide, support_points, existing=[])
            elif layout == "process":
                slide.process_steps = slide_plan_builder._enrich_process_steps(outline_slide, support_points, existing=[])
            elif layout == "comparison":
                slide.comparison = slide_plan_builder._enrich_comparison(outline_slide, support_points, existing=None)
            else:
                slide.bullets = slide_plan_builder._build_bullet_candidates(outline_slide, support_points, existing=[])
            transformations.append(
                {
                    "strategy": "regenerate_slide_content",
                    "slide_index": slide_index,
                    "field_path": f"slides[{slide_index}]",
                    "reason": "repair placeholder content before html2ppt",
                    "before": issue_codes,
                    "after": {
                        "layout_intent": slide.layout_intent,
                        "lead": slide.lead,
                    },
                }
            )

        return {
            "slide_plan": repaired,
            "transformations": transformations,
        }
