from __future__ import annotations

import json

from app.services.course_membership_store import CourseMembershipStore


def test_upsert_is_unique_and_persists(tmp_path):
    path = tmp_path / "memberships.json"
    store = CourseMembershipStore(path)

    store.upsert("course-1", "teacher-a", "editor", added_by="system")
    store.upsert("course-1", "teacher-a", "owner", added_by="admin")

    reopened = CourseMembershipStore(path)
    membership = reopened.get("course-1", "teacher-a")
    assert membership is not None
    assert membership.role == "owner"
    assert membership.added_by == "admin"
    assert len(reopened.list_for_course("course-1")) == 1


def test_list_for_user_does_not_leak_other_users(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    store.upsert("course-1", "teacher-a", "editor", added_by="system")
    store.upsert("course-2", "student-a", "viewer", added_by="system")

    assert [item.course_id for item in store.list_for_user("teacher-a")] == [
        "course-1"
    ]


def test_delete_is_idempotent_and_keeps_valid_json(tmp_path):
    path = tmp_path / "memberships.json"
    store = CourseMembershipStore(path)
    store.upsert("course-1", "teacher-a", "editor", added_by="system")

    assert store.delete("course-1", "teacher-a") is True
    assert store.delete("course-1", "teacher-a") is False
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "memberships": [],
    }
