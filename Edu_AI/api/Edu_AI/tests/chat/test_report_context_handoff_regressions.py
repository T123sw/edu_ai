from types import SimpleNamespace

from app.chat.agents.universal_report_engine import extractor_node
from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor
from app.chat.workflows.report.assembler import ReportAssembler


class _FakeStructuredLLM:
    def __init__(self, payload):
        self._payload = payload

    def invoke(self, prompt):
        report_slots = self._payload.get("report_slots", {})

        class _StructuredSlots:
            def __init__(self, slots):
                self._slots = slots

            def model_dump(self, exclude_none=True):
                return dict(self._slots)

        class _StructuredResult:
            def __init__(self, slots):
                self.report_slots = _StructuredSlots(slots)

        return _StructuredResult(report_slots)


class _FakeExtractorLLM:
    def __init__(self, payload):
        self._payload = payload

    def with_structured_output(self, schema, method="function_calling"):
        return _FakeStructuredLLM(self._payload)


def test_memory_extractor_ignores_generic_follow_up_topics():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="具体一点，介绍下整个过程",
            course_id=None,
            capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
        ),
        result={
            "message": {
                "content": "可以，我来把关羽北伐中的内部失和和军资问题展开梳理。",
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={
            "conversation_memory": {
                "current_topics": ["关羽北伐失败的原因"],
            },
        },
        recent_messages=[],
    )

    assert patch["conversation_memory"]["current_topics"] == ["关羽北伐失败的原因"]


def test_memory_extractor_does_not_treat_assistant_questions_as_confirmed_facts():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=SimpleNamespace(
            question="请基于当前内容生成一份报告",
            course_id=None,
            capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
        ),
        result={
            "message": {
                "content": (
                    "1. 您想具体了解军资供应中的哪个方面？比如：军粮短缺、军饷拖欠、武器装备不足，还是运输问题？\n"
                    "2. 您更关注军资供应问题的原因分析，还是其导致的内部冲突具体表现？"
                ),
            },
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_user"},
        },
        existing_state={},
        recent_messages=[],
    )

    assert patch["conversation_memory"]["confirmed_facts"] == []


def test_extractor_node_preserves_prefilled_core_topic_against_generic_short_reply():
    patch = extractor_node(
        {
            "user_input": "请基于当前内容生成一份报告",
            "human_feedback": "",
            "phase": "extracting",
            "report_slots": {},
            "gathered_context": {
                "slot_hints": {
                    "core_topic": "关羽北伐失败中的内部失和与军资问题",
                    "focus_area": "军资供应问题如何引发内部失和",
                },
            },
        },
        extractor_llm=_FakeExtractorLLM(
            {
                "report_slots": {
                    "core_topic": "具体一点",
                    "focus_area": "内部失和：因军资供应问题",
                },
                "notes": "",
            }
        ),
    )

    assert patch["report_slots"]["core_topic"] == "关羽北伐失败中的内部失和与军资问题"
    assert patch["report_slots"]["focus_area"] == "内部失和：因军资供应问题"


def test_report_assembler_prefers_substantive_context_over_generic_topics():
    gathered = ReportAssembler().from_generation_context(
        GenerationContext(
            conversation_id="conv-1",
            resource_type="report",
            summary_text="当前围绕关羽北伐失败的原因展开分析，重点涉及军资供应与内部失和。",
            current_topics=["具体一点", "介绍下整个过程"],
            user_goals=["生成报告"],
            confirmed_facts=["军资问题与内部失和相互影响"],
            constraints={},
            teaching_issues=["军资供应问题如何引发内部失和"],
            student_signals=[],
            evidence_points=[],
            recent_relevant_messages=[
                {"role": "user", "content": "我想分析关羽北伐失败中军资供应问题如何引发内部失和。"},
            ],
            source_scope={},
        )
    )

    assert gathered["slot_hints"]["core_topic"] == "我想分析关羽北伐失败中军资供应问题如何引发内部失和"
