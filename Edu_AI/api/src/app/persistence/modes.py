from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class PersistenceMode(str, Enum):
    JSON = "json"
    SHADOW = "shadow"
    POSTGRES = "postgres"


def _mode_from_environment(variable_name: str) -> PersistenceMode:
    raw_value = str(os.getenv(variable_name, PersistenceMode.JSON.value)).strip().lower()
    try:
        return PersistenceMode(raw_value)
    except ValueError as exc:
        supported = ", ".join(mode.value for mode in PersistenceMode)
        raise ValueError(
            f"{variable_name} must be one of: {supported}; got {raw_value!r}"
        ) from exc


@dataclass(frozen=True)
class PersistenceSettings:
    user: PersistenceMode
    course: PersistenceMode
    course_membership: PersistenceMode

    @classmethod
    def from_environment(cls) -> "PersistenceSettings":
        return cls(
            user=_mode_from_environment("USER_PERSISTENCE_MODE"),
            course=_mode_from_environment("COURSE_PERSISTENCE_MODE"),
            course_membership=_mode_from_environment(
                "COURSE_MEMBERSHIP_PERSISTENCE_MODE"
            ),
        )
