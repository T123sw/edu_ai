from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.course_dependencies import get_course_access_service
from app.auth import get_current_user
from app.chat.api import routes_v2
from app.services.course_access import CourseAccessDenied, CoursePrincipal
from app.services.generation_source_resolver import (
    GenerationSourceResolver,
    SourceDocumentRecord,
)


@dataclass
class FakeCatalog:
    records: list[SourceDocumentRecord]

    def list_for_course(self, course_id: str):
        return [item for item in self.records if item.course_id == course_id]

    def get_by_public_id(self, document_id: str):
        return next(
            (item for item in self.records if item.document_id == document_id),
            None,
        )


class ContentMustNotBeRead:
    def read_many(self, rag_index_keys):
        raise AssertionError("preflight must not read document content")


class FakeCourseAccessService:
    def require(self, course_id, user, capability):
        role = str(user.get("course_role") or "viewer")
        if capability == "generate" and role == "viewer":
            raise CourseAccessDenied(
                course_id=course_id,
                user_id=str(user.get("username") or ""),
                capability=capability,
            )
        return CoursePrincipal(
            course_id=course_id,
            user_id=str(user.get("username") or ""),
            system_role=str(user.get("role") or "teacher"),
            course_role=role,
        )


@pytest.fixture()
def preflight_client(monkeypatch):
    records = [
        SourceDocumentRecord(
            course_id="c1",
            document_id="doc-1",
            name="Mechanics.pdf",
            status="ready",
            rag_index_key="rag-mechanics",
            chunk_count=12,
        ),
        SourceDocumentRecord(
            course_id="c1",
            document_id="doc-pending",
            name="Pending.pdf",
            status="indexing",
            rag_index_key="",
            chunk_count=0,
        ),
        SourceDocumentRecord(
            course_id="c2",
            document_id="doc-other-course",
            name="Other.pdf",
            status="ready",
            rag_index_key="rag-other",
            chunk_count=3,
        ),
    ]
    resolver = GenerationSourceResolver(
        FakeCatalog(records),
        ContentMustNotBeRead(),
    )
    monkeypatch.setattr(
        routes_v2,
        "_get_generation_source_resolver",
        lambda: resolver,
        raising=False,
    )
    monkeypatch.setattr(
        routes_v2.generation_command_service,
        "submit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("preflight must not create a durable job")
        ),
    )

    active_user = {
        "username": "teacher-a",
        "role": "teacher",
        "course_role": "editor",
    }
    app = FastAPI()
    app.include_router(routes_v2.router)
    app.dependency_overrides[get_current_user] = lambda: active_user
    app.dependency_overrides[get_course_access_service] = (
        lambda: FakeCourseAccessService()
    )
    with TestClient(app) as client:
        yield client, active_user


def test_preflight_returns_ready_document_summary(preflight_client):
    client, _ = preflight_client

    response = client.post(
        "/api/chat/v2/generation/preflight",
        json={
            "course_id": "c1",
            "resource_type": "quiz",
            "source_mode": "selected_documents",
            "selected_doc_ids": ["doc-1"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "source_mode": "selected_documents",
        "ready_document_count": 1,
        "documents": [
            {
                "document_id": "doc-1",
                "name": "Mechanics.pdf",
                "chunk_count": 12,
            }
        ],
        "warnings": [],
    }


def test_course_auto_without_ready_documents_returns_warning(preflight_client):
    client, _ = preflight_client

    response = client.post(
        "/api/chat/v2/generation/preflight",
        json={
            "course_id": "empty-course",
            "resource_type": "report",
            "source_mode": "course_auto",
            "selected_doc_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["ready_document_count"] == 0
    assert response.json()["warnings"] == ["NO_READY_COURSE_DOCUMENTS"]


@pytest.mark.parametrize(
    ("document_id", "expected_code"),
    [
        ("missing", "SOURCE_DOCUMENT_NOT_FOUND"),
        ("doc-other-course", "SOURCE_DOCUMENT_WRONG_COURSE"),
        ("doc-pending", "SOURCE_DOCUMENT_NOT_READY"),
    ],
)
def test_preflight_returns_stable_source_errors(
    preflight_client,
    document_id,
    expected_code,
):
    client, _ = preflight_client

    response = client.post(
        "/api/chat/v2/generation/preflight",
        json={
            "course_id": "c1",
            "resource_type": "quiz",
            "source_mode": "selected_documents",
            "selected_doc_ids": [document_id],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == expected_code


def test_student_viewer_can_run_generation_preflight_for_personal_output(
    preflight_client,
):
    client, active_user = preflight_client
    active_user["role"] = "student"
    active_user["course_role"] = "viewer"

    response = client.post(
        "/api/chat/v2/generation/preflight",
        json={
            "course_id": "c1",
            "resource_type": "quiz",
            "source_mode": "none",
            "selected_doc_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_student_viewer_can_submit_allowed_personal_generation(
    preflight_client,
    monkeypatch,
):
    client, active_user = preflight_client
    active_user["role"] = "student"
    active_user["course_role"] = "viewer"
    captured = {}

    def submit(command):
        captured["command"] = command
        return type("Job", (), {"edu_job_id": "student-report-job"})()

    monkeypatch.setattr(routes_v2.generation_command_service, "submit", submit)

    response = client.post(
        "/api/chat/v2/report/direct",
        json={
            "course_id": "c1",
            "question": "链表如何实现",
            "source_mode": "none",
            "selected_doc_ids": [],
            "idempotency_key": "viewer-direct-report",
        },
    )

    assert response.status_code == 202
    assert response.json()["task_id"] == "student-report-job"
    assert captured["command"].owner_user_id == "teacher-a"
    assert captured["command"].resource_type == "report"


def test_generation_tool_catalog_is_filtered_by_authenticated_role(
    preflight_client,
):
    client, active_user = preflight_client
    active_user["role"] = "student"

    response = client.get("/api/chat/v2/generation/tools")

    assert response.status_code == 200
    assert [item["tool_id"] for item in response.json()["tools"]] == [
        "report",
        "ppt",
        "mind_map",
        "quiz",
        "classroom",
        "flashcard",
        "game",
    ]
    assert all(
        item == {
            "tool_id": item["tool_id"],
            "output_scope": "personal",
            "allowed_source_scopes": ["none", "personal", "course"],
            "can_publish": False,
        }
        for item in response.json()["tools"]
    )


def test_direct_generation_rejects_cross_course_selected_document_before_submit(
    preflight_client,
):
    client, _ = preflight_client

    response = client.post(
        "/api/chat/v2/report/direct",
        json={
            "course_id": "c1",
            "question": "链表如何实现",
            "source_mode": "selected_documents",
            "selected_doc_ids": ["doc-other-course"],
            "idempotency_key": "cross-course-direct-report",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SOURCE_DOCUMENT_WRONG_COURSE"


def test_preflight_rejects_unknown_resource_type(preflight_client):
    client, _ = preflight_client

    response = client.post(
        "/api/chat/v2/generation/preflight",
        json={
            "course_id": "c1",
            "resource_type": "unknown",
            "source_mode": "none",
            "selected_doc_ids": [],
        },
    )

    assert response.status_code == 422

