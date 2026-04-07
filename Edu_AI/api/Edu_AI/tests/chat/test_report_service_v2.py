from types import SimpleNamespace

from app.chat.application.report_service_v2 import ReportServiceV2, build_default_report_service_v2


class DummyRuntime:
    def __init__(self):
        self.calls = []

    def run(self, *, request, snapshot, decision):
        self.calls.append((request.question, decision.workflow_name))
        return {
            "message": {"role": "assistant", "content": "report"},
            "conversation": {"conversation_id": request.conversation_id or "conv-1"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "running"},
            "artifacts": [],
            "sources": [],
            "trace": {"path": "workflow", "workflow_name": "report"},
        }


class DummyBuilder:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def build(self, request):
        return self.snapshot


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, result["action"]["name"]))


class DummyStatusCardBuilder:
    def __init__(self):
        self.calls = []

    def build(self, *, snapshot, workflow, capability):
        self.calls.append((snapshot, workflow, capability))
        return {"mode": "workflow", "status_label": "正在生成报告", "source_labels": ["当前会话"]}


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


def test_report_service_calls_runtime_directly_and_writes_back():
    runtime = DummyRuntime()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    status_card_builder = DummyStatusCardBuilder()
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=runtime,
        conversation_store=DummyStore(),
        status_card_builder=status_card_builder,
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    result = service.report(payload)

    assert runtime.calls == [("生成报告", "report")]
    assert result["action"]["name"] == "generate.report"
    assert result["status_card"]["status_label"] == "正在生成报告"


def test_report_service_assigns_conversation_id_when_missing(monkeypatch):
    runtime = DummyRuntime()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    status_card_builder = DummyStatusCardBuilder()
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=runtime,
        conversation_store=DummyStore(),
        status_card_builder=status_card_builder,
    )
    monkeypatch.setattr("app.chat.application.report_service_v2.uuid4", lambda: SimpleNamespace(hex="fedcba9876543210"))
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id=None,
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    result = service.report(payload)

    assert result["conversation"]["conversation_id"] == "conv-fedcba987654"


def test_build_default_report_service_v2_builds_runtime_without_legacy_chat_service(monkeypatch):
    seen = {}

    def fake_build_engine(*, allow_rag=False, allow_web=False):
        seen["built"] = True
        seen["allow_rag"] = allow_rag
        seen["allow_web"] = allow_web

        class DummyEngine:
            def invoke(self, state):
                return {"reply": "ok", "status": "running"}

        return DummyEngine()

    monkeypatch.setattr("app.chat.application.report_service_v2.build_default_report_engine", fake_build_engine)

    service = build_default_report_service_v2()
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    result = service.report(payload)

    assert service is not None
    assert seen["built"] is True
    assert seen["allow_rag"] is False
    assert seen["allow_web"] is False
    assert result["action"]["name"] == "generate.report"


def test_report_service_preserves_report_config_in_trace():
    runtime = DummyRuntime()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    status_card_builder = DummyStatusCardBuilder()
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=runtime,
        conversation_store=DummyStore(),
        status_card_builder=status_card_builder,
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config={"topic": "课堂观察"},
        owner="u1",
    )

    result = service.report(payload)

    assert result["trace"]["input"]["report_config"]["topic"] == "课堂观察"


def test_report_service_uses_final_user_prompt_for_knowledge_base_entry():
    runtime = DummyRuntime()
    snapshot = SimpleNamespace(
        workflow_state=None,
        active_artifact=None,
        active_task=None,
        recent_messages=[{"role": "user", "content": "旧会话消息"}],
        summary="旧会话摘要",
        conversation_memory={"summary": "旧记忆"},
        active_context={"from_recent_messages": True},
    )
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=runtime,
        conversation_store=DummyStore(),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="旧问题",
        final_user_prompt="最终问题",
        prompt_draft="默认草稿",
        entry_mode="knowledge_base_report",
        selected_card={"card_id": "preset-brief", "card_type": "preset", "preset_key": "brief"},
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=["doc-1"],
        report_config=None,
        owner="u1",
    )

    result = service.report(payload)

    assert runtime.calls == [("最终问题", "report")]
    assert result["trace"]["input"]["entry_mode"] == "knowledge_base_report"
    assert result["trace"]["input"]["prompt_draft"] == "默认草稿"
    assert result["trace"]["input"]["final_user_prompt"] == "最终问题"


def test_report_service_ignores_conversation_snapshot_when_entry_mode_is_knowledge_base():
    seen = {}

    class RuntimeCapturingSnapshot:
        def run(self, *, request, snapshot, decision):
            seen["summary"] = getattr(snapshot, "summary", "")
            seen["recent_messages"] = list(getattr(snapshot, "recent_messages", []) or [])
            seen["conversation_memory"] = dict(getattr(snapshot, "conversation_memory", {}) or {})
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": request.conversation_id or "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    snapshot = SimpleNamespace(
        workflow_state=None,
        active_artifact=None,
        active_task=None,
        recent_messages=[{"role": "user", "content": "旧会话消息"}],
        summary="旧会话摘要",
        conversation_memory={"summary": "旧记忆"},
        active_context={"from_recent_messages": True},
    )
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=RuntimeCapturingSnapshot(),
        conversation_store=DummyStore(),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="生成报告",
        entry_mode="knowledge_base_report",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=["doc-1"],
        report_config=None,
        owner="u1",
    )

    service.report(payload)

    assert seen["summary"] == ""
    assert seen["recent_messages"] == []
    assert seen["conversation_memory"] == {}


def test_report_service_syncs_report_artifact_titles_from_report_config():
    class RuntimeWithArtifacts:
        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": request.conversation_id or "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [
                    {
                        "artifact_id": "outline-1",
                        "artifact_type": "report_outline",
                        "content": [{"chapter_id": 1, "chapter_title": "问题界定", "sections": []}],
                    },
                    {
                        "artifact_id": "report-1",
                        "artifact_type": "report",
                        "content": "# 占位标题\n\n正文",
                    },
                ],
                "sources": [],
                "trace": {
                    "path": "workflow",
                    "workflow_name": "report",
                    "report_preparation_result": {"report_subject": "课堂参与度分析"},
                },
            }

    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    status_card_builder = DummyStatusCardBuilder()
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=RuntimeWithArtifacts(),
        conversation_store=DummyStore(),
        status_card_builder=status_card_builder,
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config={"title": "高一物理课堂观察报告"},
        owner="u1",
    )

    result = service.report(payload)

    assert result["artifacts"][0]["title"] == "高一物理课堂观察报告-大纲.md"
    assert result["artifacts"][1]["title"] == "高一物理课堂观察报告.md"


def test_report_service_syncs_report_artifact_titles_from_secondary_markdown_heading():
    class RuntimeWithArtifacts:
        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": request.conversation_id or "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [
                    {
                        "artifact_id": "report-1",
                        "artifact_type": "report",
                        "title": "报告.md",
                        "content": "**摘要**：这是一段摘要。\n\n## 狂放不羁与理想主义：李白性格的多维解析\n\n正文",
                    },
                ],
                "sources": [],
                "trace": {
                    "path": "workflow",
                    "workflow_name": "report",
                },
            }

    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=RuntimeWithArtifacts(),
        conversation_store=DummyStore(),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    result = service.report(payload)

    assert result["artifacts"][0]["title"] == "狂放不羁与理想主义：李白性格的多维解析.md"


def test_build_default_report_service_v2_uses_request_capability_when_building_engine(monkeypatch):
    seen = {}

    def fake_build_engine(*, allow_rag, allow_web):
        seen["allow_rag"] = allow_rag
        seen["allow_web"] = allow_web

        class DummyEngine:
            def invoke(self, state):
                return {"reply": "ok", "status": "running"}

        return DummyEngine()

    monkeypatch.setattr("app.chat.application.report_service_v2.build_default_report_engine", fake_build_engine)

    service = build_default_report_service_v2()
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=True,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    service.report(payload)

    assert seen["allow_rag"] is True
    assert seen["allow_web"] is False


def test_report_service_persists_generated_report_to_course_materials():
    course_storage = DummyCourseStorageManager()

    class RuntimeWithArtifacts:
        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": request.conversation_id or "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [
                    {
                        "artifact_id": "report-1",
                        "artifact_type": "report",
                        "title": "高一物理课堂观察报告.md",
                        "content": "# 高一物理课堂观察报告\n\n正文",
                    },
                ],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=RuntimeWithArtifacts(),
        conversation_store=DummyStore(),
        status_card_builder=DummyStatusCardBuilder(),
        course_storage_manager=course_storage,
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id="course-1",
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    service.report(payload)

    assert len(course_storage.saved) == 1
    assert course_storage.saved[0]["course_id"] == "course-1"
    assert course_storage.saved[0]["material_type"] == "report"
    assert course_storage.saved[0]["material_id"] == "report-1"
    assert course_storage.saved[0]["material_data"]["title"] == "高一物理课堂观察报告.md"


def test_build_default_report_service_v2_wires_generation_context_dependencies(monkeypatch):
    seen = {}

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

    monkeypatch.setattr("app.chat.application.report_service_v2.ReportWorkflowRuntime", DummyRuntime)

    service = build_default_report_service_v2()
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    service.report(payload)

    assert seen["runtime_kwargs"]["generation_context_builder"] is not None
    assert seen["runtime_kwargs"]["report_assembler"] is not None
    assert getattr(service, "status_card_builder", None) is not None
