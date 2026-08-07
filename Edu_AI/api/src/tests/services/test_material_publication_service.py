from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from app.services.material_publication_service import (
    MaterialPublicationError,
    MaterialPublicationService,
)
from core.course_storage import CourseStorageManager


def _private_report_with_attachment(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "report",
        "draft-1",
        {
            "title": "个人报告",
            "summary": "可发布摘要",
            "final_markdown": "# 最终报告",
            "file_extension": ".md",
        },
        file_data=b"# final artifact",
        owner_user_id="teacher-a",
        source_snapshot={
            "absolute_path": r"C:\Users\alice\private.md",
            "private_document": "PRIVATE_DOCUMENT_BODY",
        },
        config_snapshot={"api_key": "sk-private-test-value"},
    )
    source = manager.get_generated_material(
        "course-1", "report", "draft-1", owner_user_id="teacher-a"
    )
    return manager, source


def test_publish_creates_sanitized_independent_course_snapshot(tmp_path):
    manager, source = _private_report_with_attachment(tmp_path)

    result = MaterialPublicationService(manager).publish(
        course_id="course-1",
        material_type="report",
        material_id=source["material_id"],
        owner_user_id="teacher-a",
    )

    assert result.action == "published"
    assert result.material["visibility"] == "course"
    assert result.material["owner_user_id"] is None
    assert result.material["created_by"] == "teacher-a"
    assert result.material["published_by"] == "teacher-a"
    assert result.material["published_from_material_id"] == "draft-1"
    assert result.material["published_from_owner_user_id"] == "teacher-a"
    assert result.material["published_from_version"] == 1
    assert result.material["title"] == "个人报告"
    assert result.material["final_markdown"] == "# 最终报告"
    assert "source_snapshot" not in result.material
    assert "config_snapshot" not in result.material
    serialized = str(result.material)
    assert "sk-private-test-value" not in serialized
    assert r"C:\Users\alice\private.md" not in serialized
    assert "PRIVATE_DOCUMENT_BODY" not in serialized

    published_path = manager.get_file_path(
        "course-1", result.material["artifact_paths"][0]
    )
    assert published_path.read_bytes() == b"# final artifact"
    assert Path(result.material["artifact_paths"][0]).parts[:2] == (
        "generated_materials",
        "published",
    )
    assert result.material["artifact_paths"] != source["artifact_paths"]


def test_republish_is_unchanged_then_updates_same_snapshot(tmp_path):
    manager, source = _private_report_with_attachment(tmp_path)
    service = MaterialPublicationService(manager)
    first = service.publish(
        course_id="course-1",
        material_type="report",
        material_id=source["material_id"],
        owner_user_id="teacher-a",
    )

    unchanged = service.publish(
        course_id="course-1",
        material_type="report",
        material_id=source["material_id"],
        owner_user_id="teacher-a",
    )

    assert unchanged.action == "unchanged"
    assert unchanged.material["material_id"] == first.material["material_id"]
    assert unchanged.material["version"] == 1

    assert manager.rename_generated_material(
        "course-1",
        "report",
        source["material_id"],
        "修订后的报告",
        owner_user_id="teacher-a",
    )
    updated = service.publish(
        course_id="course-1",
        material_type="report",
        material_id=source["material_id"],
        owner_user_id="teacher-a",
    )

    assert updated.action == "updated"
    assert updated.material["material_id"] == first.material["material_id"]
    assert updated.material["version"] == 2
    assert updated.material["published_from_version"] == 2
    assert updated.material["title"] == "修订后的报告"


def test_publish_rejects_non_owner_without_revealing_source(tmp_path):
    manager, source = _private_report_with_attachment(tmp_path)

    with pytest.raises(MaterialPublicationError) as raised:
        MaterialPublicationService(manager).publish(
            course_id="course-1",
            material_type="report",
            material_id=source["material_id"],
            owner_user_id="teacher-b",
        )

    assert raised.value.code == "MATERIAL_NOT_FOUND"


def test_publish_rejects_artifact_path_outside_course_root(tmp_path):
    manager, source = _private_report_with_attachment(tmp_path)
    material_file = manager._material_file("course-1", "report", source["material_id"])
    stored = manager._read_json(material_file)
    stored["artifact_paths"] = ["../outside.txt"]
    stored["file_path"] = "../outside.txt"
    manager._write_json(material_file, stored)

    with pytest.raises(MaterialPublicationError) as raised:
        MaterialPublicationService(manager).publish(
            course_id="course-1",
            material_type="report",
            material_id=source["material_id"],
            owner_user_id="teacher-a",
        )

    assert raised.value.code == "MATERIAL_ARTIFACT_UNSAFE"
    assert manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="course"
    ) == []


def test_withdraw_removes_snapshot_and_published_files_but_keeps_private_source(tmp_path):
    manager, source = _private_report_with_attachment(tmp_path)
    service = MaterialPublicationService(manager)
    published = service.publish(
        course_id="course-1",
        material_type="report",
        material_id=source["material_id"],
        owner_user_id="teacher-a",
    )
    published_path = manager.get_file_path(
        "course-1", published.material["artifact_paths"][0]
    )
    assert published_path.exists()

    removed = service.withdraw(
        course_id="course-1",
        material_type="report",
        published_material_id=published.material["material_id"],
    )

    assert removed["material_id"] == published.material["material_id"]
    assert manager.get_stored_generated_material(
        "course-1", "report", published.material["material_id"]
    ) is None
    assert published_path.exists() is False
    source_after = manager.get_generated_material(
        "course-1", "report", source["material_id"], owner_user_id="teacher-a"
    )
    assert source_after is not None
    assert source_after.get("published_material_id") is None
    assert source_after.get("published_version") is None
    assert source_after.get("published_at") is None


def test_failed_source_link_update_restores_previous_publication(tmp_path, monkeypatch):
    manager, source = _private_report_with_attachment(tmp_path)
    service = MaterialPublicationService(manager)
    first = service.publish(
        course_id="course-1",
        material_type="report",
        material_id=source["material_id"],
        owner_user_id="teacher-a",
    )
    published_file = manager._material_file(
        "course-1", "report", first.material["material_id"]
    )
    previous_manifest = published_file.read_bytes()
    previous_artifact_path = manager.get_file_path(
        "course-1", first.material["artifact_paths"][0]
    )
    previous_artifact = previous_artifact_path.read_bytes()
    assert manager.save_generated_material(
        "course-1",
        "report",
        source["material_id"],
        {
            "title": "不会完成发布的修订",
            "summary": "修订摘要",
            "final_markdown": "# 修订报告",
            "file_extension": ".md",
        },
        file_data=b"# revised artifact",
        owner_user_id="teacher-a",
    )
    monkeypatch.setattr(
        manager,
        "update_generated_material_metadata",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(MaterialPublicationError) as raised:
        service.publish(
            course_id="course-1",
            material_type="report",
            material_id=source["material_id"],
            owner_user_id="teacher-a",
        )

    assert raised.value.code == "MATERIAL_PUBLICATION_INVALID"
    assert published_file.read_bytes() == previous_manifest
    assert previous_artifact_path.read_bytes() == previous_artifact


def test_concurrent_publish_creates_one_stable_course_snapshot(tmp_path):
    manager, source = _private_report_with_attachment(tmp_path)
    service = MaterialPublicationService(manager)
    start = Barrier(2)

    def publish_once():
        start.wait()
        return service.publish(
            course_id="course-1",
            material_type="report",
            material_id=source["material_id"],
            owner_user_id="teacher-a",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: publish_once(), range(2)))

    assert {result.action for result in results} == {"published", "unchanged"}
    assert len({result.material["material_id"] for result in results}) == 1
    snapshots = manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="course"
    )
    assert len(snapshots) == 1
    assert snapshots[0]["material_id"] == results[0].material["material_id"]
