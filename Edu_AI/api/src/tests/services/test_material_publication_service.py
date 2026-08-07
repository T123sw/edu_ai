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


@pytest.mark.parametrize(
    ("material_type", "material_data", "expected_public_values"),
    [
        (
            "report",
            {
                "title": "报告",
                "report": {
                    "summary": "公开摘要",
                    "mainContent": [
                        {
                            "title": "公开章节",
                            "content": "公开正文",
                            "model_trace": "PRIVATE_TRACE",
                        }
                    ],
                    "private_notes": "PRIVATE_NOTES",
                },
            },
            ["公开摘要", "公开章节", "公开正文"],
        ),
        (
            "quiz",
            {
                "title": "测验",
                "content": {
                    "difficulty": "medium",
                    "questions": [
                        {
                            "id": "q1",
                            "type": "choice",
                            "question": "公开题干",
                            "choices": ["A", "B"],
                            "correct_answer": "A",
                            "private_rationale": "PRIVATE_RATIONALE",
                        }
                    ],
                    "draft_context": "PRIVATE_DRAFT_CONTEXT",
                },
            },
            ["公开题干", "A", "B"],
        ),
        (
            "ppt",
            {
                "title": "课件",
                "content": {
                    "pptx_url": "/files/deck.pptx",
                    "content_markdown": "# 公开课件",
                    "provider_debug": "PRIVATE_PROVIDER_DEBUG",
                },
                "outline": {
                    "deck_title": "公开大纲",
                    "slides": [
                        {
                            "slide_index": 1,
                            "title": "公开页面",
                            "goal": "公开目标",
                            "chain_of_thought": "PRIVATE_REASONING",
                        }
                    ],
                },
            },
            ["/files/deck.pptx", "# 公开课件", "公开大纲", "公开页面"],
        ),
        (
            "classroom",
            {
                "title": "课堂",
                "stage": {"id": "stage-1", "name": "公开课堂", "internal": "PRIVATE_INTERNAL"},
                "scenes": [
                    {
                        "id": "scene-1",
                        "type": "slide",
                        "content": {
                            "type": "slide",
                            "canvas": {
                                "id": "canvas-1",
                                "viewportRatio": 0.5625,
                                "elements": [
                                    {
                                        "id": "text-1",
                                        "type": "text",
                                        "content": "公开画面",
                                        "private_payload": "PRIVATE_CANVAS",
                                    }
                                ],
                            },
                        },
                        "actions": [
                            {
                                "id": "speech-1",
                                "type": "speech",
                                "text": "公开讲解",
                                "diagnostic": "PRIVATE_DIAGNOSTIC",
                            }
                        ],
                    }
                ],
            },
            ["公开课堂", "公开画面", "公开讲解"],
        ),
    ],
)
def test_publication_uses_positive_nested_schema_per_material_type(
    tmp_path, material_type, material_data, expected_public_values
):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        material_type,
        "draft-1",
        material_data,
        owner_user_id="teacher-a",
    )

    result = MaterialPublicationService(manager).publish(
        course_id="course-1",
        material_type=material_type,
        material_id="draft-1",
        owner_user_id="teacher-a",
    )

    serialized = str(result.material)
    for expected in expected_public_values:
        assert expected in serialized
    assert "PRIVATE_" not in serialized


@pytest.mark.parametrize("target_is_directory", [False, True])
def test_publish_rejects_nested_symlinks_in_artifact_directories(
    tmp_path, target_is_directory
):
    manager = CourseStorageManager(root_path=str(tmp_path / "storage"))
    manager.create_course_structure("course-1")
    course_root = manager.get_course_dir("course-1")
    artifact_dir = course_root / "generated_materials" / "draft-tree"
    artifact_dir.mkdir(parents=True)
    outside = tmp_path / ("outside-dir" if target_is_directory else "outside.txt")
    if target_is_directory:
        outside.mkdir()
        (outside / "secret.txt").write_text("PRIVATE_SYMLINK", encoding="utf-8")
    else:
        outside.write_text("PRIVATE_SYMLINK", encoding="utf-8")
    link = artifact_dir / ("linked-dir" if target_is_directory else "linked.txt")
    try:
        link.symlink_to(outside, target_is_directory=target_is_directory)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    assert manager.save_generated_material(
        "course-1",
        "report",
        "draft-1",
        {"title": "报告", "final_markdown": "# 公开报告"},
        owner_user_id="teacher-a",
    )
    manifest = manager._material_file("course-1", "report", "draft-1")
    stored = manager._read_json(manifest)
    stored["artifact_paths"] = [
        str(artifact_dir.relative_to(course_root)).replace("\\", "/")
    ]
    manager._write_json(manifest, stored)

    with pytest.raises(MaterialPublicationError) as raised:
        MaterialPublicationService(manager).publish(
            course_id="course-1",
            material_type="report",
            material_id="draft-1",
            owner_user_id="teacher-a",
        )

    assert raised.value.code == "MATERIAL_ARTIFACT_UNSAFE"


def test_publish_checks_every_artifact_descendant_for_links(tmp_path, monkeypatch):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    course_root = manager.get_course_dir("course-1")
    artifact_dir = course_root / "generated_materials" / "draft-tree"
    artifact_dir.mkdir(parents=True)
    nested_file = artifact_dir / "nested.txt"
    nested_file.write_text("public artifact", encoding="utf-8")
    assert manager.save_generated_material(
        "course-1",
        "report",
        "draft-1",
        {"title": "报告", "final_markdown": "# 公开报告"},
        owner_user_id="teacher-a",
    )
    manifest = manager._material_file("course-1", "report", "draft-1")
    stored = manager._read_json(manifest)
    stored["artifact_paths"] = [
        str(artifact_dir.relative_to(course_root)).replace("\\", "/")
    ]
    manager._write_json(manifest, stored)
    original_is_symlink = Path.is_symlink

    def simulated_is_symlink(path):
        return path.name == "nested.txt" or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", simulated_is_symlink)

    with pytest.raises(MaterialPublicationError) as raised:
        MaterialPublicationService(manager).publish(
            course_id="course-1",
            material_type="report",
            material_id="draft-1",
            owner_user_id="teacher-a",
        )

    assert raised.value.code == "MATERIAL_ARTIFACT_UNSAFE"


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
