from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import classroom_catalog as api
from app.services.course_access import CoursePrincipal


class _CatalogService:
    def build(self, *, course_id: str, mode: str, student_id: str | None):
        resource = {
            "standard_kind": "study_guide",
            "material_type": "report",
            "material_id": "guide-1",
            "review_status": "pending" if mode == "manage" else "approved",
            "current_version": 2 if mode == "manage" else 1,
            "approved_version": 1,
            "resource": {
                "title": "待审核标题" if mode == "manage" else "已发布标题",
                **({"rejection_reason": "教师备注"} if mode == "manage" else {}),
            },
            "progress": None,
        }
        return {
            "course_id": course_id,
            "mode": mode,
            "leaves": [{
                "leaf_id": "leaf-1",
                "title": "1.1 线性表",
                "chapter_id": "chapter-1",
                "chapter_title": "第一章",
                "path_titles": ["数据结构", "第一章", "1.1 线性表"],
                "resources": [resource],
                **(
                    {"summary": {"pending": 1, "published": 1}}
                    if mode == "manage"
                    else {"learning_summary": {"completed": 0, "total": 1}}
                ),
            }],
        }


def _client(role: str | None) -> TestClient:
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_classroom_catalog_service] = lambda: _CatalogService()
    if role is None:
        def deny():
            raise HTTPException(status_code=403, detail={"code": "COURSE_ACCESS_DENIED"})
        app.dependency_overrides[api.require_course_read] = deny
    else:
        app.dependency_overrides[api.require_course_read] = lambda: CoursePrincipal(
            course_id="course-1",
            user_id="teacher-1" if role == "editor" else "student-1",
            system_role="teacher" if role == "editor" else "student",
            course_role=role,
        )
    return TestClient(app)


def test_editor_receives_manage_projection() -> None:
    response = _client("editor").get("/api/courses/course-1/classroom-catalog")
    assert response.status_code == 200
    assert response.json()["mode"] == "manage"
    assert response.json()["leaves"][0]["resources"][0]["resource"]["title"] == "待审核标题"


def test_viewer_receives_only_learn_projection_without_review_details() -> None:
    response = _client("viewer").get("/api/courses/course-1/classroom-catalog")
    payload = response.json()
    assert response.status_code == 200
    assert payload["mode"] == "learn"
    assert "待审核标题" not in response.text
    assert "rejection_reason" not in response.text


def test_unaffiliated_user_is_denied() -> None:
    response = _client(None).get("/api/courses/course-1/classroom-catalog")
    assert response.status_code == 403
