from __future__ import annotations

import pytest


def _persistence_types():
    try:
        from app.persistence.modes import PersistenceMode, PersistenceSettings
    except ModuleNotFoundError:
        pytest.fail("persistence mode configuration is not implemented")
    return PersistenceMode, PersistenceSettings


def test_persistence_modes_default_to_json(monkeypatch: pytest.MonkeyPatch):
    PersistenceMode, PersistenceSettings = _persistence_types()
    for domain in ("USER", "COURSE", "COURSE_MEMBERSHIP"):
        monkeypatch.delenv(f"{domain}_PERSISTENCE_MODE", raising=False)

    settings = PersistenceSettings.from_environment()

    assert settings.user is PersistenceMode.JSON
    assert settings.course is PersistenceMode.JSON
    assert settings.course_membership is PersistenceMode.JSON


def test_persistence_modes_can_enable_one_shadow_domain(
    monkeypatch: pytest.MonkeyPatch,
):
    PersistenceMode, PersistenceSettings = _persistence_types()
    monkeypatch.setenv("COURSE_PERSISTENCE_MODE", "shadow")
    monkeypatch.delenv("USER_PERSISTENCE_MODE", raising=False)
    monkeypatch.delenv("COURSE_MEMBERSHIP_PERSISTENCE_MODE", raising=False)

    settings = PersistenceSettings.from_environment()

    assert settings.user is PersistenceMode.JSON
    assert settings.course is PersistenceMode.SHADOW
    assert settings.course_membership is PersistenceMode.JSON


def test_persistence_modes_reject_unknown_values(monkeypatch: pytest.MonkeyPatch):
    _, PersistenceSettings = _persistence_types()
    monkeypatch.setenv("USER_PERSISTENCE_MODE", "automatic")

    with pytest.raises(ValueError, match="USER_PERSISTENCE_MODE"):
        PersistenceSettings.from_environment()


def test_persistence_modes_support_postgres_cutover(
    monkeypatch: pytest.MonkeyPatch,
):
    PersistenceMode, PersistenceSettings = _persistence_types()
    monkeypatch.setenv("USER_PERSISTENCE_MODE", "postgres")
    monkeypatch.setenv("COURSE_PERSISTENCE_MODE", "postgres")
    monkeypatch.setenv("COURSE_MEMBERSHIP_PERSISTENCE_MODE", "postgres")

    settings = PersistenceSettings.from_environment()

    assert settings.user is PersistenceMode.POSTGRES
    assert settings.course is PersistenceMode.POSTGRES
    assert settings.course_membership is PersistenceMode.POSTGRES
