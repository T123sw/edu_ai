from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2, build_default_reply_service_v2


class DummyOrchestrator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def dispatch(self, request):
        self.calls.append(request)
        return self.result


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result["action"]["name"]))


class DummyStatusCardBuilder:
    def __init__(self):
        self.calls = []

    def build(self, *, snapshot, workflow, capability):
        self.calls.append((snapshot, workflow, capability))
        return {"mode": "chat", "status_label": "普通对话", "source_labels": ["当前会话"]}


class DummyCourseStorageManager:
    def __init__(self):
        self.saved = []

    def save_generated_material(self, *, course_id, material_type, material_id, material_data, file_data=None):
        self.saved.append(
            {
                "course_id": course_id,
                "material_type": material_type,
                "material_id": material_id,
                "material_data": material_data,
                "file_data": file_data,
            }
        )
        return True


def test_reply_service_returns_orchestrator_result_and_writes_back():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "ok"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        }
    )
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReplyServiceV2(
        orchestrator=orchestrator,
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="hello",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "chat.reply"
    assert store.saved == [("conv-1", "hello", "chat.reply")]
    assert result["status_card"]["status_label"] == "普通对话"


def test_reply_service_preserves_report_switch_result():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "report"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "running"},
            "artifacts": [],
            "sources": [],
            "trace": {"path": "workflow", "workflow_name": "report"},
        }
    )
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReplyServiceV2(
        orchestrator=orchestrator,
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert result["workflow"]["type"] == "report"
    assert store.saved == [("conv-1", "生成报告", "generate.report")]


def test_reply_service_shortens_report_reply_and_persists_course_material():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "这里是很长的报告正文，不应该直接出现在对话区。"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "completed"},
            "artifacts": [
                {
                    "artifact_id": "outline-1",
                    "artifact_type": "report_outline",
                    "title": "报告大纲.md",
                    "content": [{"chapter_id": 1, "chapter_title": "问题界定", "sections": []}],
                },
                {
                    "artifact_id": "report-1",
                    "artifact_type": "report",
                    "title": "报告.md",
                    "content": "# 高一物理课堂观察报告\n\n正文",
                },
            ],
            "sources": [],
            "trace": {"path": "workflow", "workflow_name": "report"},
        }
    )
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    course_storage = DummyCourseStorageManager()
    service = ReplyServiceV2(
        orchestrator=orchestrator,
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
        course_storage_manager=course_storage,
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert result["message"]["content"] == "已生成，请在右侧查看。"
    assert result["artifacts"][0]["title"] == "高一物理课堂观察报告-大纲.md"
    assert result["artifacts"][1]["title"] == "高一物理课堂观察报告.md"
    assert course_storage.saved[0]["course_id"] == "course-1"
    assert course_storage.saved[0]["material_data"]["title"] == "高一物理课堂观察报告.md"


def test_reply_service_persists_report_version_metadata_and_generation_state():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "report.edit"},
            "workflow": {"type": "report", "status": "completed"},
            "artifacts": [
                {
                    "artifact_id": "report-2",
                    "artifact_type": "report",
                    "title": "李白性格分析.md",
                    "content": "# 李白性格分析\n\n正文",
                    "version": {
                        "version_id": "v2",
                        "version_number": 2,
                        "parent_artifact_id": "report-1",
                        "root_artifact_id": "report-root",
                    },
                    "generation_state": {
                        "generation_mode": "revise_report",
                        "source_report_artifact_id": "report-1",
                    },
                },
            ],
            "sources": [],
            "trace": {"path": "workflow"},
        }
    )
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    course_storage = DummyCourseStorageManager()
    service = ReplyServiceV2(
        orchestrator=orchestrator,
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
        course_storage_manager=course_storage,
    )
    payload = SimpleNamespace(
        question="重写结论",
        conversation_id="conv-1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    service.reply(payload)

    assert course_storage.saved[0]["material_data"]["version"]["version_id"] == "v2"
    assert course_storage.saved[0]["material_data"]["generation_state"]["generation_mode"] == "revise_report"


def test_build_default_reply_service_v2_wires_course_storage_manager(monkeypatch):
    seen = {}

    class DummyGateway:
        def chat(self, messages):
            return "ok"

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question, owner=None):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    course_storage_marker = object()

    monkeypatch.setattr("app.chat.application.reply_service_v2.build_default_gateway", lambda model_id=None: DummyGateway())
    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.ConversationStoreAdapter",
        lambda: SimpleNamespace(
            storage=DummyStoreImpl(),
            load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
            write_v2_result=lambda conversation_id, request, result: None,
        ),
    )
    monkeypatch.setattr("app.chat.application.reply_service_v2.default_course_storage_manager", course_storage_marker)

    service = build_default_reply_service_v2()

    assert service.course_storage_manager is course_storage_marker


def test_reply_service_assigns_conversation_id_when_missing(monkeypatch):
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "ok"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        }
    )
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReplyServiceV2(
        orchestrator=orchestrator,
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
    )
    monkeypatch.setattr("app.chat.application.reply_service_v2.uuid4", lambda: SimpleNamespace(hex="abc123def4567890"))
    payload = SimpleNamespace(
        question="hello",
        conversation_id=None,
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert result["conversation"]["conversation_id"] == "conv-abc123def456"
    assert store.saved == [("conv-abc123def456", "hello", "chat.reply")]


def test_build_default_reply_service_v2_returns_service(monkeypatch):
    class DummyGateway:
        def chat(self, messages):
            return "ok"

    monkeypatch.setattr("app.chat.application.reply_service_v2.build_default_gateway", lambda model_id=None: DummyGateway())

    service = build_default_reply_service_v2()

    assert service is not None


def test_build_default_reply_service_v2_uses_request_capability_when_switching_to_report(monkeypatch):
    seen = {}

    class DummyGateway:
        def chat(self, messages):
            return "ok"

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    def fake_build_engine(*, allow_rag=False, allow_web=False):
        seen["allow_rag"] = allow_rag
        seen["allow_web"] = allow_web

        class DummyEngine:
            def invoke(self, state):
                return {"reply": "report", "status": "running"}

        return DummyEngine()

    monkeypatch.setattr("app.chat.application.reply_service_v2.build_default_gateway", lambda model_id=None: DummyGateway())
    monkeypatch.setattr("app.chat.application.reply_service_v2.ConversationStoreAdapter", lambda: SimpleNamespace(
        storage=DummyStoreImpl(),
        load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
        write_v2_result=lambda conversation_id, request, result: None,
    ))
    monkeypatch.setattr("app.chat.application.reply_service_v2.build_default_report_engine", fake_build_engine)

    service = build_default_reply_service_v2()
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=True,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert seen["allow_rag"] is True
    assert seen["allow_web"] is False
    assert result["action"]["name"] == "generate.report"


def test_build_default_reply_service_v2_uses_request_model_id_for_gateway(monkeypatch):
    seen = {}

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    class DummyGateway:
        def chat(self, messages):
            return "ok"

    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.ConversationStoreAdapter",
        lambda: SimpleNamespace(
            storage=DummyStoreImpl(),
            load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
            write_v2_result=lambda conversation_id, request, result: None,
        ),
    )

    def fake_build_default_gateway(model_id=None):
        seen["model_id"] = model_id
        return DummyGateway()

    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.build_default_gateway",
        fake_build_default_gateway,
    )

    service = build_default_reply_service_v2()
    payload = SimpleNamespace(
        question="hello",
        conversation_id="conv-1",
        model_id="custom-model",
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    service.reply(payload)

    assert seen["model_id"] == "custom-model"


def test_build_default_reply_service_v2_uses_rag_retriever_for_fast_chat(monkeypatch):
    seen = {}

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    class DummyGateway:
        def __init__(self):
            self.last_messages = None

        def chat(self, messages):
            self.last_messages = messages
            return "ok"

    gateway = DummyGateway()

    def fake_rag_search_tool(*, query, top_k=5, selected_doc_ids=None, owner=None):
        seen["query"] = query
        seen["top_k"] = top_k
        seen["selected_doc_ids"] = list(selected_doc_ids or [])
        seen["owner"] = owner
        return {
            "ok": True,
            "payload": {
                "answer": "rag summary",
                "sources": [{"source": "doc-1", "content": "chunk", "page": 1}],
            },
        }

    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.ConversationStoreAdapter",
        lambda: SimpleNamespace(
            storage=DummyStoreImpl(),
            load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
            write_v2_result=lambda conversation_id, request, result: None,
        ),
    )
    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.build_default_gateway",
        lambda model_id=None: gateway,
    )
    monkeypatch.setattr("app.chat.application.reply_service_v2.rag_search_tool", fake_rag_search_tool)

    service = build_default_reply_service_v2()
    payload = SimpleNamespace(
        question="根据知识库总结关羽生平",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=True,
        allow_web=False,
        selected_doc_ids=["doc-1"],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert seen == {
        "query": "根据知识库总结关羽生平",
        "top_k": 5,
        "selected_doc_ids": ["doc-1"],
        "owner": "u1",
    }
    assert result["sources"][0]["source"] == "doc-1"
    assert "rag summary" in gateway.last_messages[-1]["content"]


def test_build_default_reply_service_v2_uses_web_retriever_for_fast_chat(monkeypatch):
    seen = {}

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    class DummyGateway:
        def __init__(self):
            self.last_messages = None

        def chat(self, messages):
            self.last_messages = messages
            return "ok"

    gateway = DummyGateway()

    def fake_web_search_tool(*, query, owner=None):
        seen["query"] = query
        seen["owner"] = owner
        return {
            "ok": True,
            "payload": {
                "summary": "web summary",
                "sources": [{"source": "https://example.com", "content": "chunk", "page": 0}],
            },
        }

    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.ConversationStoreAdapter",
        lambda: SimpleNamespace(
            storage=DummyStoreImpl(),
            load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
            write_v2_result=lambda conversation_id, request, result: None,
        ),
    )
    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.build_default_gateway",
        lambda model_id=None: gateway,
    )
    monkeypatch.setattr("app.chat.application.reply_service_v2.web_search_tool", fake_web_search_tool)

    service = build_default_reply_service_v2()
    payload = SimpleNamespace(
        question="请联网总结关羽生平",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=True,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert seen == {
        "query": "请联网总结关羽生平",
        "owner": "u1",
    }
    assert result["sources"][0]["source"] == "https://example.com"
    assert "web summary" in gateway.last_messages[-1]["content"]


def test_build_default_reply_service_v2_wires_generation_context_dependencies(monkeypatch):
    seen = {}
    llm_marker = object()

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question, owner=None):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    class DummyGateway:
        def chat(self, messages):
            return "ok"

    class DummyRuntime:
        def __init__(self, **kwargs):
            seen["runtime_kwargs"] = kwargs

        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": request.conversation_id or "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.ConversationStoreAdapter",
        lambda: SimpleNamespace(
            storage=DummyStoreImpl(),
            load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
            write_v2_result=lambda conversation_id, request, result: None,
        ),
    )
    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.build_default_gateway",
        lambda model_id=None: DummyGateway(),
    )
    monkeypatch.setattr("app.chat.application.reply_service_v2.ReportWorkflowRuntime", DummyRuntime)
    monkeypatch.setattr("app.chat.application.reply_service_v2.get_fallback_llm", lambda: llm_marker)

    service = build_default_reply_service_v2()
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint="generate.report",
        owner="u1",
    )

    service.reply(payload)

    assert seen["runtime_kwargs"]["generation_context_builder"] is not None
    assert seen["runtime_kwargs"]["report_assembler"] is not None
    assert seen["runtime_kwargs"]["report_context_organizer"] is not None
    assert getattr(seen["runtime_kwargs"]["report_context_organizer"], "llm", None) is llm_marker
    assert seen["runtime_kwargs"]["generation_readiness_judge"] is not None
    assert getattr(service, "status_card_builder", None) is not None
    assert getattr(service, "context_builder", None) is not None


def test_build_default_reply_service_v2_uses_fallback_llm_for_full_ppt_workflow(monkeypatch):
    seen = {}
    fallback_llm_marker = object()

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question, owner=None):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    class DummyGateway:
        def chat(self, messages):
            return "ok"

    class DummyReportRuntime:
        def __init__(self, **kwargs):
            seen["report_runtime_kwargs"] = kwargs

        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": request.conversation_id or "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    class DummyPptRuntime:
        def __init__(self, **kwargs):
            seen["ppt_runtime_kwargs"] = kwargs

        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "ppt"},
                "conversation": {"conversation_id": request.conversation_id or "conv-2"},
                "action": {"name": "generate.ppt"},
                "workflow": {"type": "ppt", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "ppt"},
            }

    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.ConversationStoreAdapter",
        lambda: SimpleNamespace(
            storage=DummyStoreImpl(),
            load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
            write_v2_result=lambda conversation_id, request, result: None,
        ),
    )
    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.build_default_gateway",
        lambda model_id=None: DummyGateway(),
    )
    monkeypatch.setattr("app.chat.application.reply_service_v2.ReportWorkflowRuntime", DummyReportRuntime)
    monkeypatch.setattr("app.chat.application.reply_service_v2.PptWorkflowRuntime", DummyPptRuntime)
    monkeypatch.setattr("app.chat.application.reply_service_v2.get_fallback_llm", lambda: fallback_llm_marker)

    service = build_default_reply_service_v2()
    payload = SimpleNamespace(
        question="生成 PPT",
        conversation_id="conv-2",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint="generate.ppt",
        owner="u1",
    )

    service.reply(payload)

    assert getattr(seen["report_runtime_kwargs"]["report_context_organizer"], "llm", None) is fallback_llm_marker
    assert getattr(seen["ppt_runtime_kwargs"]["ppt_context_organizer"], "llm", None) is fallback_llm_marker
    assert getattr(seen["ppt_runtime_kwargs"]["outline_builder"], "llm", None) is fallback_llm_marker
    assert getattr(seen["ppt_runtime_kwargs"]["content_markdown_generator"], "llm", None) is fallback_llm_marker
    assert "slide_plan_builder" not in seen["ppt_runtime_kwargs"]
    assert "content_markdown_assembler" not in seen["ppt_runtime_kwargs"]
    assert "content_reviewer" not in seen["ppt_runtime_kwargs"]
    assert "content_optimizer" not in seen["ppt_runtime_kwargs"]
