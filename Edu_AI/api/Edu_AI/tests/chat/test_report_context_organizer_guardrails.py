from app.chat.domain.generation_context import GenerationContext
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
