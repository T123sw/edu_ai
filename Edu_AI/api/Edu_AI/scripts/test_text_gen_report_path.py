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
                '{"chapter_id":1,"chapter_title":"背景","chapter_goal":"说明背景","sections":[{"section_id":"1.1","title":"问题定义"}]}'
                ']}'
            )

        return _Resp()


def _fake_build_report_markdown(*, skill_manager, slots, outline):
    _ = skill_manager, slots
    return "# 报告\n\n引擎集成测试正文", {
        "chapter_count": len(outline or []),
        "completed_chapters": len(outline or []),
        "retry_count": 0,
        "failed_chapters": [],
    }


def run() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.chat.engines.text_gen_engine import TextGenEngine
    from app.chat.engines.plugins.report_plugin import ReportPlugin

    report_plugin = ReportPlugin(
        skill_manager=_DummySkillManager(),
        llm=_DummyLLM(),
        build_report_markdown_fn=_fake_build_report_markdown,
    )
    engine = TextGenEngine(plugins={"report": report_plugin})

    state = {
        "resource_type": "report",
        "slots": {"core_topic": "函数"},
        "slot_collection_phase": "done",
        "outline": [],
        "generated_content": "",
        "generation_checkpoint": {},
        "final_answer": "",
    }

    s1 = engine.slot_collector_node(dict(state))
    s2 = engine.planner_node(dict(s1))
    s3 = engine.validator_node(dict(s2))
    s4 = engine.executor_node(dict(s3))
    s5 = engine.analyzer_node(dict(s4))

    assert s5.get("engine_stage") == "finished"
    assert "引擎集成测试正文" in str(s5.get("final_answer") or "")
    assert isinstance(s5.get("generation_checkpoint"), dict)

    print("text_gen report path tests passed")


if __name__ == "__main__":
    run()
