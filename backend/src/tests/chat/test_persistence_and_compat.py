from pathlib import Path
import uuid

from app.chat.legacy.compat_service import CompatChatService
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from core.conversation_storage import ConversationStorage


def test_conversation_store_adapter_reads_and_writes():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-1", "你好")
    adapter = ConversationStoreAdapter(storage=storage)

    adapter.append_message("conv-1", "user", "你好")
    adapter.update_workflow_state("conv-1", {"workflow_type": "report"})
    snapshot = adapter.load_snapshot("conv-1")

    assert len(snapshot["messages"]) == 1
    assert snapshot["state"]["workflow_state"]["workflow_type"] == "report"


def test_conversation_store_adapter_clears_active_task_when_workflow_interrupted():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-2", "hello")
    storage.update_state("conv-2", {"active_task": "generate.report"})
    adapter = ConversationStoreAdapter(storage=storage)

    class Request:
        question = "算了"

    adapter.write_v2_result(
        "conv-2",
        Request(),
        {
            "message": {"role": "assistant", "content": "已中断"},
            "conversation": {"conversation_id": "conv-2"},
            "action": {"name": "chat.reply"},
            "workflow": {"type": "report", "status": "interrupted"},
            "artifacts": [],
            "sources": [],
            "trace": {"path": "workflow"},
        },
    )

    state = storage.get_state("conv-2")

    assert state["workflow_state"]["status"] == "interrupted"
    assert state["active_task"] in {"", None}


def test_conversation_store_adapter_persists_capability_policy():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-cap-policy", "hello")
    adapter = ConversationStoreAdapter(storage=storage)

    class Capability:
        allow_rag = True
        allow_web = True
        selected_doc_ids = ["doc-1", "doc-2"]

    class Request:
        question = "hello"
        capability = Capability()

    adapter.write_v2_result(
        "conv-cap-policy",
        Request(),
        {
            "message": {"role": "assistant", "content": "ok"},
            "conversation": {"conversation_id": "conv-cap-policy"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        },
    )

    state = storage.get_state("conv-cap-policy")

    assert state["capability_policy"]["allow_rag"] is True
    assert state["capability_policy"]["allow_web"] is True
    assert state["capability_policy"]["selected_doc_ids"] == ["doc-1", "doc-2"]


def test_conversation_store_adapter_persists_user_input_images_in_history_and_state():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-image-history", "hello")
    adapter = ConversationStoreAdapter(storage=storage)

    class Request:
        question = "继续围绕这张图片讨论"
        input_images = [
            {
                "image_id": "img-1",
                "file_name": "hero.png",
                "mime_type": "image/png",
                "storage_path": "D:/tmp/hero.png",
                "relative_path": "teacher/conv-image-history/hero.png",
                "image_url": "/api/chat/v2/images?path=teacher%2Fconv-image-history%2Fhero.png",
                "source": "paste",
            }
        ]

    adapter.write_v2_result(
        "conv-image-history",
        Request(),
        {
            "message": {"role": "assistant", "content": "ok"},
            "conversation": {"conversation_id": "conv-image-history"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        },
    )

    detail = storage.get_conversation("conv-image-history")
    state = storage.get_state("conv-image-history")

    assert detail["history"][0]["role"] == "user"
    assert detail["history"][0]["input_images"][0]["image_id"] == "img-1"
    assert detail["history"][0]["input_images"][0]["image_url"].startswith("/api/chat/v2/images")
    assert state["last_input_images"][0]["image_id"] == "img-1"
    assert state["last_input_image_count"] == 1


def test_conversation_store_adapter_persists_user_input_videos_in_history_and_state():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-video-history", "hello")
    adapter = ConversationStoreAdapter(storage=storage)

    class Request:
        question = "继续围绕这个视频讨论"
        input_videos = [
            {
                "video_id": "vid-1",
                "file_name": "clip.mp4",
                "mime_type": "video/mp4",
                "storage_path": "D:/tmp/clip.mp4",
                "relative_path": "teacher/conv-video-history/clip.mp4",
                "video_url": "/api/chat/v2/videos?path=teacher%2Fconv-video-history%2Fclip.mp4",
                "source": "upload",
            }
        ]

    adapter.write_v2_result(
        "conv-video-history",
        Request(),
        {
            "message": {"role": "assistant", "content": "ok"},
            "conversation": {"conversation_id": "conv-video-history"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        },
    )

    detail = storage.get_conversation("conv-video-history")
    state = storage.get_state("conv-video-history")

    assert detail["history"][0]["role"] == "user"
    assert detail["history"][0]["input_videos"][0]["video_id"] == "vid-1"
    assert detail["history"][0]["input_videos"][0]["video_url"].startswith("/api/chat/v2/videos")
    assert state["last_input_videos"][0]["video_id"] == "vid-1"
    assert state["last_input_video_count"] == 1


def test_conversation_store_adapter_persists_summary_and_memory_for_normal_reply():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-memory", "hello")
    adapter = ConversationStoreAdapter(storage=storage)

    class Capability:
        allow_rag = False
        allow_web = False
        selected_doc_ids = []

    class Request:
        question = "请分析关羽水淹七军为什么能赢"
        capability = Capability()
        course_id = None
        owner = "teacher-a"

    adapter.write_v2_result(
        "conv-memory",
        Request(),
        {
            "message": {
                "role": "assistant",
                "content": "关羽取胜的关键在于战略窗口、水军优势，以及对禁援军被洪水打散后的快速歼灭。"
            },
            "conversation": {"conversation_id": "conv-memory"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        },
    )

    state = storage.get_state("conv-memory")

    assert "关羽水淹七军为什么能赢" in state["conversation_summary"]["summary_text"]
    assert state["conversation_memory"]["current_topics"]
    assert state["conversation_memory"]["user_goals"][0] == "分析问题"


def test_conversation_storage_filters_conversations_by_owner():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-a", "hello a", owner="teacher-a")
    storage.append_message("conv-a", "user", "hello a")
    storage.ensure_conversation("conv-b", "hello b", owner="teacher-b")
    storage.append_message("conv-b", "user", "hello b")

    listing = storage.list_conversations(owner="teacher-a")

    assert [item["conversation_id"] for item in listing["conversations"]] == ["conv-a"]


def test_conversation_storage_requires_matching_owner_for_detail_lookup():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-a", "hello a", owner="teacher-a")
    storage.append_message("conv-a", "user", "hello a")

    try:
        storage.get_conversation("conv-a", owner="teacher-b")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for mismatched owner")


def test_compat_service_delegates_to_new_service():
    service = CompatChatService(
        delegate=lambda payload: {
            "message": {"role": "assistant", "content": "ok"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "chat.reply"},
            "artifacts": [],
            "workflow": None,
            "sources": [],
            "trace": {"path": "fast"},
        }
    )

    data = service.chat(
        question="你好",
        conversation_id=None,
        model_id=None,
        use_rag=False,
        selected_doc_ids=None,
        owner="tester",
        course_id=None,
    )

    assert data["intent_category"] == "chat"
    assert data["answer"] == "ok"
    assert data["conversation_id"] == "conv-1"


def test_compat_service_defaults_missing_legacy_intent_category_to_chat():
    service = CompatChatService(
        delegate=lambda payload: {
            "answer": "legacy-only-answer",
            "conversation_id": "conv-2",
            "model_id": "",
            "meta": {},
        }
    )

    data = service.chat(
        question="hello",
        conversation_id="conv-2",
        model_id=None,
        use_rag=False,
        selected_doc_ids=None,
        owner="tester",
        course_id=None,
    )

    assert data["answer"] == "legacy-only-answer"
    assert data["intent_category"] == "chat"
