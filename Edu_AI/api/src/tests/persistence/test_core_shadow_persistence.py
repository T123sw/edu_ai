from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, User
from app.persistence.modes import PersistenceMode, PersistenceSettings
from app.persistence.postgres_repositories import (
    PostgresCourseMembershipRepository,
    PostgresCourseRepository,
    PostgresUserRepository,
)


def _shadow_types():
    try:
        from app.persistence.shadow import (
            CoreShadowPersistence,
            JsonlShadowFailureJournal,
        )
    except ModuleNotFoundError:
        pytest.fail("core shadow persistence is not implemented")
    return CoreShadowPersistence, JsonlShadowFailureJournal


def _settings(*, user: PersistenceMode) -> PersistenceSettings:
    return PersistenceSettings(
        user=user,
        course=PersistenceMode.JSON,
        course_membership=PersistenceMode.JSON,
    )


def _shadow_service(engine, journal_path, *, user_mode: PersistenceMode):
    CoreShadowPersistence, JsonlShadowFailureJournal = _shadow_types()
    return CoreShadowPersistence(
        settings=_settings(user=user_mode),
        user_repository=PostgresUserRepository(engine),
        course_repository=PostgresCourseRepository(engine),
        course_membership_repository=PostgresCourseMembershipRepository(engine),
        failure_journal=JsonlShadowFailureJournal(journal_path),
    )


def test_json_mode_does_not_attempt_database_write(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    journal_path = tmp_path / "shadow-failures.jsonl"
    service = _shadow_service(
        engine,
        journal_path,
        user_mode=PersistenceMode.JSON,
    )

    result = service.upsert_user(
        {"username": "teacher", "password_hash": "secret-hash", "role": "teacher"}
    )

    assert result.attempted is False
    assert result.succeeded is True
    assert not journal_path.exists()


def test_shadow_mode_writes_user_to_database(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    service = _shadow_service(
        engine,
        tmp_path / "shadow-failures.jsonl",
        user_mode=PersistenceMode.SHADOW,
    )

    result = service.upsert_user(
        {"username": "teacher", "password_hash": "secret-hash", "role": "teacher"}
    )

    with Session(engine) as session:
        user = session.get(User, "teacher")
        assert user is not None
        assert user.role == "teacher"
    assert result.attempted is True
    assert result.succeeded is True


def test_shadow_failure_is_recorded_without_sensitive_payload(tmp_path):
    engine_without_schema = create_engine("sqlite+pysqlite:///:memory:")
    journal_path = tmp_path / "shadow-failures.jsonl"
    service = _shadow_service(
        engine_without_schema,
        journal_path,
        user_mode=PersistenceMode.SHADOW,
    )

    result = service.upsert_user(
        {
            "username": "teacher",
            "password_hash": "must-never-enter-the-journal",
            "role": "teacher",
        }
    )

    event = json.loads(journal_path.read_text(encoding="utf-8"))
    journal_text = journal_path.read_text(encoding="utf-8")
    assert result.attempted is True
    assert result.succeeded is False
    assert event["domain"] == "user"
    assert event["operation"] == "upsert"
    assert event["entity_key"] == "teacher"
    assert event["error_type"] == "OperationalError"
    assert "must-never-enter-the-journal" not in journal_text
