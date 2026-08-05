from core.course_storage import (
    CourseStorageManager,
    reset_generation_persistence_context,
    set_generation_persistence_context,
)


def test_legacy_generator_inherits_owner_job_and_config_snapshot(tmp_path):
    manager = CourseStorageManager(tmp_path)
    token = set_generation_persistence_context(
        owner_user_id="teacher-a",
        source_job_id="job-1",
        config_snapshot_id="cfg-1",
    )
    try:
        assert manager.save_generated_material(
            "course-1",
            "report",
            "report-1",
            {"title": "报告"},
        )
    finally:
        reset_generation_persistence_context(token)

    material = manager.get_generated_material(
        "course-1",
        "report",
        "report-1",
        owner_user_id="teacher-a",
    )
    assert material["owner_user_id"] == "teacher-a"
    assert material["source_job_id"] == "job-1"
    assert material["config_snapshot_id"] == "cfg-1"
