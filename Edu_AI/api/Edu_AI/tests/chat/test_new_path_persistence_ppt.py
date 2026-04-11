from pathlib import Path
from types import SimpleNamespace
import uuid

from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


def test_write_v2_result_persists_ppt_intermediate_artifacts_and_prefers_deck_as_active_artifact():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    request = SimpleNamespace(
        question="确认并生成",
        owner="teacher-a",
        course_id="course-1",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
    )
    result = {
        "message": {"role": "assistant", "content": "PPT 已生成完成，请在右侧查看和下载。"},
        "action": {"name": "generate.ppt"},
        "workflow": {
            "type": "ppt",
            "status": "completed",
            "phase": "completed",
            "required_slots": [],
            "filled_slots": {
                "deck_topic": "TCP 三次握手",
                "audience": "大一学生",
                "objective": "课堂讲解",
                "key_points": "三次握手流程 | 常见误区",
                "theme_id": "heu_academic_elegant",
                "slide_count": "6",
                "__ppt_followup_rounds": "1",
            },
        },
        "artifacts": [
            {
                "artifact_id": "conv-ppt:outline",
                "artifact_type": "ppt_outline",
                "title": "TCP 三次握手-大纲",
                "content": {"deck_title": "TCP 三次握手", "slides": []},
            },
            {
                "artifact_id": "conv-ppt:content_markdown",
                "artifact_type": "ppt_content_markdown",
                "title": "TCP 三次握手-content.md",
                "content": "# Deck\n",
            },
            {
                "artifact_id": "conv-ppt:deck:job_001",
                "artifact_type": "ppt_deck",
                "title": "TCP 三次握手.pptx",
                "content": {
                    "job_id": "job_001",
                    "revision_id": "rev_0000",
                    "pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx",
                },
            },
        ],
        "sources": [],
        "trace": {
            "ppt_preparation_result": {
                "topic": "TCP 三次握手",
                "audience": "大一学生",
                "objective": "课堂讲解",
                "key_points": ["三次握手流程", "常见误区"],
                "theme": "heu_academic_elegant",
                "page_count": 6,
                "source_basis": ["conversation_summary"],
            }
        },
    }

    adapter.write_v2_result("conv-ppt-persist", request, result)

    state = storage.get_state("conv-ppt-persist")

    assert state["workflow_state"]["workflow_type"] == "ppt"
    assert state["workflow_state"]["status"] == "completed"
    assert state["workflow_state"]["stage"] == "completed"
    assert state["workflow_state"]["required_slots"] == []
    assert state["workflow_state"]["filled_slots"]["deck_topic"] == "TCP 三次握手"
    assert state["workflow_state"]["filled_slots"]["audience"] == "大一学生"
    assert state["workflow_state"]["filled_slots"]["objective"] == "课堂讲解"
    assert state["workflow_state"]["filled_slots"]["key_points"] == "三次握手流程 | 常见误区"
    assert state["workflow_state"]["filled_slots"]["theme_id"] == "heu_academic_elegant"
    assert state["workflow_state"]["filled_slots"]["slide_count"] == "6"
    assert state["workflow_state"]["filled_slots"]["__ppt_followup_rounds"] == "1"
    assert [artifact["artifact_type"] for artifact in state["workflow_state"]["artifacts"]] == [
        "ppt_outline",
        "ppt_content_markdown",
        "ppt_deck",
    ]
    assert state["active_context"]["active_workflow_type"] == "ppt"
    assert state["active_context"]["active_artifact_type"] == "ppt_deck"
    assert state["active_artifact"]["artifact_type"] == "ppt_deck"
    assert state["referenced_artifact_ids"] == [
        "conv-ppt:outline",
        "conv-ppt:content_markdown",
        "conv-ppt:deck:job_001",
    ]
