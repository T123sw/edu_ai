from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.chat.api import routes_v2 as routes_v2_module
from app.chat.api.routes_v2 import router as v2_router
from core.config import Config


def test_reply_v2_route_returns_v2_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            assert payload.owner == "tester"
            return {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/reply", json={"question": "hello"})

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "chat.reply"


def test_reply_v2_route_passes_input_images_to_service(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            assert payload.owner == "tester"
            assert payload.input_images[0]["image_id"] == "img-1"
            assert payload.input_images[0]["source"] == "paste"
            return {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/reply",
        json={
            "question": "hello",
            "input_images": [
                {
                    "image_id": "img-1",
                    "file_name": "diagram.png",
                    "mime_type": "image/png",
                    "storage_path": "D:/chat_images/diagram.png",
                    "relative_path": "chat_images/diagram.png",
                    "image_url": "/api/chat/v2/images/chat_images/diagram.png",
                    "source": "paste",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "chat.reply"


def test_reply_v2_route_passes_input_videos_to_service(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            assert payload.owner == "tester"
            assert payload.input_videos[0]["video_id"] == "vid-1"
            assert payload.input_videos[0]["source"] == "upload"
            return {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/reply",
        json={
            "question": "hello",
            "input_videos": [
                {
                    "video_id": "vid-1",
                    "file_name": "clip.mp4",
                    "mime_type": "video/mp4",
                    "storage_path": "D:/chat_videos/clip.mp4",
                    "relative_path": "chat_videos/clip.mp4",
                    "video_url": "/api/chat/v2/videos?path=chat_videos%2Fclip.mp4",
                    "source": "upload",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "chat.reply"


def test_chat_image_upload_route_returns_normalized_metadata(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    upload_root = Path(__file__).with_name("_chat_image_upload_storage")
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Config, "STORAGE_ROOT", upload_root)
    client = TestClient(app)

    try:
        response = client.post(
            "/api/chat/v2/images/upload",
            files=[
                (
                    "files",
                    (
                        "diagram.png",
                        bytes.fromhex(
                            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C6360000002000154A24F5D0000000049454E44AE426082"
                        ),
                        "image/png",
                    ),
                )
            ],
            data={"conversation_id": "conv-image", "source": "paste"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["images"][0]["file_name"] == "diagram.png"
        assert payload["images"][0]["mime_type"] == "image/png"
        assert payload["images"][0]["source"] == "paste"
        assert payload["images"][0]["image_url"].startswith("/api/chat/v2/images?path=")
    finally:
        if upload_root.exists():
            for item in sorted(upload_root.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()


def test_chat_image_preview_route_serves_uploaded_image(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    upload_root = Path(__file__).with_name("_chat_image_preview_storage")
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Config, "STORAGE_ROOT", upload_root)
    client = TestClient(app)

    try:
        upload_response = client.post(
            "/api/chat/v2/images/upload",
            files=[
                (
                    "files",
                    (
                        "diagram.png",
                        bytes.fromhex(
                            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C6360000002000154A24F5D0000000049454E44AE426082"
                        ),
                        "image/png",
                    ),
                )
            ],
            data={"conversation_id": "conv-image", "source": "upload"},
        )
        image_url = upload_response.json()["images"][0]["image_url"]

        preview_response = client.get(image_url)

        assert preview_response.status_code == 200
        assert preview_response.headers["content-type"].startswith("image/png")
    finally:
        if upload_root.exists():
            for item in sorted(upload_root.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()


def test_chat_video_upload_route_returns_normalized_metadata(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    upload_root = Path(__file__).with_name("_chat_video_upload_storage")
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Config, "STORAGE_ROOT", upload_root)
    client = TestClient(app)

    try:
        response = client.post(
            "/api/chat/v2/videos/upload",
            files=[
                (
                    "files",
                    (
                        "clip.mp4",
                        b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom",
                        "video/mp4",
                    ),
                )
            ],
            data={"conversation_id": "conv-video", "source": "upload"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["videos"][0]["file_name"] == "clip.mp4"
        assert payload["videos"][0]["mime_type"] == "video/mp4"
        assert payload["videos"][0]["source"] == "upload"
        assert payload["videos"][0]["video_url"].startswith("/api/chat/v2/videos?path=")
    finally:
        if upload_root.exists():
            for item in sorted(upload_root.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()


def test_chat_video_preview_route_serves_uploaded_video(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    upload_root = Path(__file__).with_name("_chat_video_preview_storage")
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Config, "STORAGE_ROOT", upload_root)
    client = TestClient(app)

    try:
        upload_response = client.post(
            "/api/chat/v2/videos/upload",
            files=[
                (
                    "files",
                    (
                        "clip.mp4",
                        b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom",
                        "video/mp4",
                    ),
                )
            ],
            data={"conversation_id": "conv-video", "source": "upload"},
        )
        video_url = upload_response.json()["videos"][0]["video_url"]

        preview_response = client.get(video_url)

        assert preview_response.status_code == 200
        assert preview_response.headers["content-type"].startswith("video/mp4")
    finally:
        if upload_root.exists():
            for item in sorted(upload_root.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()


def test_report_v2_route_returns_v2_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def report(self, payload):
            assert payload.owner == "tester"
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_report_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/report", json={"question": "generate report"})

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "generate.report"


def test_report_cards_v2_route_returns_cards_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def get_cards(self, payload):
            assert payload.owner == "tester"
            assert payload.selected_doc_ids == ["doc-1"]
            return {
                "entry_mode": "knowledge_base_report",
                "cards": [
                    {
                        "card_id": "preset-brief",
                        "card_type": "preset",
                        "title": "Brief report",
                        "description": "Summarize the key ideas.",
                        "prompt_draft": "Generate a brief report.",
                        "preset_key": "brief",
                    }
                ],
                "trace": {
                    "cache_hit": False,
                    "selected_doc_count": 1,
                },
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_report_entry_cards_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/report/cards",
        json={"course_id": "course-1", "selected_doc_ids": ["doc-1"]},
    )

    assert response.status_code == 200
    assert response.json()["entry_mode"] == "knowledge_base_report"
    assert response.json()["cards"][0]["card_id"] == "preset-brief"


def test_ppt_cards_v2_route_returns_cards_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def get_cards(self, payload):
            assert payload.owner == "tester"
            assert payload.selected_doc_ids == ["doc-1"]
            return {
                "entry_mode": "knowledge_base_ppt",
                "default_selected_card_id": "rec-concept-focus",
                "cards": [
                    {
                        "card_id": "preset-knowledge-lecture",
                        "card_type": "preset",
                        "title": "Knowledge lecture",
                        "description": "Lecture-oriented PPT entry.",
                        "objective_hint": "课堂讲解",
                        "length_option": "medium",
                        "preset_key": "knowledge_lecture",
                        "prefill_config": {
                            "deck_title": "System skills",
                            "audience": "本科生",
                            "objective": "课堂讲解",
                            "theme_id": "heu_academic_elegant",
                            "length_option": "medium",
                            "target_slide_count": 16,
                            "key_points": ["定义"],
                        },
                    }
                ],
                "trace": {
                    "selected_doc_count": 1,
                },
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_ppt_entry_cards_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/ppt/cards",
        json={"course_id": "course-1", "selected_doc_ids": ["doc-1"]},
    )

    assert response.status_code == 200
    assert response.json()["entry_mode"] == "knowledge_base_ppt"
    assert response.json()["default_selected_card_id"] == "rec-concept-focus"
    assert response.json()["cards"][0]["prefill_config"]["theme_id"] == "heu_academic_elegant"


def test_lesson_plan_cards_v2_route_returns_cards_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def get_cards(self, payload):
            assert payload.owner == "tester"
            assert payload.selected_doc_ids == ["doc-1"]
            return {
                "entry_mode": "knowledge_base_lesson_plan",
                "default_selected_card_id": "preset-new-lesson",
                "cards": [
                    {
                        "card_id": "preset-new-lesson",
                        "card_type": "preset",
                        "title": "新授课教案",
                        "description": "面向单课时新授场景。",
                        "prompt_draft": "请基于已选文档生成一份新授课教案。",
                        "preset_key": "new_lesson",
                        "prefill_config": {
                            "topic": "关羽的战绩与历史评价",
                            "audience": "初中历史",
                            "duration": "45分钟",
                            "lesson_type": "新授课",
                            "objective": "梳理战绩并进行历史评价",
                        },
                    }
                ],
                "trace": {
                    "selected_doc_count": 1,
                },
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_lesson_plan_entry_cards_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/lesson-plan/cards",
        json={"course_id": "course-1", "selected_doc_ids": ["doc-1"]},
    )

    assert response.status_code == 200
    assert response.json()["entry_mode"] == "knowledge_base_lesson_plan"
    assert response.json()["default_selected_card_id"] == "preset-new-lesson"
    assert response.json()["cards"][0]["prefill_config"]["lesson_type"] == "新授课"


def test_direct_report_v2_route_returns_direct_artifact_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def generate(self, payload):
            assert payload.owner == "tester"
            assert payload.selected_doc_ids == ["doc-1"]
            return {
                "action": {"name": "generate.report.direct"},
                "artifacts": [
                    {
                        "artifact_id": "report-1",
                        "artifact_type": "report",
                        "title": "report.md",
                        "content": "# report",
                    }
                ],
                "trace": {"path": "direct", "selected_doc_count": 1},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_direct_report_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/report/direct",
        json={
            "question": "generate report",
            "course_id": "course-1",
            "selected_doc_ids": ["doc-1"],
        },
    )

    assert response.status_code == 200
    assert response.json()["action"]["name"] == "generate.report.direct"
    assert response.json()["artifacts"][0]["artifact_type"] == "report"


def test_direct_ppt_outline_v2_route_returns_draft_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def generate_outline(self, payload):
            assert payload.owner == "tester"
            assert payload.selected_doc_ids == ["doc-1"]
            assert payload.ppt_config["deck_title"] == "Agent Basics"
            return {
                "action": {"name": "generate.ppt.outline.direct"},
                "draft": {"draft_id": "ppt-draft-1", "status": "outline_ready"},
                "artifacts": [],
                "trace": {"path": "direct", "draft_id": "ppt-draft-1"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_direct_ppt_outline_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/ppt/outline",
        json={
            "course_id": "course-1",
            "selected_doc_ids": ["doc-1"],
            "ppt_config": {
                "deck_title": "Agent Basics",
                "audience": "Undergraduate students",
                "objective": "Classroom presentation",
                "theme_id": "heu_academic_elegant",
                "target_slide_count": 16,
                "key_points": ["Definition"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["draft"]["draft_id"] == "ppt-draft-1"


def test_direct_ppt_generate_v2_route_returns_run_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def generate(self, payload):
            assert payload.owner == "tester"
            assert payload.draft_id == "ppt-draft-1"
            assert payload.confirm is True
            return {
                "action": {"name": "generate.ppt.direct"},
                "run": {"run_id": "ppt-run-1", "status": "running"},
                "artifacts": [],
                "trace": {"path": "direct", "draft_id": "ppt-draft-1", "run_id": "ppt-run-1"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_direct_ppt_generation_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/ppt/generate",
        json={
            "draft_id": "ppt-draft-1",
            "confirm": True,
            "outline": {"deck_title": "Agent Basics", "slides": []},
        },
    )

    assert response.status_code == 200
    assert response.json()["run"]["run_id"] == "ppt-run-1"


def test_reply_v2_route_returns_structured_error_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            raise ValueError("broken")

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/reply", json={"question": "hello"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "workflow_failed"
    assert response.json()["error"]["message"] == "broken"


def test_reply_v2_report_intent_error_uses_workflow_trace(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply(self, payload):
            raise ValueError("report broken")

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/reply", json={"question": "generate report", "action_hint": "generate.report"})

    assert response.status_code == 500
    assert response.json()["trace"]["path"] == "workflow"
