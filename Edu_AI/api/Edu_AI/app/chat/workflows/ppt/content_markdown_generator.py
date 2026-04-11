from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.chat.domain.ppt_outline import PptOutline


class PptContentMarkdownGenerator:
    def __init__(self, *, llm=None, protocol_path: str | Path | None = None) -> None:
        self.llm = llm
        self.protocol_path = Path(protocol_path) if protocol_path is not None else self._default_protocol_path()

    @staticmethod
    def _default_protocol_path() -> Path:
        return Path(__file__).resolve().parents[4] / "html2ppt" / "content-protocol.md"

    @staticmethod
    def _clean(value: object, default: str = "") -> str:
        text = str(value or "").strip()
        return text or default

    @staticmethod
    def _preview_text(value: object, limit: int = 360) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...(+{len(text) - limit} chars)"

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
    def _strip_markdown_fences(text: str) -> str:
        normalized = str(text or "").strip()
        normalized = re.sub(r"^```(?:markdown|md)?\s*\n?", "", normalized, flags=re.I)
        normalized = re.sub(r"\n?```\s*$", "", normalized, flags=re.S)
        return normalized.strip()

    @staticmethod
    def _join_points(values: list[str]) -> str:
        return " | ".join([str(item).strip() for item in list(values or []) if str(item).strip()]) or "未提供"

    def _load_protocol_text(self) -> str:
        try:
            return self.protocol_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise FileNotFoundError(f"Unable to read PPT content protocol from {self.protocol_path}") from exc

    def _build_prompt(self, *, outline: PptOutline, preparation, protocol_text: str) -> str:
        slides: list[str] = []
        for slide in list(outline.slides or []):
            key_points = " | ".join([str(item).strip() for item in list(getattr(slide, "key_points", []) or []) if str(item).strip()])
            slides.append(
                f"- slide_index={slide.slide_index}; role={slide.role}; title={slide.title}; goal={slide.goal}; key_points={key_points}"
            )

        chapters: list[str] = []
        for chapter in list(outline.chapters or []):
            chapters.append(
                f"- chapter_index={chapter.chapter_index}; title={chapter.chapter_title}; goal={chapter.chapter_goal}"
            )

        audience = self._clean(getattr(preparation, "audience", None), "中文课堂学习者")
        objective = self._clean(getattr(preparation, "objective", None), "课堂讲解")
        slide_count = self._clean(getattr(preparation, "slide_count", None), "15+")
        key_points = self._join_points(list(getattr(preparation, "key_points", []) or []))
        source_basis = self._join_points(list(getattr(preparation, "source_basis", []) or []))
        source_excerpts = self._join_points(list(getattr(preparation, "source_excerpts", []) or []))

        prompt = (
            "请直接生成完整的最终 content_markdown，不要先输出提纲、解释、JSON 或其他中间结构。\n"
            "你要根据下面的 PPT 大纲与备课信息，直接写出可交给 html2ppt 的最终 content.md。\n"
            "内容必须足够充实，适合课堂讲解，整体建议不少于 15+ 页。\n"
            "每一页都要写出真实内容，不要只重复标题，也不要故意写得很短。\n"
            "请严格遵守下方原始 content-protocol.md 里的结构约束，用 Role + Blocks 的方式组织每一页。\n"
            "如果需要取舍，请优先保证教学内容完整、表达清晰、可直接讲授。\n\n"
            "【内容表达约束】\n"
            "请把下面要求作为内容生成时的写作约束，而不是额外解释出来。\n"
            "不要使用 *、** 这类 Markdown 强调或列表符号，正文直接写自然语言内容。\n"
            "模板里如果已经有 01/02/03 或 1/2/3 这类视觉序号，正文不要再写 Step 1、步骤一、第一步 这类重复编号，只保留内容本身。\n"
            "不要输出字面量 \\n、\\t 或其他转义符号文本，换行请通过协议允许的正常文本结构自然表达。\n"
            "结束页（thanks）不要写成回顾总结页，不要堆很多要点，只保留感谢语、汇报人、学校/学院等少量收尾信息。\n\n"
            "【PPT 大纲】\n"
            f"- deck_title={outline.deck_title}\n"
            f"- deck_subtitle={self._clean(outline.deck_subtitle, '无')}\n"
            f"- theme_id={self._clean(outline.theme_id, 'heu_academic_elegant')}\n"
            + ("- chapters:\n" + "\n".join(chapters) + "\n" if chapters else "")
            + "- slides:\n"
            + "\n".join(slides)
            + "\n\n"
            "【备课信息】\n"
            f"- audience={audience}\n"
            f"- objective={objective}\n"
            f"- slide_count={slide_count}\n"
            f"- key_points={key_points}\n"
            f"- source_basis={source_basis}\n"
            f"- source_excerpts={source_excerpts}\n\n"
            "【原始 content-protocol.md】\n"
            f"{protocol_text}"
        )
        return prompt

    def generate(self, *, outline: PptOutline, preparation=None) -> tuple[str, dict[str, Any]]:
        protocol_text = self._load_protocol_text()
        if self.llm is None:
            raise RuntimeError("PptContentMarkdownGenerator requires llm to generate content")

        prompt = self._build_prompt(outline=outline, preparation=preparation, protocol_text=protocol_text)
        response = self.llm.invoke(prompt)
        response_text = self._extract_response_text(response)
        content_markdown = self._strip_markdown_fences(response_text)
        debug = {
            "generation_mode": "direct_content_markdown",
            "protocol_path": str(self.protocol_path),
            "protocol_loaded": True,
            "prompt_preview": self._preview_text(prompt),
            "response_preview": self._preview_text(response_text),
        }
        return content_markdown, debug
