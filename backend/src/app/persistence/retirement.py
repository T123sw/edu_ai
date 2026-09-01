from __future__ import annotations

import os


POSTGRES_PERSISTENCE_VARIABLES = (
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
)


def validate_retired_legacy_storage() -> None:
    """Fail startup before any legacy business-data backend can be opened."""
    if os.getenv("PERSISTENCE_PROFILE", "compatibility").strip().lower() != "database":
        return
    if not os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError("DATABASE_URL is required by the database persistence profile")
    invalid = [
        name
        for name in POSTGRES_PERSISTENCE_VARIABLES
        if os.getenv(name, "").strip().lower() != "postgres"
    ]
    if invalid:
        raise RuntimeError(
            "Legacy business storage is retired; PostgreSQL is required for: "
            + ", ".join(invalid)
        )
