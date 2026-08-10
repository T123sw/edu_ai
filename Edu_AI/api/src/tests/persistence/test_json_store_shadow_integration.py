from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, Course, CourseMembership, User
from app.persistence.postgres_repositories import (
    PostgresCourseRepository,
    PostgresUserRepository,
)
from app.services.course_membership_store import CourseMembershipStore
from core.course_storage import CourseStorageManager
from core.user_storage import UserStorage


def _database_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.as_posix()}"


def _configure_shadow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    user: str = "json",
    course: str = "json",
    membership: str = "json",
):
    database_url = _database_url(tmp_path / "shadow.db")
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("USER_PERSISTENCE_MODE", user)
    monkeypatch.setenv("COURSE_PERSISTENCE_MODE", course)
    monkeypatch.setenv("COURSE_MEMBERSHIP_PERSISTENCE_MODE", membership)
    monkeypatch.setenv(
        "SHADOW_FAILURE_JOURNAL",
        str(tmp_path / "shadow-failures.jsonl"),
    )
    return engine


def test_user_json_store_shadows_created_user_to_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    engine = _configure_shadow(monkeypatch, tmp_path, user="shadow")
    storage = UserStorage(str(tmp_path / "users.json"))

    storage.create_user("new-teacher", "safe-password", "teacher")

    with Session(engine) as session:
        user = session.get(User, "new-teacher")
        assert user is not None
        assert user.role == "teacher"


def test_course_json_store_shadows_saved_course_to_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    engine = _configure_shadow(monkeypatch, tmp_path, course="shadow")
    manager = CourseStorageManager(str(tmp_path / "course-data"))
    manager.create_course_structure("new-course")

    assert manager.save_course_info(
        "new-course",
        {
            "id": "new-course",
            "title": "新课程",
            "description": "影子迁移课程",
            "objectives": ["目标一"],
        },
    )

    with Session(engine) as session:
        course = session.get(Course, "new-course")
        assert course is not None
        assert course.title == "新课程"


def test_membership_json_store_shadows_upsert_and_delete_to_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    engine = _configure_shadow(monkeypatch, tmp_path, membership="shadow")
    PostgresUserRepository(engine).upsert(
        {"username": "student-one", "password_hash": "hash", "role": "student"}
    )
    PostgresCourseRepository(engine).upsert(
        {"id": "new-course", "title": "新课程", "objectives": []}
    )
    storage = CourseMembershipStore(tmp_path / "memberships.json")

    storage.upsert(
        "new-course",
        "student-one",
        "viewer",
        added_by="teacher-one",
    )

    with Session(engine) as session:
        membership = session.get(CourseMembership, ("new-course", "student-one"))
        assert membership is not None
        assert membership.role == "viewer"

    assert storage.delete("new-course", "student-one") is True
    with Session(engine) as session:
        assert session.get(
            CourseMembership, ("new-course", "student-one")
        ) is None
