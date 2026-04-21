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
  "report_subject": "Python Variables",
  "report_focus": "Variable definitions and naming rules",
  "report_context_summary": {
    "subject_summary": "Discuss Python variable basics",
    "focus_summary": "Explain definitions and naming rules",
    "key_points": ["definition", "naming"],
    "evidence_points": [],
    "constraints": {},
    "source_scope": ["from_conversation"]
  },
  "key_points": ["definition", "naming"],
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
  "soft_confirm_message": "",
  "followup_candidates": []
}
```"""

    context = GenerationContext(
        conversation_id="conv-llm",
        resource_type="report",
        summary_text="Discuss Python variable basics",
        current_topics=["Python Variables"],
        user_goals=["generate report"],
    )

    result = ReportContextOrganizer(llm=DummyLlm()).organize(
        context=context,
        request_question="Generate a report from the discussion.",
    )

    assert result.report_subject == "Python Variables"
    assert result.report_focus == "Variable definitions and naming rules"
    assert result.confidence == "high"
    assert result.preparation_source == "llm_raw_json"


def test_report_context_organizer_uses_raw_json_directly_for_qwen_compatible_models():
    class DummyLlm:
        model = "qwen3.5-plus"
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        def __init__(self):
            self.structured_calls = 0
            self.prompts = []

        def with_structured_output(self, schema, method=None):
            self.structured_calls += 1
            raise AssertionError("qwen-compatible llm should not use function_calling structured output")

        def invoke(self, prompt):
            self.prompts.append(prompt)
            return """```json
{
  "report_intent": "generate_report",
  "report_subject": "Python Variables",
  "report_focus": "Variable definitions and naming rules",
  "report_context_summary": {
    "subject_summary": "Discuss Python variable basics",
    "focus_summary": "Explain definitions and naming rules",
    "key_points": ["definition", "naming"],
    "evidence_points": [],
    "constraints": {},
    "source_scope": ["from_conversation"]
  },
  "key_points": ["definition", "naming"],
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
  "soft_confirm_message": "",
  "followup_candidates": []
}
```"""

    llm = DummyLlm()
    context = GenerationContext(
        conversation_id="conv-report-qwen",
        resource_type="report",
        summary_text="Discuss Python variable basics",
        current_topics=["Python Variables"],
        user_goals=["generate report"],
    )

    result = ReportContextOrganizer(llm=llm).organize(
        context=context,
        request_question="Generate a report from the discussion.",
    )

    assert llm.structured_calls == 0
    assert llm.prompts
    assert result.report_subject == "Python Variables"
    assert result.report_focus == "Variable definitions and naming rules"
    assert result.preparation_source == "llm_raw_json"
