from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _database_api():
    try:
        from app.database import (
            Base,
            Course,
            CourseMembership,
            CourseObjective,
            database_session,
            User,
            probe_database,
        )
    except ModuleNotFoundError as exc:  # RED: database foundation is not implemented yet.
        pytest.fail(f"database foundation is missing: {exc}")
    return {
        "Base": Base,
        "Course": Course,
        "CourseMembership": CourseMembership,
        "CourseObjective": CourseObjective,
        "database_session": database_session,
        "User": User,
        "probe_database": probe_database,
    }


def test_core_models_preserve_existing_ids_and_relationships() -> None:
    api = _database_api()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    api["Base"].metadata.create_all(engine)

    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    with Session(engine) as session:
        teacher = api["User"](
            user_id="teacher",
            username="teacher",
            password_hash="pbkdf2_sha256$fixture",
            role="teacher",
            created_at=now,
            updated_at=now,
            raw_payload={"legacy_username": "teacher"},
        )
        course = api["Course"](
            course_id="computational-thinking",
            title="计算思维",
            description="面向本科生的计算思维课程",
            icon="menu_book",
            color="#2563eb",
            revision=3,
            created_by="teacher",
            created_at=now,
            updated_at=now,
            raw_payload={"legacy_field": "kept"},
        )
        course.objectives.append(
            api["CourseObjective"](position=0, objective="掌握问题分解")
        )
        course.memberships.append(
            api["CourseMembership"](
                user=teacher,
                role="owner",
                joined_at=now,
                added_by="teacher",
            )
        )
        session.add(course)
        session.commit()

        loaded = session.scalar(
            select(api["Course"]).where(
                api["Course"].course_id == "computational-thinking"
            )
        )
        assert loaded is not None
        assert loaded.created_by == "teacher"
        assert loaded.raw_payload == {"legacy_field": "kept"}
        assert [(item.position, item.objective) for item in loaded.objectives] == [
            (0, "掌握问题分解")
        ]
        assert [(item.user_id, item.role) for item in loaded.memberships] == [
            ("teacher", "owner")
        ]


def test_membership_composite_key_rejects_duplicate_course_user_pair() -> None:
    api = _database_api()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    api["Base"].metadata.create_all(engine)

    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(
            api["User"](
                user_id="teacher",
                username="teacher",
                password_hash="hash",
                role="teacher",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            api["Course"](
                course_id="course-1",
                title="课程",
                description="",
                icon="menu_book",
                color="#2563eb",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        session.add_all(
            [
                api["CourseMembership"](
                    course_id="course-1",
                    user_id="teacher",
                    role="owner",
                    joined_at=now,
                    added_by="teacher",
                ),
                api["CourseMembership"](
                    course_id="course-1",
                    user_id="teacher",
                    role="editor",
                    joined_at=now,
                    added_by="teacher",
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_membership_accepts_non_user_system_actor_from_legacy_audit_data() -> None:
    api = _database_api()
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    api["Base"].metadata.create_all(engine)
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(
            api["User"](
                user_id="teacher",
                username="teacher",
                password_hash="hash",
                role="teacher",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            api["Course"](
                course_id="course-1",
                title="课程",
                description="",
                icon="menu_book",
                color="#2563eb",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        session.add(
            api["CourseMembership"](
                course_id="course-1",
                user_id="teacher",
                role="owner",
                joined_at=now,
                added_by="development-auto-enroll",
            )
        )
        session.commit()

        membership = session.get(
            api["CourseMembership"],
            {"course_id": "course-1", "user_id": "teacher"},
        )
        assert membership is not None
        assert membership.added_by == "development-auto-enroll"


def test_database_probe_is_disabled_without_configuration() -> None:
    api = _database_api()

    result = api["probe_database"](database_url="")

    assert result == {
        "configured": False,
        "status": "disabled",
        "message": "database is not configured",
    }


def test_database_probe_reports_ready_for_reachable_database() -> None:
    api = _database_api()
    engine = create_engine("sqlite+pysqlite:///:memory:")

    result = api["probe_database"](engine=engine)

    assert result == {
        "configured": True,
        "status": "ready",
        "message": "database connection ready",
    }


def test_database_session_commits_successful_unit_of_work() -> None:
    api = _database_api()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    api["Base"].metadata.create_all(engine)

    with api["database_session"](engine=engine) as session:
        session.add(
            api["User"](
                user_id="teacher",
                username="teacher",
                password_hash="hash",
                role="teacher",
            )
        )

    with Session(engine) as verification_session:
        persisted = verification_session.get(api["User"], "teacher")
        assert persisted is not None
        assert persisted.username == "teacher"


def test_database_session_rolls_back_failed_unit_of_work() -> None:
    api = _database_api()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    api["Base"].metadata.create_all(engine)

    with pytest.raises(RuntimeError, match="stop migration"):
        with api["database_session"](engine=engine) as session:
            session.add(
                api["User"](
                    user_id="teacher",
                    username="teacher",
                    password_hash="hash",
                    role="teacher",
                )
            )
            raise RuntimeError("stop migration")

    with Session(engine) as verification_session:
        assert verification_session.get(api["User"], "teacher") is None
