from __future__ import annotations

import time
from pathlib import Path
import re
from typing import Dict, List


class SkillManager:
    """Load and apply project skills as runtime prompt context."""

    NODE_SKILL_MAP: Dict[str, List[str]] = {
        "router": ["edu-orchestrator", "edu-agent-routing"],
        "extractor": ["edu-orchestrator", "edu-agent-routing", "edu-report-workflow"],
        "ask": ["edu-orchestrator", "edu-report-workflow", "edu-dialogue-agent"],
        "outline": ["edu-orchestrator", "edu-report-workflow"],
        "generate": ["edu-orchestrator", "edu-report-workflow", "edu-teacher-content-factory"],
        "chat": ["edu-orchestrator", "edu-dialogue-agent", "edu-rag-multimodal"],
    }

    def __init__(self, skills_dir: Path | None = None, cache_ttl_sec: int = 30) -> None:
        default_dir = Path(__file__).resolve().parents[3] / "skills"
        self._skills_dir = (skills_dir or default_dir).resolve()
        self._cache_ttl_sec = max(1, int(cache_ttl_sec))
        self._cache_expires_at = 0.0
        self._cache: Dict[str, str] = {}

    def _read_skill_file(self, path: Path) -> str:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

        if not text:
            return ""

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                text = parts[2].strip()
        return text

    def _refresh_cache_if_needed(self) -> None:
        now = time.time()
        if now < self._cache_expires_at and self._cache:
            return

        loaded: Dict[str, str] = {}
        if self._skills_dir.exists() and self._skills_dir.is_dir():
            for skill_dir in self._skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                content = self._read_skill_file(skill_file)
                if content:
                    loaded[skill_dir.name.strip()] = content

        self._cache = loaded
        self._cache_expires_at = now + self._cache_ttl_sec

    def get_skill_text(self, skill_name: str) -> str:
        self._refresh_cache_if_needed()
        return self._cache.get(skill_name, "")

    @staticmethod
    def _dedup(items: List[str]) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for name in items:
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        return deduped

    def select_node_skills(
        self,
        *,
        node_name: str,
        intent_category: str,
        response_type: str,
        is_report: bool,
        has_video_context: bool,
        has_image_context: bool,
        question: str = "",
        dialogue_skill: str = "",
    ) -> List[str]:
        base = list(self.NODE_SKILL_MAP.get(node_name, ["edu-orchestrator"]))

        if node_name == "chat":
            if "edu-agent-routing" not in base:
                base.append("edu-agent-routing")

            # 第二阶段收敛：chat 主技能统一为 edu-dialogue-agent，
            # 细分由 state.dialogue_skill 控制，不再按多个 dialogue-* skill 注入。
            if "edu-dialogue-agent" not in base:
                base.append("edu-dialogue-agent")

            if has_video_context or has_image_context:
                if "edu-rag-multimodal" not in base:
                    base.append("edu-rag-multimodal")

        if node_name in {"ask", "outline", "generate", "extractor"} and (is_report or response_type in {"ask", "outline", "generate"}):
            if "edu-report-workflow" not in base:
                base.append("edu-report-workflow")

        if intent_category == "generate_content" and node_name in {"generate", "chat"}:
            if "edu-teacher-content-factory" not in base:
                base.append("edu-teacher-content-factory")

        return self._dedup(base)

    def select_skills(
        self,
        *,
        intent_category: str,
        response_type: str,
        is_report: bool,
        has_video_context: bool,
        has_image_context: bool,
        question: str = "",
        dialogue_skill: str = "",
    ) -> List[str]:
        return self.select_node_skills(
            node_name="chat",
            intent_category=intent_category,
            response_type=response_type,
            is_report=is_report,
            has_video_context=has_video_context,
            has_image_context=has_image_context,
            question=question,
            dialogue_skill=dialogue_skill,
        )

    @staticmethod
    def _extract_section(skill_text: str, section_name: str) -> str:
        if not skill_text:
            return ""

        # 兼容二级/三级标题：## SECTION_NAME 或 ### SECTION_NAME
        heading_pattern = rf"^##{{1,2}}\s+{re.escape(section_name)}\s*$"
        section_break_pattern = r"^##{1,2}\s+"

        lines = skill_text.splitlines()
        start = -1
        for i, line in enumerate(lines):
            if re.match(heading_pattern, line.strip()):
                start = i + 1
                break
        if start == -1:
            return ""

        collected: List[str] = []
        for j in range(start, len(lines)):
            line = lines[j]
            if re.match(section_break_pattern, line.strip()):
                break
            collected.append(line)
        return "\n".join(collected).strip()

    def extract_section(self, skill_name: str, section_name: str) -> str:
        skill_text = self.get_skill_text(skill_name)
        return self._extract_section(skill_text, section_name)

    def extract_prompt_sections(self, skill_name: str) -> Dict[str, str]:
        skill_text = self.get_skill_text(skill_name)
        return {
            "system_prompt": self._extract_section(skill_text, "SYSTEM_PROMPT"),
            "output_template": self._extract_section(skill_text, "OUTPUT_TEMPLATE"),
            "question_template": self._extract_section(skill_text, "QUESTION_TEMPLATE"),
            "followup_template": self._extract_section(skill_text, "FOLLOWUP_TEMPLATE"),
            "fallback_after_2_turns_template": self._extract_section(skill_text, "FALLBACK_AFTER_2_TURNS_TEMPLATE"),
            "tool_auth_template": self._extract_section(skill_text, "TOOL_AUTH_TEMPLATE"),
        }

    def render_system_prompt(self, *, base_prompt: str, skill_names: List[str]) -> str:
        blocks: List[str] = [base_prompt.strip()]

        skill_blocks: List[str] = []
        for name in skill_names:
            skill_text = self.get_skill_text(name)
            if not skill_text:
                continue
            sections = self.extract_prompt_sections(name)
            preferred = sections.get("system_prompt") or skill_text
            short_text = preferred[:2200].strip()
            if not short_text:
                continue
            skill_blocks.append(f"[Skill:{name}]\n{short_text}")

        if skill_blocks:
            blocks.append("【运行时技能约束】\n请优先遵循以下技能规范（若冲突，以系统安全规则为最高优先级）：\n" + "\n\n".join(skill_blocks))

        return "\n\n".join([b for b in blocks if b]).strip()
