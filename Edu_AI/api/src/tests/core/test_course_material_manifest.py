import json
import threading

from core.course_storage import CourseStorageManager


def test_formal_material_manifest_contains_stable_provenance_and_artifact(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")

    saved = manager.save_generated_material(
        "course-1",
        "flashcard",
        "deck:1",
        {
            "title": "排序算法闪卡",
            "source": {"document_ids": ["doc-1"]},
            "file_extension": ".json",
        },
        file_data=b'{"cards":[]}',
        owner_user_id="teacher-a",
        source_job_id="job-1",
        config_snapshot_id="cfg-1",
    )

    assert saved is True
    material = manager.get_generated_material(
        "course-1", "flashcard", "deck:1", owner_user_id="teacher-a"
    )
    assert material["schema_version"] == 2
    assert material["version"] == 1
    assert material["material_id"] == "deck__1"
    assert material["owner_user_id"] == "teacher-a"
    assert material["source_job_id"] == "job-1"
    assert material["config_snapshot_id"] == "cfg-1"
    assert material["source"]["document_ids"] == ["doc-1"]
    assert material["content_hash"]
    assert manager.check_generated_material_integrity(
        "course-1", "flashcard", "deck:1", owner_user_id="teacher-a"
    )["ok"] is True


def test_manifest_write_failure_removes_new_attachment(tmp_path, monkeypatch):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")

    def fail_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(manager, "_write_json", fail_write)
    assert manager.save_generated_material(
        "course-1",
        "ppt",
        "deck-1",
        {"title": "PPT", "file_extension": ".pptx"},
        file_data=b"pptx",
    ) is False
    material_dir = manager._material_dir("course-1", "ppt")
    assert list(material_dir.glob("deck-1*")) == []
    assert list(material_dir.glob("*.tmp")) == []


def test_concurrent_manifest_updates_never_leave_invalid_json(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")

    def save(index: int):
        assert manager.save_generated_material(
            "course-1",
            "report",
            "report-1",
            {"title": f"报告 {index}", "content": f"content-{index}"},
        )

    threads = [threading.Thread(target=save, args=(index,)) for index in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    path = manager._material_file("course-1", "report", "report-1")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 12
    assert payload["title"].startswith("报告 ")


def test_formal_types_never_fall_back_to_others(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    for material_type in ("ppt", "flashcard", "game", "classroom"):
        assert manager.save_generated_material(
            "course-1", material_type, f"{material_type}-1", {"title": material_type}
        )
        assert "others" not in str(
            manager._material_file("course-1", material_type, f"{material_type}-1")
        )

