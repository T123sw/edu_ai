from __future__ import annotations

from app.chat.domain.ppt_slide_plan import PptSlidePlan, PptSlidePlanSlide


class PptContentMarkdownAssembler:
    @staticmethod
    def _indent_lines(prefix: str, items: list[str]) -> list[str]:
        return [f"{prefix}{item}" for item in items if str(item or "").strip()]

    def _render_slide(self, slide: PptSlidePlanSlide, *, toc_items: list[str]) -> list[str]:
        lines: list[str] = [
            f"## Slide {slide.slide_index}",
            f"- Role: {slide.role}",
            f"- Title: {slide.title}",
            "",
            "### Blocks",
        ]

        if slide.role == "cover":
            if slide.lead:
                lines.append(f"- Lead: {slide.lead}")
            if slide.bullets:
                lines.append("- Meta:")
                lines.extend(self._indent_lines("  - ", slide.bullets))
        elif slide.role == "toc":
            lines.append("- Toc:")
            lines.extend(self._indent_lines("  - ", toc_items or slide.bullets))
        elif slide.layout_intent == "comparison" and slide.comparison is not None:
            if slide.lead:
                lines.append(f"- Lead: {slide.lead}")
            lines.append("- Comparison:")
            lines.append(f"  - Left-Title: {slide.comparison.left.title}")
            lines.append("    Left-Items:")
            lines.extend(self._indent_lines("      - ", list(slide.comparison.left.items or [])))
            lines.append(f"  - Right-Title: {slide.comparison.right.title}")
            lines.append("    Right-Items:")
            lines.extend(self._indent_lines("      - ", list(slide.comparison.right.items or [])))
        elif slide.layout_intent == "cards" and slide.cards:
            if slide.lead:
                lines.append(f"- Lead: {slide.lead}")
            lines.append("- Cards:")
            for card in slide.cards:
                lines.append(f"  - Title: {card.title}")
                lines.append(f"    Text: {card.text}")
        elif slide.layout_intent == "process" and slide.process_steps:
            if slide.lead:
                lines.append(f"- Lead: {slide.lead}")
            lines.append("- Process:")
            for step in slide.process_steps:
                lines.append(f"  - Step-Title: {step.title}")
                lines.append(f"    Step-Text: {step.text}")
        else:
            if slide.lead:
                lines.append(f"- Lead: {slide.lead}")
            if slide.bullets:
                lines.append("- Bullets:")
                lines.extend(self._indent_lines("  - ", list(slide.bullets or [])))

        if slide.presenter_notes:
            lines.extend(["", "### Notes", slide.presenter_notes])
        return lines

    def assemble(self, *, slide_plan: PptSlidePlan | None = None, outline=None) -> str:
        if slide_plan is None:
            raise ValueError("slide_plan is required")

        lines: list[str] = [
            "# Deck",
            f"- Title: {slide_plan.deck_title}",
            f"- Subtitle: {slide_plan.deck_subtitle or ''}",
            f"- Theme: {slide_plan.theme_id}",
        ]

        toc_items = [
            str(getattr(chapter, "chapter_title", "") or "").strip()
            for chapter in list(getattr(slide_plan, "chapters", []) or [])
            if str(getattr(chapter, "chapter_title", "") or "").strip()
        ]
        if not toc_items:
            toc_items = [slide.title for slide in list(slide_plan.slides or []) if str(slide.role) == "content"]
        for slide in list(slide_plan.slides or []):
            lines.extend(["", "---", ""])
            lines.extend(self._render_slide(slide, toc_items=toc_items))

        return "\n".join(lines).strip() + "\n"
