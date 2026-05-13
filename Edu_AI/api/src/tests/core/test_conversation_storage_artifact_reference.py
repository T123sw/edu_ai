from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from core.conversation_storage import ConversationStorage


def test_conversation_detail_preserves_artifact_reference_state():
    root_path = Path(__file__).resolve().parent / ".manual_conversation_storage" / uuid4().hex
    try:
        storage = ConversationStorage(storage_file=root_path / "conversations.json")
        storage.ensure_conversation("conv-1", "第一问", owner="u1")
        storage.update_state(
            "conv-1",
            {
                "active_artifact": {
                    "artifact_id": "report-1",
                    "artifact_type": "report",
                    "title": "李白性格分析.md",
                },
                "active_context": {
                    "active_artifact_id": "report-1",
                    "active_artifact_type": "report",
                    "active_reference_mode": "artifact_edit",
                },
                "artifact_reference": {
                    "artifact_id": "report-1",
                    "artifact_type": "report",
                    "version_id": "v1",
                    "title": "李白性格分析.md",
                },
            },
        )

        detail = storage.get_conversation("conv-1", owner="u1")

        assert detail["state"]["artifact_reference"]["artifact_id"] == "report-1"
        assert detail["state"]["active_context"]["active_reference_mode"] == "artifact_edit"
    finally:
        rmtree(root_path, ignore_errors=True)
