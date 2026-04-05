from pathlib import Path
import uuid
from types import SimpleNamespace

from app.chat.application.route_chat_service import RouteChatService
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


class DummyGateway:
    def chat(self, messages, temperature=0.2, max_tokens=1200):
        return "新链路持久化回复"


class DummyLegacyService:
    def chat(self, **kwargs):
        return {
            "answer": "旧回复",
            "conversation_id": kwargs.get("conversation_id") or "legacy-conv",
            "model_id": "",
            "intent_category": "chat",
            "meta": {},
        }

    def chat_stream_with_meta(self, **kwargs):
        return {"conversation_id": "legacy-conv"}, []

    @staticmethod
    def skill_health_check(meta):
        return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}


def test_new_fast_path_persists_user_and_assistant_messages():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        conversation_store=adapter,
    )

    data = service.chat(
        question="你好",
        conversation_id="conv-persist",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    messages = storage.get_messages("conv-persist")

    assert data["answer"] == "新链路持久化回复"
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_new_fast_path_persists_summary_and_memory_for_normal_chat():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        conversation_store=adapter,
    )

    service.chat(
        question="请分析关羽水淹七军为什么能赢",
        conversation_id="conv-persist-memory",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    state = storage.get_state("conv-persist-memory")

    assert "关羽水淹七军为什么能赢" in state["conversation_summary"]["summary_text"]
    assert state["conversation_memory"]["current_topics"]
    assert state["conversation_memory"]["user_goals"][0] == "分析问题"


def test_new_report_path_persists_workflow_state_and_active_artifact():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    class DummyReportEngine:
        def invoke(self, state):
            return {
                "final_response": "请确认报告大纲",
                "status": "awaiting_human",
                "phase": "confirming",
                "report_outline": [{"title": "一、背景"}],
                "report_slots": {"core_topic": "课堂管理"},
            }

    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        report_engine=DummyReportEngine(),
        enable_report_workflow=True,
        conversation_store=adapter,
    )

    data = service.chat(
        question="帮我整理成报告",
        conversation_id="conv-report",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint="generate.report",
        artifact_id=None,
    )

    state = storage.get_state("conv-report")

    assert "主题" in data["answer"]
    assert state["workflow_state"]["workflow_type"] == "report"
    assert state["active_task"] == "generate.report"
    assert state["workflow_state"]["status"] == "awaiting_confirm"
    assert state["workflow_state"]["stage"] == "critical_gap"
    assert "active_artifact" not in state


def test_new_report_path_persists_active_context_and_referenced_artifacts():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    class DummyReportEngine:
        def invoke(self, state):
            return {
                "final_response": "请确认报告大纲",
                "status": "awaiting_human",
                "phase": "confirming",
                "artifacts": [
                    {
                        "artifact_id": "conv-report-active:outline",
                        "artifact_type": "report_outline",
                        "title": "课堂观察报告大纲",
                    }
                ],
            }

    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        report_engine=DummyReportEngine(),
        enable_report_workflow=True,
        conversation_store=adapter,
    )

    service.chat(
        question="帮我整理成报告",
        conversation_id="conv-report-active",
        model_id=None,
        use_rag=False,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
        course_id="course-1",
        allow_web=False,
        action_hint="generate.report",
        artifact_id=None,
    )

    state = storage.get_state("conv-report-active")

    assert state["active_context"]["active_workflow_type"] == "report"
    assert state["active_context"]["active_workflow_status"] == "awaiting_confirm"
    assert state["active_context"]["active_artifact_type"] == ""
    assert state["active_context"]["current_course_id"] == "course-1"
    assert state["active_context"]["pinned_doc_ids"] == ["doc-1"]
    assert "referenced_artifact_ids" not in state


def test_new_stream_path_persists_messages_after_stream_finishes():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        conversation_store=adapter,
    )

    meta, stream = service.chat_stream_with_meta(
        question="你好",
        conversation_id="conv-stream-persist",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
    )
    events = list(stream)
    messages = storage.get_messages("conv-stream-persist")

    assert meta["conversation_id"] == "conv-stream-persist"
    assert any(event.get("type") == "delta" for event in events)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_write_v2_result_persists_report_preparation_into_workflow_filled_slots():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    request = SimpleNamespace(
        question="请基于当前内容生成一份报告",
        owner="teacher-a",
        course_id="course-1",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
    )
    result = {
        "message": {"role": "assistant", "content": "我将基于 Skills 怎么使用生成一版报告。可以直接开始吗？"},
        "action": {"name": "generate.report"},
        "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        "artifacts": [],
        "sources": [],
        "trace": {
            "report_preparation_result": {
                "report_subject": "Skills 怎么使用",
                "report_focus": "与 MCP 的差异和使用方式",
                "preparation_source": "llm_structured_output",
                "preparation_model": "deepseek-chat",
            }
        },
    }

    adapter.write_v2_result("conv-filled-slots", request, result)

    state = storage.get_state("conv-filled-slots")

    assert state["workflow_state"]["filled_slots"]["core_topic"] == "Skills 怎么使用"
    assert state["workflow_state"]["filled_slots"]["focus_area"] == "与 MCP 的差异和使用方式"
    assert state["workflow_state"]["filled_slots"]["__preparation_source"] == "llm_structured_output"
    assert state["workflow_state"]["filled_slots"]["__preparation_model"] == "deepseek-chat"
