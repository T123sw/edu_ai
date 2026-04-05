from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer


def test_report_context_organizer_falls_back_to_raw_llm_json_when_structured_output_fails():
    class DummyStructured:
        def invoke(self, prompt):
            raise RuntimeError("structured failed")

    class DummyLlm:
        def with_structured_output(self, schema, method=None):
            return DummyStructured()

        def invoke(self, prompt):
            return """```json
{
  "report_intent": "generate_report",
  "report_subject": "Skills 与 MCP 的差异",
  "report_focus": "工具集成方式与适用场景差异",
  "report_context_summary": {
    "subject_summary": "当前围绕 Skills 与 MCP 的差异展开讨论",
    "focus_summary": "重点比较工具集成方式与适用场景",
    "key_points": ["Skills 偏内置能力", "MCP 偏开放协议"],
    "evidence_points": [],
    "constraints": {},
    "source_scope": ["from_conversation"]
  },
  "key_points": ["Skills 偏内置能力", "MCP 偏开放协议"],
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
  "soft_confirm_message": "我将基于 Skills 与 MCP 的差异生成报告，可以开始吗？",
  "followup_candidates": []
}
```"""

    context = GenerationContext(
        conversation_id="conv-llm",
        resource_type="report",
        summary_text="当前围绕 Skills 与 MCP 的差异展开讨论。",
        current_topics=["Skills 与 MCP 的差异"],
        user_goals=["生成报告"],
    )

    result = ReportContextOrganizer(llm=DummyLlm()).organize(
        context=context,
        request_question="请基于当前内容生成一份报告",
    )

    assert result.report_subject == "Skills 与 MCP 的差异"
    assert result.report_focus == "工具集成方式与适用场景差异"
    assert result.confidence == "high"
    assert result.preparation_source == "llm_raw_json"
