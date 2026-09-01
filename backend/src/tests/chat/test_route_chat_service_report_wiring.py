from pathlib import Path
import uuid

from app.chat.application.route_chat_service import RouteChatService
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage

from tests.chat.test_route_chat_service import DummyGateway, DummyLegacyService, DummyReportEngine


def test_route_chat_service_wires_llm_report_context_organizer(monkeypatch):
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    seen = {}

    class DummyRuntime:
        def __init__(self, **kwargs):
            seen["runtime_kwargs"] = kwargs

        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": request.conversation_id or "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    monkeypatch.setattr("app.chat.workflows.report.runtime.ReportWorkflowRuntime", DummyRuntime)

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
        conversation_id="conv-wire",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id=None,
        allow_web=False,
        action_hint="generate.report",
        artifact_id=None,
    )

    assert seen["runtime_kwargs"]["report_context_organizer"] is not None
    assert getattr(seen["runtime_kwargs"]["report_context_organizer"], "llm", None) is not None
    assert seen["runtime_kwargs"]["generation_readiness_judge"] is not None
