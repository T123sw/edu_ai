from types import SimpleNamespace

from app.chat.application.request_normalizer import normalize_chat_request


def test_normalize_v1_request_maps_to_v2_defaults():
    payload = SimpleNamespace(
        question="你好",
        conversation_id=None,
        model_id=None,
        owner="teacher-a",
        course_id="course-1",
        artifact_id=None,
        use_rag=None,
        allow_rag=False,
        allow_web=False,
        action_hint=None,
        selected_doc_ids=None,
    )

    result = normalize_chat_request(payload)

    assert result.question == "你好"
    assert result.owner == "teacher-a"
    assert result.course_id == "course-1"
    assert result.capability.allow_rag is False
    assert result.capability.allow_web is False
    assert result.action_hint is None


def test_normalize_v1_use_rag_is_supported_when_allow_rag_missing():
    payload = SimpleNamespace(
        question="查资料",
        conversation_id="conv-1",
        model_id="model-a",
        owner=None,
        course_id=None,
        artifact_id=None,
        use_rag=True,
        allow_web=False,
        action_hint="research.lookup",
        selected_doc_ids=["doc-1"],
    )

    result = normalize_chat_request(payload)

    assert result.conversation_id == "conv-1"
    assert result.model_id == "model-a"
    assert result.capability.allow_rag is True
    assert result.capability.selected_doc_ids == ["doc-1"]
    assert result.action_hint == "research.lookup"


def test_normalize_request_enables_rag_when_selected_docs_exist():
    payload = SimpleNamespace(
        question="查资料",
        conversation_id="conv-1",
        model_id=None,
        owner="teacher-a",
        course_id=None,
        artifact_id=None,
        use_rag=False,
        allow_rag=False,
        allow_web=False,
        action_hint=None,
        selected_doc_ids=["doc-1"],
    )

    result = normalize_chat_request(payload)

    assert result.capability.allow_rag is True
    assert result.capability.allow_tools is True
    assert result.capability.selected_doc_ids == ["doc-1"]


def test_normalize_request_preserves_workspace_scope():
    payload = SimpleNamespace(
        question="hello",
        conversation_id="conv-scope",
        model_id=None,
        owner="teacher-a",
        course_id="course-1",
        scope_type="knowledge_point",
        scope_id="kp-1",
        artifact_id=None,
        use_rag=False,
        allow_rag=False,
        allow_web=False,
        action_hint=None,
        selected_doc_ids=[],
    )

    result = normalize_chat_request(payload)

    assert result.course_id == "course-1"
    assert result.scope_type == "knowledge_point"
    assert result.scope_id == "kp-1"
