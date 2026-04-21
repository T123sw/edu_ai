from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import courses as courses_module


class DummyManager:
    def get_course_info(self, course_id: str):
        return {"id": course_id, "title": "计算思维"} if course_id == "course-1" else None


class DummyAiLectureSessionService:
    def __init__(self):
        self.create_calls = []
        self.patch_calls = []
        self.start_calls = []
        self.stop_calls = []

    def create_session(self, *, course_id: str, source_ppt_material_id: str, title: str | None, owner: str):
        self.create_calls.append(
            {
                "course_id": course_id,
                "source_ppt_material_id": source_ppt_material_id,
                "title": title,
                "owner": owner,
            }
        )
        return {
            "material_id": "ai_session_001",
            "material_type": "ai_lecture_session",
            "title": title,
            "content": {"session_snapshot_id": "ai_session_001", "can_continue_interactive": True},
            "generation_state": {"status": "created"},
        }

    def get_session(self, course_id: str, session_id: str):
        return {
            "material": {"material_id": session_id, "material_type": "ai_lecture_session"},
            "snapshot": {"snapshot_id": session_id, "events": [], "slide_image_urls": [f"/slides/{session_id}/slide-001.png"]},
            "metadata": {"recording_status": "not_started"},
        }

    def patch_snapshot(self, *, course_id: str, session_id: str, payload: dict):
        self.patch_calls.append({"course_id": course_id, "session_id": session_id, "payload": payload})
        return {"snapshot_id": session_id, "events": payload["events"], "last_position": payload["last_position"]}

    def start_recording(self, course_id: str, session_id: str, *, livetalking_session_id: int):
        self.start_calls.append({"course_id": course_id, "session_id": session_id, "livetalking_session_id": livetalking_session_id})
        return {"recording_status": "recording"}

    def stop_recording(self, course_id: str, session_id: str, *, livetalking_session_id: int):
        self.stop_calls.append({"course_id": course_id, "session_id": session_id, "livetalking_session_id": livetalking_session_id})
        return {"recording_status": "completed", "recording_url": "/recording.mp4"}

    def slide_image_response(self, course_id: str, session_id: str, slide_name: str):
        self.slide_image_calls = getattr(self, "slide_image_calls", [])
        self.slide_image_calls.append({"course_id": course_id, "session_id": session_id, "slide_name": slide_name})
        from fastapi.responses import Response

        return Response(content=b"png", media_type="image/png")


def _client(service: DummyAiLectureSessionService) -> TestClient:
    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}
    courses_module.get_ai_lecture_session_service = lambda: service
    courses_module._get_manager = lambda: DummyManager()
    return TestClient(app)


def test_ai_lecture_session_routes_create_get_patch_and_record():
    service = DummyAiLectureSessionService()
    client = _client(service)

    created = client.post(
        "/api/courses/course-1/lecture-sessions",
        json={"source_ppt_material_id": "ppt-ready", "title": "AI 实时讲解"},
    )
    fetched = client.get("/api/courses/course-1/lecture-sessions/ai_session_001")
    patched = client.patch(
        "/api/courses/course-1/lecture-sessions/ai_session_001/snapshot",
        json={
            "events": [{"type": "speak", "text": "第一句"}],
            "last_position": {"page_index": 0, "sentence_index": 0},
        },
    )
    started = client.post(
        "/api/courses/course-1/lecture-sessions/ai_session_001/recording/start",
        json={"livetalking_session_id": 123456},
    )
    stopped = client.post(
        "/api/courses/course-1/lecture-sessions/ai_session_001/recording/stop",
        json={"livetalking_session_id": 123456},
    )
    slide = client.get("/api/courses/course-1/lecture-sessions/ai_session_001/slides/slide-001.png")

    assert created.status_code == 200
    assert created.json()["material_type"] == "ai_lecture_session"
    assert service.create_calls[0]["owner"] == "teacher-a"
    assert fetched.status_code == 200
    assert fetched.json()["snapshot"]["snapshot_id"] == "ai_session_001"
    assert patched.status_code == 200
    assert patched.json()["events"][0]["type"] == "speak"
    assert started.json()["recording_status"] == "recording"
    assert stopped.json()["recording_status"] == "completed"
    assert slide.status_code == 200
