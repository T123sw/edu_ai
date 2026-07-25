from types import SimpleNamespace

from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


def test_retired_ppt_runtime_hands_off_to_classroom_studio():
    result = PptWorkflowRuntime().run(
        request=SimpleNamespace(conversation_id="conv-1", course_id="course-1"),
        snapshot=None,
        decision=None,
    )

    assert result["workflow"] == {
        "type": "ppt",
        "status": "completed",
        "phase": "classroom_handoff",
        "progress": 100,
    }
    assert result["artifacts"] == []
    assert result["trace"]["classroom_url"] == "#classroom-studio?course_id=course-1"

