from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.report_preparation import ReportPreparationResult
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer


def test_report_context_organizer_falls_back_to_raw_json_when_structured_output_returns_none():
    class DummyStructured:
        def invoke(self, prompt):
            return None

    class DummyLlm:
        def with_structured_output(self, schema, method=None):
            return DummyStructured()

        def invoke(self, prompt):
            return """```json
{
  "report_intent": "generate_report",
  "report_subject": "Flooded Seven Armies",
  "report_focus": "Campaign timeline and strategic reversal",
  "report_context_summary": {
    "subject_summary": "Discuss the battle and its consequences",
    "focus_summary": "Explain how tactical success became strategic failure",
    "key_points": ["battle background", "flood attack"],
    "evidence_points": [],
    "constraints": {},
    "source_scope": ["from_conversation"]
  },
  "key_points": ["battle background", "flood attack"],
  "evidence_points": [],
  "constraints": {},
  "source_scope": {
    "from_conversation": true,
    "from_docs": false,
    "from_course": false,
    "from_artifacts": false
  },
  "open_questions": [],
  "missing_critical_fields": [],
  "confidence": "high",
  "soft_confirm_message": "I will draft the report now.",
  "followup_candidates": []
}
```"""

    context = GenerationContext(
        conversation_id="conv-llm-none",
        resource_type="report",
        summary_text="Discuss the Flooded Seven Armies campaign.",
        current_topics=["Flooded Seven Armies"],
        user_goals=["generate report"],
    )

    result = ReportContextOrganizer(llm=DummyLlm()).organize(
        context=context,
        request_question="Please generate a report from the current context.",
    )

    assert result.report_subject == "Flooded Seven Armies"
    assert result.report_focus == "Campaign timeline and strategic reversal"
    assert result.preparation_source == "llm_raw_json"


def test_report_context_organizer_does_not_promote_generic_report_request_to_subject():
    context = GenerationContext(
        conversation_id="conv-generic-report",
        resource_type="report",
        summary_text="",
        current_topics=["继续分析"],
        user_goals=["生成报告"],
        recent_relevant_messages=[{"role": "user", "content": "请基于当前内容生成一份报告"}],
    )

    result = ReportContextOrganizer().organize(
        context=context,
        request_question="请基于当前内容生成一份报告",
    )

    assert result.report_subject is None
    assert result.missing_critical_fields == ["report_subject"]
    assert result.followup_candidates == ["你希望这份报告围绕哪个主题来写？"]


def test_report_context_organizer_extracts_subject_from_explicit_report_request():
    context = GenerationContext(
        conversation_id="conv-explicit-report",
        resource_type="report",
        summary_text="",
        current_topics=[],
        user_goals=["生成报告"],
    )

    result = ReportContextOrganizer().organize(
        context=context,
        request_question="请围绕课堂前10分钟学生参与度下降生成一份报告",
    )

    assert result.report_subject == "课堂前10分钟学生参与度下降"
    assert result.missing_critical_fields == []


def test_report_context_organizer_rewrites_low_signal_llm_subject_and_focus():
    class DummyStructured:
        def invoke(self, prompt):
            return ReportPreparationResult(
                report_intent="generate_report",
                report_subject="请基于当前内容生成一份报告",
                report_focus="详细一点",
            )

    class DummyLlm:
        def with_structured_output(self, schema, method=None):
            return DummyStructured()

    context = GenerationContext(
        conversation_id="conv-llm-guard",
        resource_type="report",
        summary_text="课堂前10分钟学生参与度下降，需要聚焦导入和提问设计。",
        current_topics=["课堂前10分钟学生参与度下降"],
        user_goals=["生成报告"],
        teaching_issues=["导入环节吸引力不足"],
    )

    result = ReportContextOrganizer(llm=DummyLlm()).organize(
        context=context,
        request_question="请基于当前内容生成一份报告",
    )

    assert result.report_subject == "课堂前10分钟学生参与度下降"
    assert result.report_focus == "导入环节吸引力不足"
    assert result.preparation_source == "llm_structured_output"
