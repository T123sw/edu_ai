from __future__ import annotations

import json

from core.course_storage import CourseStorageManager
from app.api.courses import _knowledge_document_model
from scripts.migrate_course_document_ids import migrate_course_documents


def _write_index(manager, course_id, records):
    manager.create_course_structure(course_id)
    path = manager.get_course_dir(course_id) / "knowledge_base" / "index.json"
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return path


def test_migration_dry_run_reports_repair_without_writing(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    index_path = _write_index(
        manager,
        "course-1",
        [
            {
                "filename": "Mechanics.pdf",
                "path": "knowledge_base/documents/Mechanics.pdf",
                "status": "ready",
            }
        ],
    )
    before = index_path.read_bytes()
    rag_index = {
        "rag/key/mechanics": {
            "path": "knowledge_base/documents/Mechanics.pdf",
            "file_name": "Mechanics.pdf",
            "chunk_count": 12,
        }
    }

    report = migrate_course_documents(
        tmp_path,
        apply=False,
        rag_document_index=rag_index,
    )

    assert report.applied is False
    assert report.scanned_count == 1
    assert report.repairable_count == 1
    assert report.changed_count == 0
    assert report.issues[0]["changes"] == [
        "assign_public_id",
        "repair_rag_index_key",
    ]
    assert index_path.read_bytes() == before


def test_dry_run_does_not_create_an_absent_storage_root(tmp_path):
    absent_root = tmp_path / "does-not-exist"

    report = migrate_course_documents(
        absent_root,
        apply=False,
        rag_document_index={},
    )

    assert report.scanned_count == 0
    assert absent_root.exists() is False


def test_migration_apply_is_idempotent_and_backfills_ready_metadata(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    _write_index(
        manager,
        "course-1",
        [
            {
                "filename": "Mechanics.pdf",
                "path": "knowledge_base/documents/Mechanics.pdf",
                "status": "ready",
            }
        ],
    )
    rag_index = {
        "rag/key/mechanics": {
            "path": "knowledge_base/documents/Mechanics.pdf",
            "file_name": "Mechanics.pdf",
            "chunk_count": 12,
        }
    }

    first = migrate_course_documents(
        tmp_path,
        apply=True,
        rag_document_index=rag_index,
    )
    migrated = manager.get_knowledge_base_index("course-1")[0]
    second = migrate_course_documents(
        tmp_path,
        apply=True,
        rag_document_index=rag_index,
    )

    assert first.changed_count == 1
    assert migrated["id"].startswith("doc-")
    assert "Mechanics.pdf" not in migrated["id"]
    assert migrated["rag_index_key"] == "rag/key/mechanics"
    assert migrated["status"] == "ready"
    assert migrated["chunk_count"] == 12
    assert second.repairable_count == 0
    assert second.changed_count == 0


def test_migration_marks_document_failed_when_rag_index_is_missing(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    _write_index(
        manager,
        "course-1",
        [
            {
                "id": "doc-existing",
                "filename": "Missing.pdf",
                "path": "knowledge_base/documents/Missing.pdf",
                "rag_index_key": "rag/key/gone",
                "status": "ready",
                "chunk_count": 7,
            }
        ],
    )

    report = migrate_course_documents(
        tmp_path,
        apply=True,
        rag_document_index={},
    )
    migrated = manager.get_knowledge_base_index("course-1")[0]

    assert report.changed_count == 1
    assert migrated["id"] == "doc-existing"
    assert migrated["rag_index_key"] is None
    assert migrated["status"] == "failed"
    assert migrated["chunk_count"] == 0
    assert migrated["error_code"] == "RAG_INDEX_MISSING"


def test_duplicate_public_ids_are_repaired_deterministically(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    for course_id, filename in (
        ("course-1", "A.pdf"),
        ("course-2", "B.pdf"),
    ):
        _write_index(
            manager,
            course_id,
            [
                {
                    "id": "doc-duplicate",
                    "filename": filename,
                    "path": f"knowledge_base/documents/{filename}",
                    "status": "received",
                }
            ],
        )

    migrate_course_documents(tmp_path, apply=True, rag_document_index={})
    first_ids = {
        manager.get_knowledge_base_index(course_id)[0]["id"]
        for course_id in ("course-1", "course-2")
    }
    rerun = migrate_course_documents(tmp_path, apply=True, rag_document_index={})

    assert len(first_ids) == 2
    assert "doc-duplicate" not in first_ids
    assert rerun.changed_count == 0


def test_course_document_response_hides_internal_relative_path():
    model = _knowledge_document_model(
        {
            "id": "doc-public",
            "filename": "Mechanics.pdf",
            "path": "knowledge_base/documents/Mechanics.pdf",
            "status": "ready",
        },
        "course-1",
    )

    assert model.id == "doc-public"
    assert model.file_path is None
