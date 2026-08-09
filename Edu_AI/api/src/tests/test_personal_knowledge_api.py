from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import personal_knowledge
from app.auth import get_current_user
from app.services import knowledge_document_service as knowledge_lifecycle
from app.services.personal_knowledge_service import PersonalKnowledgeService
from app.services.course_access import CoursePrincipal


@pytest.fixture()
def personal_api(tmp_path: Path, monkeypatch):
    service = PersonalKnowledgeService(root_path=tmp_path / "personal")
    active_user = {"username": "student-a", "role": "student"}
    app = FastAPI()
    app.include_router(personal_knowledge.router)
    app.dependency_overrides[get_current_user] = lambda: active_user
    app.dependency_overrides[personal_knowledge.get_personal_knowledge_service] = (
        lambda: service
    )
    app.dependency_overrides[personal_knowledge.get_course_access_service] = (
        lambda: type(
            "Access",
            (),
            {
                "require": staticmethod(
                    lambda course_id, user, _capability: CoursePrincipal(
                        course_id=course_id,
                        user_id=user["username"],
                        system_role=user["role"],
                        course_role="viewer",
                    )
                )
            },
        )()
    )
    monkeypatch.setattr(personal_knowledge, "get_rag_system", lambda: object())
    monkeypatch.setattr(
        service,
        "submit_index",
        lambda **_kwargs: {"edu_job_id": "personal-index-job", "status": "queued"},
    )
    with TestClient(app) as client:
        yield client, active_user, service


def test_student_can_manage_personal_documents_without_course_edit(personal_api):
    client, _, _ = personal_api

    uploaded = client.post(
        "/api/personal-knowledge/documents",
        files={"file": ("notes.txt", "个人笔记", "text/plain")},
        data={"course_context_id": "course-1"},
    )
    assert uploaded.status_code == 202
    document_id = uploaded.json()["document"]["id"]
    assert uploaded.json()["job"]["edu_job_id"] == "personal-index-job"

    listed = client.get("/api/personal-knowledge/documents")
    content = client.get(
        f"/api/personal-knowledge/documents/{document_id}/content"
    )
    renamed = client.patch(
        f"/api/personal-knowledge/documents/{document_id}",
        json={"name": "复习笔记.txt"},
    )
    deleted = client.delete(
        f"/api/personal-knowledge/documents/{document_id}"
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [document_id]
    assert content.status_code == 200
    assert content.json()["content"] == "个人笔记"
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "复习笔记.txt"
    assert deleted.status_code == 200
    assert client.get("/api/personal-knowledge/documents").json() == []


def test_personal_document_ids_do_not_cross_user_boundaries(personal_api):
    client, active_user, service = personal_api
    created = service.create_document(
        owner_user_id="student-a",
        filename="private.txt",
        file_data=b"private",
    )
    active_user["username"] = "student-b"

    detail = client.get(
        f"/api/personal-knowledge/documents/{created['id']}"
    )
    content = client.get(
        f"/api/personal-knowledge/documents/{created['id']}/content"
    )
    delete = client.delete(
        f"/api/personal-knowledge/documents/{created['id']}"
    )

    assert detail.status_code == 404
    assert content.status_code == 404
    assert delete.status_code == 404


def test_only_failed_personal_documents_can_retry(personal_api):
    client, _, service = personal_api
    created = service.create_document(
        owner_user_id="student-a",
        filename="retry.txt",
        file_data=b"retry",
    )
    manager = service.manager_for("student-a")
    knowledge_lifecycle.patch_document(
        manager,
        service.access_domain("student-a"),
        created["id"],
        status="failed",
    )

    response = client.post(
        f"/api/personal-knowledge/documents/{created['id']}/retry"
    )

    assert response.status_code == 202
    assert response.json()["edu_job_id"] == "personal-index-job"
