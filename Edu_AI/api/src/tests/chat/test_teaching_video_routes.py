from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import courses as courses_module
from app.api import courses as courses_api
from app.services import course_service


class DummyManager:
    def get_course_info(self, course_id: str):
        if course_id == "course-1":
            return {"id": "course-1", "title": "计算机网络"}
        return None

    def create_course_structure(self, course_id: str):
        return True

    def save_course_info(self, course_id: str, info: dict):
        return True


class DummyTeachingVideoService:
    def __init__(self):
        self.create_calls = []
        self.status_calls = []

    def list_available_ppts(self, course_id: str):
        return [
            {
                "material_id": "ppt-ready",
                "title": "TCP 三次握手.pptx",
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job-1/rev_0000/deck.pptx",
                "html_full_url": "http://127.0.0.1:46080/ppt/artifacts/job-1/rev_0000/deck.html",
                "slide_count": 8,
            }
        ]

    def create_task(self, *, course_id: str, ppt_material_id: str, owner: str):
        self.create_calls.append(
            {
                "course_id": course_id,
                "ppt_material_id": ppt_material_id,
                "owner": owner,
            }
        )
        return {
            "task_id": "course_task_001",
            "material_id": "teaching_video__course_task_001",
            "status": "processing",
            "video_url": None,
        }

    def get_task_status(self, *, course_id: str, task_id: str):
        self.status_calls.append({"course_id": course_id, "task_id": task_id})
        return {
            "task_id": task_id,
            "material_id": "teaching_video__course_task_001",
            "status": "success",
            "video_url": "http://127.0.0.1:8008/api/v1/offline/download/course_task_001.mp4",
        }


class RuntimeFailingTeachingVideoService(DummyTeachingVideoService):
    def create_task(self, *, course_id: str, ppt_material_id: str, owner: str):
        raise RuntimeError("PowerPoint slide image export failed: COM error")


def test_teaching_video_routes_expose_ppt_listing_task_creation_and_polling(monkeypatch):
    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}

    service = DummyTeachingVideoService()
    monkeypatch.setattr(course_service, "_get_manager", lambda: DummyManager())
    monkeypatch.setattr(courses_api, "get_teaching_video_bridge_service", lambda: service)

    client = TestClient(app)

    listing = client.get("/api/courses/course-1/teaching-videos/ppts")
    created = client.post(
        "/api/courses/course-1/teaching-videos",
        json={"ppt_material_id": "ppt-ready"},
    )
    status = client.get("/api/courses/course-1/teaching-videos/tasks/course_task_001")

    assert listing.status_code == 200
    assert listing.json()[0]["material_id"] == "ppt-ready"

    assert created.status_code == 200
    assert created.json()["task_id"] == "course_task_001"
    assert service.create_calls == [
        {
            "course_id": "course-1",
            "ppt_material_id": "ppt-ready",
            "owner": "teacher-a",
        }
    ]

    assert status.status_code == 200
    assert status.json()["status"] == "success"
    assert service.status_calls == [{"course_id": "course-1", "task_id": "course_task_001"}]


def test_teaching_video_create_returns_readable_gateway_error(monkeypatch):
    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}

    monkeypatch.setattr(course_service, "_get_manager", lambda: DummyManager())
    monkeypatch.setattr(courses_api, "get_teaching_video_bridge_service", lambda: RuntimeFailingTeachingVideoService())

    client = TestClient(app)

    response = client.post(
        "/api/courses/course-1/teaching-videos",
        json={"ppt_material_id": "ppt-ready"},
    )

    assert response.status_code == 502
    assert "PowerPoint slide image export failed" in response.json()["detail"]
