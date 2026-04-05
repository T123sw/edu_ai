from pathlib import Path
from types import SimpleNamespace
import uuid

from app.chat.domain.extraction_candidate import ExtractionCandidate
from app.chat.domain.extraction_trigger import ExtractionTrigger
from app.chat.orchestrator.llm_enhancement_router import LLMEnhancementRouter
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


def test_llm_enhancement_router_is_disabled_by_default():
    router = LLMEnhancementRouter()
    trigger = ExtractionTrigger(event="reply.completed", question="继续分析课堂问题")
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂问题继续分析"},
        "conversation_memory": {"current_topics": ["课堂问题"]},
    }

    merged = router.apply(
        trigger=trigger,
        existing_state={},
        rule_patch=rule_patch,
        context={"resource_type": "chat"},
    )

    assert merged == rule_patch


def test_llm_enhancement_router_calls_enhancer_on_supported_trigger():
    seen = {}

    def enhancer(*, trigger, existing_state, rule_patch, context):
        seen["trigger"] = trigger.event
        seen["context"] = context
        return [
            ExtractionCandidate(
                field="student_signals",
                value=["后排学生多次走神"],
                source="llm",
            )
        ]

    router = LLMEnhancementRouter(enabled=True, enhancer=enhancer)
    trigger = ExtractionTrigger(
        event="reply.completed",
        conversation_id="conv-1",
        question="继续分析课堂问题",
    )
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂问题继续分析"},
        "conversation_memory": {"current_topics": ["课堂问题"]},
    }

    merged = router.apply(
        trigger=trigger,
        existing_state={},
        rule_patch=rule_patch,
        context={"resource_type": "chat"},
    )

    assert seen["trigger"] == "reply.completed"
    assert seen["context"] == {"resource_type": "chat"}
    assert merged["conversation_memory"]["student_signals"] == ["后排学生多次走神"]


def test_llm_enhancement_router_falls_back_to_rule_patch_when_enhancer_fails():
    def enhancer(*, trigger, existing_state, rule_patch, context):
        raise RuntimeError("model unavailable")

    router = LLMEnhancementRouter(enabled=True, enhancer=enhancer)
    trigger = ExtractionTrigger(
        event="reply.completed",
        conversation_id="conv-1",
        question="继续分析课堂问题",
    )
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂问题继续分析"},
        "conversation_memory": {"current_topics": ["课堂问题"]},
    }

    merged = router.apply(
        trigger=trigger,
        existing_state={},
        rule_patch=rule_patch,
        context={"resource_type": "chat"},
    )

    assert merged == rule_patch


def test_llm_enhancement_router_can_return_observation_report():
    def enhancer(*, trigger, existing_state, rule_patch, context):
        return [
            ExtractionCandidate(
                field="student_signals",
                value=["后排学生多次走神"],
                source="llm",
            )
        ]

    router = LLMEnhancementRouter(enabled=True, enhancer=enhancer)
    trigger = ExtractionTrigger(
        event="reply.completed",
        conversation_id="conv-1",
        question="继续分析课堂问题",
    )
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂问题继续分析"},
        "conversation_memory": {"current_topics": ["课堂问题"]},
    }

    merged, observation = router.apply_with_observation(
        trigger=trigger,
        existing_state={},
        rule_patch=rule_patch,
        context={"resource_type": "chat"},
    )

    assert merged["conversation_memory"]["student_signals"] == ["后排学生多次走神"]
    assert observation["trigger_event"] == "reply.completed"
    assert observation["candidate_fields"] == ["student_signals"]
    assert observation["accepted_fields"] == ["student_signals"]
    assert observation["fallback_reason"] is None


def test_conversation_store_adapter_can_apply_llm_enhancement_candidates():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-1", "hello")

    def enhancer(*, trigger, existing_state, rule_patch, context):
        assert trigger.event == "reply.completed"
        return [
            ExtractionCandidate(
                field="student_signals",
                value=["后排学生多次走神"],
                source="llm",
            )
        ]

    adapter = ConversationStoreAdapter(
        storage=storage,
        enhancement_router=LLMEnhancementRouter(enabled=True, enhancer=enhancer),
    )
    request = SimpleNamespace(
        question="请继续分析这节课的问题",
        owner="teacher-a",
        course_id=None,
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )

    adapter.write_v2_result(
        "conv-1",
        request,
        {
            "message": {"content": "这节课前10分钟举手响应较少。"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
        },
    )

    state = storage.get_state("conv-1")
    assert state["conversation_memory"]["student_signals"][0] == "后排学生多次走神"
    assert any("前10分钟" in item for item in state["conversation_memory"]["student_signals"])
