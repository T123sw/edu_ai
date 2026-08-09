from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.api.course_dependencies import get_course_access_service
from app.chat.api import routes_v2 as routes_v2_module
from app.chat.api.routes_v2 import router as v2_router
from core.config import Config


def test_ppt_outline_resolves_course_auto_documents_without_changing_source_intent(
    monkeypatch,
):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "tester",
        "role": "teacher",
    }
    app.dependency_overrides[get_course_access_service] = lambda: SimpleNamespace(
        require=lambda course_id, user, capability: SimpleNamespace(
            course_id=course_id,
            user_id=user["username"],
            course_role="editor",
        )
    )

    class DummyResolver:
        def resolve(self, course_id, source_mode, selected_doc_ids):
            assert (course_id, source_mode, selected_doc_ids) == (
                "course-1",
                "course_auto",
                [],
            )
            return SimpleNamespace(
                documents=[SimpleNamespace(rag_index_key="rag/course-1/doc-1")]
            )

    class DummyPptService:
        def generate_outline(self, payload):
            assert payload.owner == "tester"
            assert payload.source_mode == "course_auto"
            assert payload.selected_doc_ids == []
            assert payload.resolved_doc_ids == ["rag/course-1/doc-1"]
            return {"draft": {"draft_id": "draft-1", "status": "outline_ready"}}

    monkeypatch.setattr(
        routes_v2_module,
        "_get_generation_source_resolver",
        lambda: DummyResolver(),
    )
    monkeypatch.setattr(
        routes_v2_module,
        "_get_direct_ppt_service",
        lambda: DummyPptService(),
    )

    response = TestClient(app).post(
        "/api/chat/v2/ppt/outline",
        json={
            "course_id": "course-1",
            "source_mode": "course_auto",
            "selected_doc_ids": [],
            "ppt_config": {
                "deck_title": "Agent principles",
                "theme_id": "heu_academic_elegant",
                "length_option": "short",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["draft"]["draft_id"] == "draft-1"


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


def test_direct_report_v2_route_returns_task_submitted_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "tester",
        "role": "teacher",
    }
    app.dependency_overrides[get_course_access_service] = lambda: SimpleNamespace(
        require=lambda course_id, user, capability: SimpleNamespace(
            course_id=course_id,
            user_id=user["username"],
            course_role="editor",
        )
    )

    captured = {}
    monkeypatch.setattr(
        "app.chat.api.routes_v2._get_generation_source_resolver",
        lambda: SimpleNamespace(validate=lambda *_args, **_kwargs: ()),
    )

    class DummyCommandService:
        def submit(self, command):
            captured["command"] = command
            return type("Job", (), {"edu_job_id": "job-report-1"})()

    monkeypatch.setattr(
        "app.chat.api.routes_v2.generation_command_service",
        DummyCommandService(),
    )
    monkeypatch.setattr(
        "app.chat.api.routes_v2._get_direct_report_service",
        lambda: (_ for _ in ()).throw(
            AssertionError("HTTP request must not build the generator service")
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/report/direct",
        json={
            "question": "generate report",
            "course_id": "course-1",
            "selected_doc_ids": ["doc-1"],
            "idempotency_key": "report-request-1",
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    assert data["workflow_type"] == "report_direct"
    assert data["task_id"] == "job-report-1"
    assert captured["command"].resource_type == "report"
    assert captured["command"].source_mode == "selected_documents"
    assert captured["command"].config["question"] == "generate report"
    assert captured["command"].idempotency_key == "report-request-1"


def test_game_direct_route_returns_task_submitted_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "tester",
        "role": "student",
    }
    app.dependency_overrides[get_course_access_service] = lambda: SimpleNamespace(
        require=lambda course_id, user, capability: SimpleNamespace(
            course_id=course_id,
            user_id=user["username"],
            course_role="editor",
        )
    )

    captured = {}
    monkeypatch.setattr(
        "app.chat.api.routes_v2._get_generation_source_resolver",
        lambda: SimpleNamespace(validate=lambda *_args, **_kwargs: ()),
    )

    class DummyCommandService:
        def submit(self, command):
            captured["command"] = command
            return type("Job", (), {"edu_job_id": "job-game-1"})()

    monkeypatch.setattr(
        "app.chat.api.routes_v2.generation_command_service",
        DummyCommandService(),
    )
    monkeypatch.setattr(
        "app.chat.api.routes_v2._get_direct_game_service",
        lambda: (_ for _ in ()).throw(
            AssertionError("HTTP request must not build the generator service")
        ),
        raising=False,
    )
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/game/direct",
        json={
            "course_id": "course-1",
            "selected_doc_ids": ["doc-1"],
            "game_type": "drag_match",
            "idempotency_key": "game-request-1",
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    assert data["workflow_type"] == "game_direct"
    assert data["task_id"] == "job-game-1"
    assert captured["command"].resource_type == "game"
    assert captured["command"].source_mode == "selected_documents"
    assert captured["command"].config["game_type"] == "drag_match"


def test_game_html_route_uses_authenticated_path_resolution(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    monkeypatch.setattr(
        "app.chat.api.routes_v2._resolve_chat_game_path",
        lambda owner, relative_path: Path(__file__).resolve(),
        raising=False,
    )
    client = TestClient(app)
    response = client.get("/api/chat/v2/games/html", params={"path": "tester/course-1/game-1/index.html"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


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
