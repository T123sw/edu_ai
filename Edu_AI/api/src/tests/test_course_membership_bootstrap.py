from __future__ import annotations

from app.services.course_membership_bootstrap import CourseMembershipBootstrap
from app.services.course_membership_store import CourseMembershipStore


def test_sync_existing_assigns_development_roles(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    bootstrap = CourseMembershipBootstrap(store=store, enabled=True)

    summary = bootstrap.sync_existing(
        users=[
            {"username": "t1", "role": "teacher"},
            {"username": "s1", "role": "student"},
        ],
        course_ids=["c1", "c2"],
    )

    assert summary.created == 4
    assert summary.updated == 0
    assert store.get("c1", "t1").role == "editor"
    assert store.get("c1", "s1").role == "viewer"


def test_sync_is_idempotent_and_never_downgrades_owner(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    store.upsert("c1", "t1", "owner", added_by="creator")
    bootstrap = CourseMembershipBootstrap(store=store, enabled=True)

    first = bootstrap.sync_existing(
        users=[{"username": "t1", "role": "teacher"}],
        course_ids=["c1"],
    )
    second = bootstrap.sync_existing(
        users=[{"username": "t1", "role": "teacher"}],
        course_ids=["c1"],
    )

    assert first.created == first.updated == 0
    assert second.created == second.updated == 0
    assert store.get("c1", "t1").role == "owner"


def test_disabled_mode_creates_nothing(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    bootstrap = CourseMembershipBootstrap(store=store, enabled=False)

    summary = bootstrap.sync_existing(
        users=[{"username": "t1", "role": "teacher"}],
        course_ids=["c1"],
    )

    assert summary.created == summary.updated == 0
    assert store.list_for_course("c1") == []


def test_new_user_and_course_hooks_use_current_providers(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    users = [{"username": "teacher-a", "role": "teacher"}]
    courses = ["course-1"]
    bootstrap = CourseMembershipBootstrap(
        store=store,
        enabled=True,
        users_provider=lambda: list(users),
        course_ids_provider=lambda: list(courses),
    )

    bootstrap.on_user_created({"username": "student-a", "role": "student"})
    bootstrap.on_course_created("course-2")

    assert store.get("course-1", "student-a").role == "viewer"
    assert store.get("course-2", "teacher-a").role == "editor"
