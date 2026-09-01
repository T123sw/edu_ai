from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def test_runtime_resumes_body_generation_after_outline_confirmation():
    called = {"engine": False, "state": None}

    class DummyEngine:
        def invoke(self, state):
            called["engine"] = True
            called["state"] = state
            return {"reply": "report body", "status": "completed", "phase": "generating"}

    runtime = ReportWorkflowRuntime(engine=DummyEngine())

    snapshot = ConversationSnapshot(
        conversation_id="conv-outline",
        workflow_state={
            "workflow_id": "conv-outline",
            "workflow_type": "report",
            "status": "awaiting_confirm",
            "stage": "outlining",
            "required_slots": [],
            "filled_slots": {
                "core_topic": "Water Campaign",
                "focus_area": "From tactical win to strategic reversal",
                "__preparation_source": "llm_structured_output",
                "__preparation_model": "qwen3.5-plus",
            },
            "artifacts": [
                {
                    "artifact_id": "conv-outline:outline",
                    "artifact_type": "report_outline",
                    "content": [
                        {"chapter_id": 1, "chapter_title": "Background", "sections": []},
                    ],
                }
            ],
        },
    )

    result = runtime.run(
        request=ChatRequestV2(question="ok", conversation_id="conv-outline"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["engine"] is True
    assert called["state"]["soft_confirmed"] is True
    assert called["state"]["generation_ready"] is True
    assert called["state"]["report_outline"] == [
        {"chapter_id": 1, "chapter_title": "Background", "sections": []}
    ]
    assert called["state"]["human_feedback"] == "确认"
    assert called["state"]["report_slots"]["core_topic"] == "Water Campaign"
    assert result["message"]["content"] == "report body"
