import pytest

from app.persistence.retirement import validate_retired_legacy_storage


def test_database_profile_rejects_any_legacy_business_storage(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_PROFILE", "database")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://configured")
    for variable in (
        "USER_PERSISTENCE_MODE",
        "COURSE_PERSISTENCE_MODE",
        "COURSE_MEMBERSHIP_PERSISTENCE_MODE",
        "CONVERSATION_PERSISTENCE_MODE",
        "JOB_PERSISTENCE_MODE",
        "MATERIAL_PERSISTENCE_MODE",
        "KNOWLEDGE_PERSISTENCE_MODE",
        "APP_STATE_PERSISTENCE_MODE",
        "LEARNING_PERSISTENCE_MODE",
        "TASK_PERSISTENCE_MODE",
    ):
        monkeypatch.setenv(variable, "postgres")
    monkeypatch.setenv("CONVERSATION_PERSISTENCE_MODE", "json")

    with pytest.raises(RuntimeError, match="CONVERSATION_PERSISTENCE_MODE"):
        validate_retired_legacy_storage()


def test_database_profile_accepts_postgres_only(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_PROFILE", "database")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://configured")
    for variable in (
        "USER_PERSISTENCE_MODE",
        "COURSE_PERSISTENCE_MODE",
        "COURSE_MEMBERSHIP_PERSISTENCE_MODE",
        "CONVERSATION_PERSISTENCE_MODE",
        "JOB_PERSISTENCE_MODE",
        "MATERIAL_PERSISTENCE_MODE",
        "KNOWLEDGE_PERSISTENCE_MODE",
        "APP_STATE_PERSISTENCE_MODE",
        "LEARNING_PERSISTENCE_MODE",
        "TASK_PERSISTENCE_MODE",
    ):
        monkeypatch.setenv(variable, "postgres")

    validate_retired_legacy_storage()
