from __future__ import annotations

from app.services.course_membership_store import CourseMembershipStore
from scripts.migrate_course_memberships import migrate_memberships


def test_migration_dry_run_reports_without_writing(tmp_path):
    path = tmp_path / "memberships.json"
    store = CourseMembershipStore(path)

    report = migrate_memberships(
        store=store,
        users=[{"username": "teacher-a", "role": "teacher"}],
        course_ids=["course-1"],
        apply=False,
    )

    assert report.created == 1
    assert report.applied is False
    assert path.exists() is False


def test_migration_apply_is_idempotent(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    arguments = {
        "store": store,
        "users": [{"username": "teacher-a", "role": "teacher"}],
        "course_ids": ["course-1"],
        "apply": True,
    }

    first = migrate_memberships(**arguments)
    second = migrate_memberships(**arguments)

    assert first.created == 1
    assert second.created == 0
    assert second.unchanged == 1
    assert store.get("course-1", "teacher-a").role == "editor"
