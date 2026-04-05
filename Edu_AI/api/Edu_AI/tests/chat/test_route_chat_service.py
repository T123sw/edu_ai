from pathlib import Path
from types import SimpleNamespace
import uuid

from app.chat.application.route_chat_service import RouteChatService
from app.chat.domain.extraction_candidate import ExtractionCandidate
from app.chat.orchestrator.llm_enhancement_router import LLMEnhancementRouter
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


class DummyGateway:
    def chat(self, messages, temperature=0.2, max_tokens=1200):
        return "新链路回复"


class DummyLegacyService:
    def __init__(self):
        self.calls = []
        self.stream_calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "answer": "旧链路回复",
            "conversation_id": kwargs.get("conversation_id") or "legacy-conv",
            "model_id": kwargs.get("model_id") or "",
            "intent_category": "chat",
            "meta": {},
        }

    def chat_stream_with_meta(self, **kwargs):
        self.stream_calls.append(kwargs)
        return {"conversation_id": "legacy-conv"}, []

    @staticmethod
    def skill_health_check(meta):
        return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}

    @staticmethod
    def get_report_engine():
        return None


class DummyReportEngine:
    def invoke(self, state):
        return {
            "final_response": "报告工作流回复",
            "status": "awaiting_human",
            "phase": "confirming",
            "report_outline": [{"title": "一、背景"}],
            "report_slots": {"core_topic": "课堂管理"},
        }


def test_route_chat_service_uses_new_path_for_fast_chat():
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
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert data["answer"] == "新链路回复"
    assert data["intent_category"] == "chat"


def test_route_chat_service_falls_back_when_disabled():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        conversation_store=adapter,
    )

    data = service.chat(
        question="你好",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert data["answer"] == "旧链路回复"


def test_route_chat_service_falls_back_when_fast_runtime_disabled():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        enable_fast_runtime=False,
        conversation_store=adapter,
    )

    data = service.chat(
        question="你好",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert data["answer"] == "旧链路回复"


def test_route_chat_service_can_attach_llm_enhancement_trace_to_result_and_state():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")

    def enhancer(*, trigger, existing_state, rule_patch, context):
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
        enhancement_trace_enabled=True,
    )
    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        conversation_store=adapter,
        enhancement_trace_enabled=True,
    )

    data = service.chat(
        question="继续分析这节课的问题",
        conversation_id="conv-enh-trace",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    trace = data["meta"]["trace"]["llm_enhancement"]
    assert trace["trigger_event"] == "reply.completed"
    assert trace["candidate_fields"] == ["student_signals"]
    assert trace["accepted_fields"] == ["student_signals"]

    state = storage.get_state("conv-enh-trace")
    assert state["llm_enhancement_trace"]["candidate_fields"] == ["student_signals"]


def test_route_chat_service_falls_back_for_unsupported_workflow():
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
        question="帮我查一下最新课程标准",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint="research.lookup",
        artifact_id=None,
    )

    assert data["answer"] == "旧链路回复"


def test_route_chat_service_uses_report_workflow_when_engine_available():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
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
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint="generate.report",
        artifact_id=None,
    )

    assert "主题" in data["answer"]
    assert data["intent_category"] == "generate_content"


def test_route_chat_service_report_workflow_can_be_disabled_by_flag():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        report_engine=DummyReportEngine(),
        enable_report_workflow=False,
        conversation_store=adapter,
    )

    data = service.chat(
        question="帮我整理成报告",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint="generate.report",
        artifact_id=None,
    )

    assert data["answer"] == "旧链路回复"


def test_route_chat_service_enforces_capability_policy_on_legacy_fallback():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        enforce_capability_policy=True,
        conversation_store=adapter,
    )

    service.chat(
        question="查一下资料",
        conversation_id="conv-1",
        model_id=None,
        use_rag=True,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert legacy.calls[-1]["use_rag"] is True
    assert legacy.calls[-1]["allow_web"] is False


def test_route_chat_service_blocks_inferred_rag_when_policy_enforced_and_frontend_disables_it():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        enforce_capability_policy=True,
        conversation_store=adapter,
    )

    service.chat(
        question="查一下资料",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert legacy.calls[-1]["use_rag"] is False


def test_route_chat_service_preserves_explicit_allow_rag_false_when_selected_docs_exist():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        enforce_capability_policy=True,
        conversation_store=adapter,
    )

    service.chat(
        question="查一下资料",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        allow_rag=False,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert legacy.calls[-1]["use_rag"] is False


def test_route_chat_service_stream_uses_new_fast_path():
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
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
    )
    events = list(stream)

    assert meta["conversation_id"] == "conv-1"
    assert any(event.get("type") == "delta" for event in events)
    assert events[-1]["type"] == "done"


def test_route_chat_service_stream_falls_back_for_workflow():
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
        question="帮我查一下最新课程标准",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        action_hint="research.lookup",
    )

    assert meta["conversation_id"] == "legacy-conv"
    assert list(stream) == []


def test_route_chat_service_stream_falls_back_when_fast_runtime_disabled():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        enable_fast_runtime=False,
        conversation_store=adapter,
    )

    meta, stream = service.chat_stream_with_meta(
        question="你好",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
    )

    assert meta["conversation_id"] == "legacy-conv"
    assert list(stream) == []
    assert legacy.stream_calls[-1]["use_rag"] is False


def test_route_chat_service_stream_enforces_capability_policy_on_legacy_fallback():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        enforce_capability_policy=True,
        conversation_store=adapter,
    )

    meta, stream = service.chat_stream_with_meta(
        question="查一下资料",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
        course_id=None,
    )

    assert meta["conversation_id"] == "legacy-conv"
    assert list(stream) == []
    assert legacy.stream_calls[-1]["use_rag"] is False


def test_route_chat_service_forwards_extended_runtime_fields_to_legacy_fallback():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        conversation_store=adapter,
    )

    service.chat(
        question="查一下资料",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
        course_id=None,
        allow_web=True,
        action_hint="research.lookup",
        artifact_id="artifact-1",
    )

    assert legacy.calls[-1]["allow_web"] is True
    assert legacy.calls[-1]["action_hint"] == "research.lookup"
    assert legacy.calls[-1]["artifact_id"] == "artifact-1"


def test_route_chat_service_can_use_report_engine_from_legacy_runtime():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    class LegacyWithReportEngine(DummyLegacyService):
        @staticmethod
        def get_report_engine():
            return DummyReportEngine()

    service = RouteChatService(
        legacy_service=LegacyWithReportEngine(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        enable_report_workflow=True,
        conversation_store=adapter,
    )

    data = service.chat(
        question="帮我整理成报告",
        conversation_id="conv-1",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint="generate.report",
        artifact_id=None,
    )

    assert data["intent_category"] == "generate_content"


def test_route_chat_service_restores_course_id_from_conversation_state():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-course", "hello")
    storage.update_state("conv-course", {"course_id": "course-1"})
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        conversation_store=adapter,
    )

    service.chat(
        question="hello",
        conversation_id="conv-course",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert legacy.calls[-1]["course_id"] == "course-1"


def test_route_chat_service_persists_course_id_on_chat_requests():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        conversation_store=adapter,
    )

    service.chat(
        question="hello",
        conversation_id="conv-course-write",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id="course-2",
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    assert storage.get_state("conv-course-write")["course_id"] == "course-2"
    assert legacy.calls[-1]["course_id"] == "course-2"


def test_route_chat_service_stream_restores_course_id_from_conversation_state():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-course-stream", "hello")
    storage.update_state("conv-course-stream", {"course_id": "course-stream"})
    adapter = ConversationStoreAdapter(storage=storage)
    legacy = DummyLegacyService()
    service = RouteChatService(
        legacy_service=legacy,
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=False,
        conversation_store=adapter,
    )

    meta, stream = service.chat_stream_with_meta(
        question="hello",
        conversation_id="conv-course-stream",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
    )

    assert meta["conversation_id"] == "legacy-conv"
    assert list(stream) == []
    assert legacy.stream_calls[-1]["course_id"] == "course-stream"
