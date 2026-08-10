from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from app.database import DatabaseNotConfigured
from core.config import Config

from .modes import PersistenceMode, PersistenceSettings
from .postgres_conversation_repository import PostgresConversationRepository
from .postgres_job_repository import PostgresJobRepository
from .postgres_material_repository import PostgresMaterialRepository
from .postgres_knowledge_repository import PostgresKnowledgeRepository
from .postgres_repositories import (
    PostgresCourseMembershipRepository,
    PostgresCourseRepository,
    PostgresUserRepository,
)
from .shadow import CoreShadowPersistence, JsonlShadowFailureJournal


class _UnavailableRepository:
    def upsert(self, value: Any) -> None:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")

    def delete(self, *keys: str) -> bool:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")

    def __getattr__(self, name: str):
        raise DatabaseNotConfigured("DATABASE_URL is not configured")


@lru_cache(maxsize=16)
def _build_shadow_persistence(
    database_url: str,
    user_mode: str,
    course_mode: str,
    membership_mode: str,
    failure_journal_path: str,
) -> CoreShadowPersistence:
    settings = PersistenceSettings(
        user=PersistenceMode(user_mode),
        course=PersistenceMode(course_mode),
        course_membership=PersistenceMode(membership_mode),
    )
    if database_url:
        engine = create_engine(database_url, pool_pre_ping=True)
        user_repository = PostgresUserRepository(engine)
        course_repository = PostgresCourseRepository(engine)
        membership_repository = PostgresCourseMembershipRepository(engine)
    else:
        unavailable = _UnavailableRepository()
        user_repository = unavailable
        course_repository = unavailable
        membership_repository = unavailable
    return CoreShadowPersistence(
        settings=settings,
        user_repository=user_repository,
        course_repository=course_repository,
        course_membership_repository=membership_repository,
        failure_journal=JsonlShadowFailureJournal(failure_journal_path),
    )


def get_core_shadow_persistence() -> CoreShadowPersistence:
    settings = PersistenceSettings.from_environment()
    journal_path = Path(
        os.getenv(
            "SHADOW_FAILURE_JOURNAL",
            str(Path(Config.STORAGE_ROOT) / "database_shadow_failures.jsonl"),
        )
    )
    return _build_shadow_persistence(
        str(os.getenv("DATABASE_URL", "")).strip(),
        settings.user.value,
        settings.course.value,
        settings.course_membership.value,
        str(journal_path.resolve()),
    )


@lru_cache(maxsize=8)
def _build_core_repositories(database_url: str):
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    return (
        PostgresUserRepository(engine),
        PostgresCourseRepository(engine),
        PostgresCourseMembershipRepository(engine),
    )


def get_core_postgres_repositories():
    database_url = str(os.getenv("DATABASE_URL", "")).strip()
    return _build_core_repositories(database_url)


@lru_cache(maxsize=8)
def _build_conversation_repository(database_url: str):
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    return PostgresConversationRepository(
        create_engine(database_url, pool_pre_ping=True)
    )


def get_postgres_conversation_repository():
    database_url = str(os.getenv("DATABASE_URL", "")).strip()
    return _build_conversation_repository(database_url)


@lru_cache(maxsize=8)
def _build_job_repository(database_url: str):
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    return PostgresJobRepository(create_engine(database_url, pool_pre_ping=True))


def get_postgres_job_repository():
    database_url = str(os.getenv("DATABASE_URL", "")).strip()
    return _build_job_repository(database_url)


@lru_cache(maxsize=8)
def _build_material_repository(database_url: str):
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    return PostgresMaterialRepository(
        create_engine(database_url, pool_pre_ping=True)
    )


def get_postgres_material_repository():
    database_url = str(os.getenv("DATABASE_URL", "")).strip()
    return _build_material_repository(database_url)


@lru_cache(maxsize=8)
def _build_knowledge_repository(database_url: str):
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    return PostgresKnowledgeRepository(
        create_engine(database_url, pool_pre_ping=True)
    )


def get_postgres_knowledge_repository():
    database_url = str(os.getenv("DATABASE_URL", "")).strip()
    return _build_knowledge_repository(database_url)
