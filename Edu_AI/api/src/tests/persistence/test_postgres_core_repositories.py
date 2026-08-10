from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base, Course, CourseMembership, CourseObjective, User


def _repository_types():
    try:
        from app.persistence.postgres_repositories import (
            PostgresCourseMembershipRepository,
            PostgresCourseRepository,
            PostgresUserRepository,
        )
    except ModuleNotFoundError:
        pytest.fail("PostgreSQL core repositories are not implemented")
    return (
        PostgresUserRepository,
        PostgresCourseRepository,
        PostgresCourseMembershipRepository,
    )


@pytest.fixture
def engine():
    value = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(value)
    try:
        yield value
    finally:
        value.dispose()


def test_user_repository_upsert_updates_existing_user_without_duplicate(engine):
    PostgresUserRepository, _, _ = _repository_types()
    repository = PostgresUserRepository(engine)
    created_at = "2026-08-10T09:00:00+00:00"

    repository.upsert(
        {
            "username": "teacher-one",
            "password_hash": "pbkdf2_sha256$1$salt$hash",
            "role": "teacher",
            "display_name": "Teacher One",
            "created_at": created_at,
        }
    )
    repository.upsert(
        {
            "username": "teacher-one",
            "password_hash": "pbkdf2_sha256$2$salt$new-hash",
            "role": "admin",
            "display_name": "课程管理员",
            "created_at": created_at,
        }
    )

    with Session(engine) as session:
        users = session.scalars(select(User)).all()
        assert len(users) == 1
        assert users[0].user_id == "teacher-one"
        assert users[0].role == "admin"
        assert users[0].password_hash == "pbkdf2_sha256$2$salt$new-hash"
        assert users[0].raw_payload["display_name"] == "课程管理员"


def test_course_repository_upsert_replaces_objectives(engine):
    PostgresUserRepository, PostgresCourseRepository, _ = _repository_types()
    PostgresUserRepository(engine).upsert(
        {
            "username": "teacher-one",
            "password_hash": "hash",
            "role": "teacher",
        }
    )
    repository = PostgresCourseRepository(engine)

    repository.upsert(
        {
            "id": "algorithms",
            "title": "算法设计",
            "description": "第一版",
            "created_by": "teacher-one",
            "revision": 0,
            "objectives": ["理解算法", "分析复杂度"],
        }
    )
    repository.upsert(
        {
            "id": "algorithms",
            "title": "算法设计与分析",
            "description": "第二版",
            "created_by": "teacher-one",
            "revision": 1,
            "objectives": ["设计并验证算法"],
        }
    )

    with Session(engine) as session:
        course = session.get(Course, "algorithms")
        objectives = session.scalars(
            select(CourseObjective)
            .where(CourseObjective.course_id == "algorithms")
            .order_by(CourseObjective.position)
        ).all()
        assert course is not None
        assert course.title == "算法设计与分析"
        assert course.revision == 1
        assert [item.objective for item in objectives] == ["设计并验证算法"]


def test_course_repository_persists_and_resolves_unique_course_code(engine):
    _, PostgresCourseRepository, _ = _repository_types()
    repository = PostgresCourseRepository(engine)

    repository.upsert(
        {
            "id": "python-control-flow",
            "title": "Python 控制流程入门",
            "course_code": "ABCD2345",
            "objectives": ["条件判断", "循环控制"],
        }
    )

    assert repository.get("python-control-flow")["course_code"] == "ABCD2345"
    assert repository.get_by_course_code("abcd2345")["id"] == "python-control-flow"


def test_membership_repository_upserts_role_and_deletes_membership(engine):
    (
        PostgresUserRepository,
        PostgresCourseRepository,
        PostgresCourseMembershipRepository,
    ) = _repository_types()
    PostgresUserRepository(engine).upsert(
        {"username": "student-one", "password_hash": "hash", "role": "student"}
    )
    PostgresCourseRepository(engine).upsert(
        {"id": "algorithms", "title": "算法设计", "objectives": []}
    )
    repository = PostgresCourseMembershipRepository(engine)
    joined_at = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc).isoformat()

    repository.upsert(
        {
            "course_id": "algorithms",
            "user_id": "student-one",
            "role": "viewer",
            "joined_at": joined_at,
            "added_by": "teacher-one",
        }
    )
    repository.upsert(
        {
            "course_id": "algorithms",
            "user_id": "student-one",
            "role": "editor",
            "joined_at": joined_at,
            "added_by": "admin",
        }
    )

    with Session(engine) as session:
        membership = session.get(
            CourseMembership, ("algorithms", "student-one")
        )
        assert membership is not None
        assert membership.role == "editor"
        assert membership.added_by == "admin"

    assert repository.delete("algorithms", "student-one") is True
    assert repository.delete("algorithms", "student-one") is False


def test_core_repositories_read_database_records(engine):
    (
        PostgresUserRepository,
        PostgresCourseRepository,
        PostgresCourseMembershipRepository,
    ) = _repository_types()
    users = PostgresUserRepository(engine)
    courses = PostgresCourseRepository(engine)
    memberships = PostgresCourseMembershipRepository(engine)
    users.upsert(
        {
            "username": "read-user",
            "password_hash": "hash",
            "role": "student",
            "display_name": "Read User",
        }
    )
    courses.upsert(
        {
            "id": "read-course",
            "title": "Read Course",
            "revision": 2,
            "objectives": ["First", "Second"],
        }
    )
    memberships.upsert(
        {
            "course_id": "read-course",
            "user_id": "read-user",
            "role": "viewer",
            "added_by": "system",
        }
    )

    assert users.get("read-user")["display_name"] == "Read User"
    assert [item["username"] for item in users.list()] == ["read-user"]
    assert courses.get("read-course")["objectives"] == ["First", "Second"]
    assert [item["id"] for item in courses.list()] == ["read-course"]
    membership = memberships.get("read-course", "read-user")
    assert membership is not None
    assert memberships.list_for_user("read-user") == [membership]
    assert memberships.list_for_course("read-course") == [membership]
