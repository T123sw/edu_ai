from __future__ import annotations

from pathlib import Path

import pytest

from app.services.personal_knowledge_service import (
    PersonalKnowledgeNotFound,
    PersonalKnowledgeService,
    PersonalKnowledgeValidationError,
)


def test_personal_documents_are_aggregated_across_course_contexts_by_owner(
    tmp_path: Path,
):
    service = PersonalKnowledgeService(root_path=tmp_path / "personal")
    first = service.create_document(
        owner_user_id="student-a",
        filename="algebra.txt",
        file_data=b"algebra",
        course_context_id="course-1",
    )
    second = service.create_document(
        owner_user_id="student-a",
        filename="geometry.txt",
        file_data=b"geometry",
        course_context_id="course-2",
    )
    service.create_document(
        owner_user_id="student-b",
        filename="private.txt",
        file_data=b"private",
        course_context_id="course-1",
    )

    documents = service.list_documents(owner_user_id="student-a")

    assert {item["id"] for item in documents} == {first["id"], second["id"]}
    assert {item["course_context_id"] for item in documents} == {
        "course-1",
        "course-2",
    }
    assert service.list_documents(owner_user_id="teacher-a") == []


def test_personal_document_owner_controls_read_rename_and_delete(tmp_path: Path):
    service = PersonalKnowledgeService(root_path=tmp_path / "personal")
    created = service.create_document(
        owner_user_id="student-a",
        filename="notes.txt",
        file_data="个人笔记".encode(),
    )

    content = service.read_content(
        owner_user_id="student-a",
        document_id=created["id"],
    )
    renamed = service.rename_document(
        owner_user_id="student-a",
        document_id=created["id"],
        name="期末笔记.txt",
    )

    assert content["content"] == "个人笔记"
    assert renamed["filename"] == "期末笔记.txt"
    with pytest.raises(PersonalKnowledgeNotFound):
        service.get_document(
            owner_user_id="student-b",
            document_id=created["id"],
        )

    service.delete_document(
        owner_user_id="student-a",
        document_id=created["id"],
    )
    assert service.list_documents(owner_user_id="student-a") == []


@pytest.mark.parametrize(
    "filename",
    ["../escape.txt", "..\\escape.txt", "C:\\escape.txt", "/escape.txt", ""],
)
def test_personal_upload_rejects_unsafe_filenames(tmp_path: Path, filename: str):
    service = PersonalKnowledgeService(root_path=tmp_path / "personal")

    with pytest.raises(PersonalKnowledgeValidationError):
        service.create_document(
            owner_user_id="student-a",
            filename=filename,
            file_data=b"unsafe",
        )

    assert not (tmp_path / "escape.txt").exists()

