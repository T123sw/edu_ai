from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel

from ...agents.report_generation import build_report_markdown, get_fallback_llm
from ...agents.report_utils import normalize_outline_ast
from ...report_domain import REPORT_DEFAULTS
from ...slot_definitions import ReportSlots
from ...utils.json_utils import extract_json_block
from ..plugin_base import GenPlugin


class ReportPlugin(GenPlugin):
    """Report 资源类型插件（P2-03 最小可用版）。"""

    def __init__(
        self,
        *,
        skill_manager: Any,
        llm: Optional[Any] = None,
        build_report_markdown_fn: Optional[Callable[..., tuple[str, Dict[str, Any]]]] = None,
    ) -> None:
        self._skill_manager = skill_manager
        self._llm = llm
        self._build_report_markdown = build_report_markdown_fn or build_report_markdown
        self.last_checkpoint: Dict[str, Any] = {}

    @property
    def resource_type(self) -> str:
        return "report"

    @property
    def slot_class(self) -> Type[BaseModel]:
        return ReportSlots

    def needs_outline_review(self) -> bool:
        return True

    def build_outline(self, slots: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        llm = self._llm or get_fallback_llm()
        if not llm:
            return self._fallback_outline(slots)

        outline_prompt = self._safe_extract_section("edu-report-agent", "REPORT_OUTLINE_AST_PROMPT")
        if not outline_prompt:
            outline_prompt = "请按 AST JSON 生成报告大纲。"

        user_payload = {
            "report_slots": self._normalize_report_slots(slots),
            "dynamic_constraints": str(slots.get("dynamic_constraints") or "{}"),
        }

        try:
            response = llm.invoke(
                [
                    {"role": "system", "content": "你是报告大纲生成器。"},
                    {
                        "role": "user",
                        "content": f"{outline_prompt}\n\n{json.dumps(user_payload, ensure_ascii=False)}",
                    },
                ]
            )
            raw = str(getattr(response, "content", "") or "").strip()
            parsed = extract_json_block(raw)

            if isinstance(parsed, dict) and isinstance(parsed.get("outline"), list):
                outline = normalize_outline_ast(parsed.get("outline"))
            else:
                outline = normalize_outline_ast(parsed)

            return outline if outline else self._fallback_outline(slots)
        except Exception:
            return self._fallback_outline(slots)

    def generate_content(
        self,
        slots: Dict[str, Any],
        outline: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        safe_outline = normalize_outline_ast(outline) if isinstance(outline, list) else []
        safe_slots = self._normalize_report_slots(slots)

        content, checkpoint = self._build_report_markdown(
            skill_manager=self._skill_manager,
            slots=safe_slots,
            outline=safe_outline,
        )
        self.last_checkpoint = checkpoint if isinstance(checkpoint, dict) else {}
        return str(content or "").strip()

    def post_process(self, content: str) -> str:
        text = str(content or "").strip()
        if not text:
            return ""
        return text

    def _safe_extract_section(self, skill_name: str, section_name: str) -> str:
        try:
            return str(self._skill_manager.extract_section(skill_name, section_name) or "").strip()
        except Exception:
            return ""

    def _normalize_report_slots(self, slots: Dict[str, Any]) -> Dict[str, str]:
        normalized = {
            "core_topic": str(slots.get("core_topic") or REPORT_DEFAULTS["core_topic"]).strip() or REPORT_DEFAULTS["core_topic"],
            "focus_area": str(slots.get("focus_area") or REPORT_DEFAULTS["focus_area"]).strip() or REPORT_DEFAULTS["focus_area"],
            "length_requirement": str(slots.get("length_requirement") or REPORT_DEFAULTS["length_requirement"]).strip() or REPORT_DEFAULTS["length_requirement"],
            "depth_level": str(slots.get("depth_level") or REPORT_DEFAULTS["depth_level"]).strip() or REPORT_DEFAULTS["depth_level"],
            "format_style": str(slots.get("format_style") or REPORT_DEFAULTS["format_style"]).strip() or REPORT_DEFAULTS["format_style"],
            "dynamic_constraints": str(slots.get("dynamic_constraints") or "{}").strip() or "{}",
        }
        return normalized

    def _fallback_outline(self, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
        topic = str(slots.get("core_topic") or REPORT_DEFAULTS["core_topic"]).strip()
        raw = [
            {
                "chapter_id": 1,
                "chapter_title": f"{topic}：背景与问题界定",
                "chapter_goal": "澄清核心问题与研究边界",
                "sections": [
                    {"section_id": "1.1", "title": "概念与范围"},
                    {"section_id": "1.2", "title": "问题与挑战"},
                ],
            },
            {
                "chapter_id": 2,
                "chapter_title": f"{topic}：分析与建议",
                "chapter_goal": "给出结构化分析与可执行建议",
                "sections": [
                    {"section_id": "2.1", "title": "关键因素分析"},
                    {"section_id": "2.2", "title": "策略与建议"},
                ],
            },
        ]
        return normalize_outline_ast(raw)
