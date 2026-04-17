from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2
from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter


class DummyStorage:
    def __init__(self):
        self.messages = []
        self.state = {}

    def ensure_conversation(self, conversation_id, question=None, owner=None):
        return None

    def append_message(
        self,
        conversation_id,
        role,
        content,
        sources=None,
        input_images=None,
        input_videos=None,
        message_kind=None,
    ):
        self.messages.append(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "sources": sources,
                "input_images": input_images,
                "input_videos": input_videos,
                "message_kind": message_kind,
            }
        )

    def get_state(self, conversation_id):
        return dict(self.state)

    def get_messages(self, conversation_id, limit=None):
        items = list(self.messages)
        if limit:
            return items[-limit:]
        return items

    def update_state(self, conversation_id, patch):
        self.state.update(patch)


def test_normalize_chat_request_preserves_artifact_reference():
    payload = SimpleNamespace(
        question="\u91cd\u5199\u7ed3\u8bba",
        conversation_id="conv-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "version_id": "v1",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
        },
    )

    request = normalize_chat_request(payload)

    assert request.artifact_reference.model_dump(exclude_none=True) == {
        "artifact_id": "report-1",
        "artifact_type": "report",
        "version_id": "v1",
        "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
    }


def test_write_v2_result_persists_active_artifact_reference():
    storage = DummyStorage()
    adapter = ConversationStoreAdapter(storage=storage)
    request = SimpleNamespace(
        question="\u91cd\u5199\u7ed3\u8bba",
        conversation_id="conv-1",
        course_id="course-1",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "version_id": "v1",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
        },
    )
    result = {
        "message": {"content": "\u5df2\u751f\u6210\uff0c\u8bf7\u5728\u53f3\u4fa7\u67e5\u770b\u3002"},
        "conversation": {"conversation_id": "conv-1"},
        "action": {"name": "report.edit"},
        "workflow": None,
        "artifacts": [],
        "sources": [],
        "trace": {"path": "fast"},
    }

    adapter.write_v2_result("conv-1", request, result)

    assert storage.state["active_artifact"]["artifact_id"] == "report-1"
    assert storage.state["active_context"]["active_artifact_id"] == "report-1"
    assert storage.state["active_context"]["active_artifact_type"] == "report"
    assert storage.state["active_context"]["active_reference_mode"] == "artifact_edit"
    assert storage.state["referenced_artifact_ids"] == ["report-1"]


def test_reply_service_prefers_report_edit_runtime_when_artifact_reference_present():
    calls = []

    class DummyEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            calls.append(
                {
                    "question": request.question,
                    "artifact_id": request.artifact_reference.artifact_id,
                    "course_id": request.course_id,
                }
            )
            return {
                "message": {"role": "assistant", "content": "\u5df2\u751f\u6210\uff0c\u8bf7\u5728\u53f3\u4fa7\u67e5\u770b\u3002"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "report.edit"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(dispatch=lambda request: None),
        report_edit_runtime=DummyEditRuntime(),
        conversation_store=SimpleNamespace(write_v2_result=lambda conversation_id, request, result: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
        ),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "workflow", "status_label": "\u5df2\u5b8c\u6210"}),
        course_storage_manager=SimpleNamespace(),
    )
    payload = SimpleNamespace(
        question="\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba",
        conversation_id="conv-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "version_id": "v1",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
        },
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "report.edit"
    assert calls == [{"question": "\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba", "artifact_id": "report-1", "course_id": "course-1"}]


def test_reply_service_routes_artifact_question_to_orchestrator_by_default():
    calls = {"dispatch": [], "edit": []}

    class DummyEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            calls["edit"].append(request.question)
            return {"message": {"role": "assistant", "content": "unexpected"}}

    orchestrator = SimpleNamespace(
        dispatch=lambda request: calls["dispatch"].append(request.question) or {
            "message": {"role": "assistant", "content": "artifact answer"},
            "conversation": {"conversation_id": request.conversation_id},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        }
    )
    service = ReplyServiceV2(
        orchestrator=orchestrator,
        report_edit_runtime=DummyEditRuntime(),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args, **kwargs: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
        ),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "chat"}),
        course_storage_manager=SimpleNamespace(),
    )
    payload = SimpleNamespace(
        question="\u8fd9\u4efd\u62a5\u544a\u7684\u6838\u5fc3\u89c2\u70b9\u662f\u4ec0\u4e48\uff1f",
        conversation_id="conv-ask-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "report.md",
        },
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "chat.reply"
    assert calls["dispatch"] == ["\u8fd9\u4efd\u62a5\u544a\u7684\u6838\u5fc3\u89c2\u70b9\u662f\u4ec0\u4e48\uff1f"]
    assert calls["edit"] == []


def test_reply_service_routes_explicit_artifact_edit_to_edit_runtime():
    calls = {"dispatch": [], "edit": []}

    class DummyEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            calls["edit"].append(request.question)
            return {
                "message": {"role": "assistant", "content": "\u5df2\u751f\u6210\uff0c\u8bf7\u5728\u53f3\u4fa7\u67e5\u770b\u3002"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "report.edit"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(dispatch=lambda request: calls["dispatch"].append(request.question)),
        report_edit_runtime=DummyEditRuntime(),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args, **kwargs: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
        ),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "workflow"}),
        course_storage_manager=SimpleNamespace(),
    )
    payload = SimpleNamespace(
        question="\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba",
        conversation_id="conv-edit-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "report.md",
        },
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "report.edit"
    assert calls["edit"] == ["\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba"]
    assert calls["dispatch"] == []


def test_reply_service_loads_report_artifact_context_for_ask_path():
    captured = {}

    class DummyOrchestrator:
        def dispatch(self, request):
            captured["artifact_reference"] = request.artifact_reference.model_dump(exclude_none=True)
            captured["artifact_context"] = getattr(request, "artifact_context", None)
            return {
                "message": {"role": "assistant", "content": "artifact answer"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    course_storage = SimpleNamespace(
        get_generated_material=lambda course_id, material_type, material_id: {
            "material_id": material_id,
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
            "report": "# \u674e\u767d\u6027\u683c\u5206\u6790\n\n## \u6458\u8981\n\u539f\u6458\u8981\u3002\n\n## \u7ed3\u8bba\n\u539f\u7ed3\u8bba\u3002",
        }
    )
    service = ReplyServiceV2(
        orchestrator=DummyOrchestrator(),
        report_edit_runtime=SimpleNamespace(run_from_request=lambda **kwargs: None),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args, **kwargs: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
        ),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "chat"}),
        course_storage_manager=course_storage,
    )
    payload = SimpleNamespace(
        question="\u8fd9\u4efd\u62a5\u544a\u7684\u6838\u5fc3\u89c2\u70b9\u662f\u4ec0\u4e48\uff1f",
        conversation_id="conv-artifact-ctx",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
        },
    )

    service.reply(payload)

    assert captured["artifact_reference"]["artifact_type"] == "report"
    assert captured["artifact_context"]["artifact_type"] == "report"
    assert "## \u6458\u8981" in captured["artifact_context"]["context_text"]


def test_reply_service_routes_ppt_question_to_ask_path_when_no_slide_edit_intent():
    captured = {}

    class DummyOrchestrator:
        def dispatch(self, request):
            captured["artifact_context"] = getattr(request, "artifact_context", None)
            return {
                "message": {"role": "assistant", "content": "ppt answer"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    course_storage = SimpleNamespace(
        get_generated_material=lambda course_id, material_type, material_id: {
            "material_id": material_id,
            "title": "TCP \u4e09\u6b21\u63e1\u624b\u8bfe\u4ef6.pptx",
            "content": {"job_id": "job_001", "revision_id": "rev_0000", "slide_count": 6},
            "outline": {"slides": [{"slide_index": 3, "title": "\u4e09\u6b21\u63e1\u624b\u8fc7\u7a0b"}]},
        }
    )
    service = ReplyServiceV2(
        orchestrator=DummyOrchestrator(),
        ppt_edit_runtime=SimpleNamespace(run_from_request=lambda **kwargs: None),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args, **kwargs: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
        ),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "chat"}),
        course_storage_manager=course_storage,
    )

    payload = SimpleNamespace(
        question="\u8fd9\u4efd PPT \u7b2c\u4e09\u9875\u4e3b\u8981\u8bb2\u4e86\u4ec0\u4e48\uff1f",
        conversation_id="conv-ppt-ask",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={"artifact_id": "ppt-1", "artifact_type": "ppt_deck", "title": "TCP \u4e09\u6b21\u63e1\u624b\u8bfe\u4ef6.pptx"},
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "chat.reply"
    assert "\u7b2c 3 \u9875\uff1a\u4e09\u6b21\u63e1\u624b\u8fc7\u7a0b" in captured["artifact_context"]["context_text"]
