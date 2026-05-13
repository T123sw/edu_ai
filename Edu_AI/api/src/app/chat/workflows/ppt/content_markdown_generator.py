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
            key_points = " | ".join(
                [str(item).strip() for item in list(getattr(slide, "key_points", []) or []) if str(item).strip()]
            )
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
        slide_count = self._clean(getattr(preparation, "slide_count", None), "18+")
        key_points = self._join_points(list(getattr(preparation, "key_points", []) or []))
        source_basis = self._join_points(list(getattr(preparation, "source_basis", []) or []))
        source_excerpts = self._join_points(list(getattr(preparation, "source_excerpts", []) or []))

        prompt = (
            "请直接生成完整的最终 content_markdown，不要先输出提纲、解释、JSON 或其他中间结构。\n"
            "你要根据下面的 PPT 大纲与备课信息，直接写出可交给 html2ppt 的最终 content.md。\n"
            "输出必须是可直接使用的最终稿，不要输出草稿、占位内容、写作说明或元注释。\n"
            "内容目标不是简单把标题扩写，而是生成一份适合课堂讲解、信息密度高、真正有教学价值的课件文稿。\n"
            "整体建议不少于 18 页；如果主题本身信息量较大，可以在不偏离大纲的前提下主动拆页展开。\n"
            "每一页都要写出真实内容，不要只重复标题，不要故意写得很短，不要用空话凑篇幅。\n"
            "请严格遵守下方原始 content-protocol.md 里的结构约束，用 Role + Blocks 的方式组织每一页。\n"
            "如果需要取舍，请优先保证教学内容完整、逻辑递进清楚、表达准确、可直接讲授。\n\n"
            "【核心内容目标】\n"
            "请把“有干货”理解为：每一页都应提供明确的知识增量，让学生能够学到概念、原理、规律、方法、案例、比较、误区或应用中的至少一部分。\n"
            "不要把页面写成“标题 + 几句泛泛描述”的形式，也不要大量使用“具有重要意义”“值得关注”“应用广泛”这类信息密度很低的套话。\n"
            "除封面页、目录页、章节过渡页、结束页外，绝大多数内容页都必须写出充实正文，并且正文应能支撑课堂讲解，而不是只适合展示。\n\n"
            "【每页内容深度要求】\n"
            "大多数内容页应尽量同时包含以下要素中的至少 3 种，且表达自然，不要机械罗列：概念或定义、原理或机制、因果关系或推导逻辑、典型例子或场景、方法步骤或分析框架、对比辨析、常见误区或易错点、实际应用或题型。\n"
            "不要只回答“是什么”，还要尽量讲清“为什么成立”“怎么使用”“适用于什么条件”“容易错在哪里”“与相近概念有什么区别”。\n"
            "如果某一页承担公式、定理、算法、模型、制度、历史过程等核心教学内容，应尽量补充其前提、关键变量、约束条件、变化规律、判断依据或结果解释。\n\n"
            "【按内容类型展开的写作要求】\n"
            "如果是概念型内容，不要只给定义，要补充内涵、外延、辨析和例子。\n"
            "如果是方法型内容，不要只给流程，要补充适用条件、关键步骤、优缺点和常见错误。\n"
            "如果是理论型内容，不要只写结论，要补充成立条件、推理思路和直观理解。\n"
            "如果是应用型内容，不要只列场景，要说明为什么适用、如何判断、如何落地、结果如何解释。\n"
            "如果是比较型内容，不要只并列列出名词，要明确比较维度、核心差异、各自适用场景和易混点。\n\n"
            "【整体组织要求】\n"
            "请根据大纲自动补全合理的教学链路，使整套课件形成自然递进：先交代主题背景、学习对象、问题场景或学习价值，再讲核心概念和基本框架，再讲原理、机制、方法或过程，再讲案例、应用、题型、分析，最后做简洁收束。\n"
            "如果原始大纲写得比较简略，但显然不足以支撑完整授课，请在不偏离主题的前提下，合理补足课堂上本来就应该讲到的基础概念、关键过渡内容和典型例子。\n"
            "如果某个章节包含多个核心点，请主动拆成多页展开，而不是把多个重点硬压在一页里草草带过。\n"
            "不要为了凑页数制造大量重复页、空页、纯标题页；也不要为了省事把大段知识点压缩成几句摘要。\n\n"
            "【课堂表达风格】\n"
            "整套内容必须像认真备课后的教学型 PPT 文稿，而不是宣传稿、论文摘要、读书笔记或口号式提纲。\n"
            "语言要准确、自然、清楚，适合老师直接讲授，也适合学生直接阅读理解。\n"
            "抽象概念尽量配以直观解释；复杂内容尽量讲清关键转折；必要时加入简洁但真实的小例子、判断场景或典型题型。\n"
            "优先产出能够帮助理解和讲解的内容，而不是华丽但空泛的表达。\n\n"
            "【篇幅与密度要求】\n"
            "大多数内容页都应形成“一个明确小主题 + 一段展开解释 + 必要例子/比较/结论”的结构。\n"
            "不要一页只有两三句空泛文字，不要用同义反复来凑字数，不要把多个名词简单堆在一起而不展开。\n"
            "宁可少写一些装饰性表达，也要把关键知识点讲透。\n"
            "如果备课信息里给出了 key_points、source_basis、source_excerpts，请优先吸收并转化为真正可讲授的页面内容，而不是机械复述原文。\n\n"
            "【内容表达约束】\n"
            "请把下面要求作为内容生成时的写作约束，而不是额外解释出来。\n"
            "不要使用 *、** 这类 Markdown 强调或列表符号，正文直接写自然语言内容。\n"
            "模板里如果已经有 01/02/03 或 1/2/3 这类视觉序号，正文不要再写 Step 1、步骤一、第一步 这类重复编号，只保留内容本身。\n"
            "不要输出字面量 \\n、\\t 或其他转义符号文本，换行请通过协议允许的正常文本结构自然表达。\n"
            "不要输出“下面开始生成”“以下是最终结果”“第 X 页”等额外提示语。\n"
            "不要写“可视化建议”“配图建议”“本页可放图”“讲解提示”等元说明，直接写最终页面内容。\n"
            "如果协议允许使用 summary、quote、case、columns 等 block，请优先用于承载真实教学内容，而不是装饰性文字。\n"
            "结束页（thanks）不要写成回顾总结页，不要堆很多要点，只保留感谢语、汇报人、学校/学院等少量收尾信息。\n\n"
            "【封面页与结束页要求】\n"
            "封面页保持简洁，准确呈现题目、课程属性、汇报人、单位等必要信息。\n"
            "结束页只保留简洁收尾信息，不再展开知识点，不写大段总结。\n\n"
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
