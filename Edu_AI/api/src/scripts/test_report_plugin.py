from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _DummySkillManager:
    def extract_section(self, skill_name: str, section_name: str) -> str:
        if skill_name == "edu-report-agent" and section_name == "REPORT_OUTLINE_AST_PROMPT":
            return "请生成报告大纲"
        return ""


class _DummyLLM:
    def invoke(self, messages):
        class _Resp:
            content = (
                '{"outline": ['
                '{"chapter_id":1,"chapter_title":"背景","chapter_goal":"说明背景","sections":[{"section_id":"1.1","title":"问题定义"}]},'
                '{"chapter_id":2,"chapter_title":"分析","chapter_goal":"展开分析","sections":[{"section_id":"2.1","title":"关键因素"}]}'
                ']}'
            )

        return _Resp()


def _fake_build_report_markdown(*, skill_manager, slots, outline):
    _ = skill_manager, slots
    chapter_count = len(outline or [])
    return "# 报告\n\n这是测试正文。", {
        "chapter_count": chapter_count,
        "completed_chapters": chapter_count,
        "retry_count": 0,
        "failed_chapters": [],
    }


def run() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.chat.engines.plugins.report_plugin import ReportPlugin
    from app.chat.slot_definitions import ReportSlots

    plugin = ReportPlugin(
        skill_manager=_DummySkillManager(),
        llm=_DummyLLM(),
        build_report_markdown_fn=_fake_build_report_markdown,
    )

    assert plugin.resource_type == "report"
    assert plugin.slot_class is ReportSlots
    assert plugin.needs_outline_review() is True

    slots = {
        "core_topic": "函数",
        "focus_area": "教学应用",
        "length_requirement": "常规",
        "depth_level": "中等",
        "format_style": "结构化",
        "dynamic_constraints": "{}",
    }

    outline = plugin.build_outline(slots, context={})
    assert isinstance(outline, list)
    assert len(outline) >= 1
    assert isinstance(outline[0], dict)

    content = plugin.generate_content(slots, outline, context={})
    assert "测试正文" in content

    assert isinstance(plugin.last_checkpoint, dict)
    assert plugin.last_checkpoint.get("chapter_count") == len(outline)

    print("report_plugin tests passed")


if __name__ == "__main__":
    run()
