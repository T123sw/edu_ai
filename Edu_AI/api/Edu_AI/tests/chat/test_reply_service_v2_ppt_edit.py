from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter


class DummyStorage:
    def __init__(self):
        self.messages = []
        self.state = {}

    def ensure_conversation(self, conversation_id, question=None, owner=None):
        return None

    def append_message(self, conversation_id, role, content, sources=None, message_kind=None):
        self.messages.append(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "sources": sources,
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


def test_write_v2_result_updates_artifact_reference_to_latest_ppt_deck():
    storage = DummyStorage()
    adapter = ConversationStoreAdapter(storage=storage)
    request = SimpleNamespace(
        question="make slide 3 simpler",
        conversation_id="conv-ppt-1",
        course_id="course-1",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
        artifact_reference={
            "artifact_id": "ppt-deck-1",
            "artifact_type": "ppt_deck",
            "title": "deck.pptx",
            "source_conversation_id": "conv-ppt-1",
            "source_course_id": "course-1",
        },
    )
    result = {
        "message": {"content": "updated"},
        "conversation": {"conversation_id": "conv-ppt-1"},
        "action": {"name": "ppt.edit"},
        "workflow": {"type": "ppt", "status": "completed", "phase": "completed"},
        "artifacts": [
            {
                "artifact_id": "conv-ppt:outline",
                "artifact_type": "ppt_outline",
                "title": "deck-outline",
                "content": {"deck_title": "deck", "slides": [{"slide_index": 3, "title": "flow"}]},
            },
            {
                "artifact_id": "ppt-deck-1:rev_0001",
                "artifact_type": "ppt_deck",
                "title": "deck.pptx",
                "content": {"job_id": "job_001", "revision_id": "rev_0001"},
            },
        ],
        "sources": [],
        "trace": {"path": "workflow"},
    }

    adapter.write_v2_result("conv-ppt-1", request, result)

    assert storage.state["artifact_reference"]["artifact_id"] == "ppt-deck-1:rev_0001"
    assert storage.state["artifact_reference"]["artifact_type"] == "ppt_deck"
    assert storage.state["active_artifact"]["artifact_id"] == "ppt-deck-1:rev_0001"


def test_reply_service_routes_ppt_artifact_references_to_ppt_edit_runtime():
    report_calls = []
    ppt_calls = []

    class DummyReportEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            report_calls.append(request.question)
            return {}

    class DummyPptEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            ppt_calls.append(
                {
                    "question": request.question,
                    "artifact_id": request.artifact_reference.artifact_id,
                    "course_id": request.course_id,
                }
            )
            return {
                "message": {"role": "assistant", "content": "started"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "ppt.edit"},
                "workflow": {"type": "ppt", "status": "running", "phase": "polling_revision"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(dispatch=lambda request: None),
        report_edit_runtime=DummyReportEditRuntime(),
        ppt_edit_runtime=DummyPptEditRuntime(),
        conversation_store=SimpleNamespace(write_v2_result=lambda conversation_id, request, result: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(
                workflow_state=None,
                active_artifact=None,
                active_task=None,
                recent_messages=[],
            )
        ),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "workflow", "status_label": "running"}),
        course_storage_manager=SimpleNamespace(),
    )
    payload = SimpleNamespace(
        question="make slide 3 simpler",
        conversation_id="conv-ppt-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "ppt-deck-1",
            "artifact_type": "ppt_deck",
            "title": "deck.pptx",
        },
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "ppt.edit"
    assert report_calls == []
    assert ppt_calls == [{"question": "make slide 3 simpler", "artifact_id": "ppt-deck-1", "course_id": "course-1"}]


def test_reply_service_refreshes_running_ppt_edit_without_appending_poll_user_message():
    storage = DummyStorage()
    storage.state = {
        "workflow_state": {
            "workflow_id": "conv-ppt-1",
            "workflow_type": "ppt",
            "status": "running",
            "stage": "polling_revision",
            "required_slots": [],
            "filled_slots": {},
            "artifacts": [
                {
                    "artifact_id": "conv-ppt:outline",
                    "artifact_type": "ppt_outline",
                    "title": "deck-outline",
                    "content": {"deck_title": "deck", "slides": [{"slide_index": 3, "title": "flow"}]},
                },
                {
                    "artifact_id": "ppt-deck-1",
                    "artifact_type": "ppt_deck",
                    "title": "deck.pptx",
                    "content": {"job_id": "job_001", "revision_id": "rev_0001", "slide_count": 16},
                    "generation_state": {
                        "status": "running",
                        "phase": "polling_revision",
                        "generation_mode": "revise_ppt",
                        "pending_revision_id": "rev_0002",
                        "target_slide_index": 3,
                        "source_revision_id": "rev_0001",
                    },
                },
            ],
        },
        "artifact_reference": {
            "artifact_id": "ppt-deck-1",
            "artifact_type": "ppt_deck",
            "title": "deck.pptx",
            "source_conversation_id": "conv-ppt-1",
            "source_course_id": "course-1",
        },
        "active_context": {
            "current_course_id": "course-1",
        },
        "capability_policy": {
            "allow_rag": False,
            "allow_web": False,
            "selected_doc_ids": [],
        },
    }

    class DummyPptEditRuntime:
        def resume_from_snapshot(self, *, request, snapshot, course_storage_manager):
            return {
                "message": {"role": "assistant", "content": "completed"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "ppt.edit"},
                "workflow": {"type": "ppt", "status": "completed", "phase": "completed"},
                "artifacts": [
                    {
                        "artifact_id": "conv-ppt:outline",
                        "artifact_type": "ppt_outline",
                        "title": "deck-outline",
                        "content": {"deck_title": "deck", "slides": [{"slide_index": 3, "title": "flow"}]},
                    },
                    {
                        "artifact_id": "ppt-deck-1:rev_0002",
                        "artifact_type": "ppt_deck",
                        "title": "deck.pptx",
                        "content": {"job_id": "job_001", "revision_id": "rev_0002", "slide_count": 16},
                    },
                ],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    adapter = ConversationStoreAdapter(storage=storage)
    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(dispatch=lambda request: None),
        conversation_store=adapter,
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(
                workflow_state=SimpleNamespace(**storage.state["workflow_state"]),
                active_artifact=None,
                active_task=None,
                recent_messages=[],
            )
        ),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "workflow", "status_label": "completed"}),
        course_storage_manager=SimpleNamespace(),
        ppt_edit_runtime=DummyPptEditRuntime(),
    )

    refreshed = service.refresh_running_conversation(
        SimpleNamespace(
            question="",
            conversation_id="conv-ppt-1",
            owner="u1",
            course_id="course-1",
            capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
            artifact_reference=SimpleNamespace(
                artifact_id="ppt-deck-1",
                artifact_type="ppt_deck",
                title="deck.pptx",
            ),
        )
    )

    assert refreshed is not None
    assert storage.state["workflow_state"]["status"] == "completed"
    assert storage.state["artifact_reference"]["artifact_id"] == "ppt-deck-1:rev_0002"
    assert [message["role"] for message in storage.messages] == ["assistant"]
    assert storage.messages[0]["content"] == "completed"
