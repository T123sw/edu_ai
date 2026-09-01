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


def test_user_store_uses_database_without_creating_json_in_postgres_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    engine = _configure_shadow(monkeypatch, tmp_path, user="postgres")
    json_path = tmp_path / "users.json"
    storage = UserStorage(str(json_path))

    storage.create_user("database-teacher", "safe-password", "teacher")

    assert storage.get_user("database-teacher")["role"] == "teacher"
    assert json_path.exists() is False
    with Session(engine) as session:
        assert session.get(User, "database-teacher") is not None


def test_course_store_uses_database_without_course_info_json_in_postgres_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    engine = _configure_shadow(monkeypatch, tmp_path, course="postgres")
    manager = CourseStorageManager(str(tmp_path / "course-data"))
    manager.create_course_structure("database-course")

    assert manager.save_course_info(
        "database-course",
        {
            "id": "database-course",
            "title": "Database Course",
            "description": "PostgreSQL primary storage",
            "objectives": ["Persist metadata"],
        },
    )

    assert manager.get_course_info("database-course")["title"] == "Database Course"
    assert not (
        tmp_path / "course-data" / "courses" / "database-course" / "course_info.json"
    ).exists()
    with Session(engine) as session:
        assert session.get(Course, "database-course") is not None


def test_membership_store_uses_database_without_json_in_postgres_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    engine = _configure_shadow(monkeypatch, tmp_path, membership="postgres")
    PostgresUserRepository(engine).upsert(
        {"username": "database-student", "password_hash": "hash", "role": "student"}
    )
    PostgresCourseRepository(engine).upsert(
        {"id": "database-course", "title": "Database Course", "objectives": []}
    )
    json_path = tmp_path / "memberships.json"
    storage = CourseMembershipStore(json_path)

    membership = storage.upsert(
        "database-course", "database-student", "viewer", added_by="system"
    )

    assert storage.get("database-course", "database-student") == membership
    assert storage.list_for_user("database-student") == [membership]
    assert storage.list_for_course("database-course") == [membership]
    assert json_path.exists() is False
    assert storage.delete("database-course", "database-student") is True
    assert storage.get("database-course", "database-student") is None
