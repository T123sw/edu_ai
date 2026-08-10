from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .dependencies import get_core_shadow_persistence
from .shadow import ShadowWriteResult


log = logging.getLogger(__name__)


def _safe_shadow(action) -> ShadowWriteResult | None:
    try:
        return action(get_core_shadow_persistence())
    except Exception:
        log.exception("shadow persistence configuration failed")
        return None


def shadow_upsert_user(user: Mapping[str, Any]) -> ShadowWriteResult | None:
    return _safe_shadow(lambda persistence: persistence.upsert_user(user))


def shadow_upsert_course(course: Mapping[str, Any]) -> ShadowWriteResult | None:
    return _safe_shadow(lambda persistence: persistence.upsert_course(course))


def shadow_delete_course(course_id: str) -> ShadowWriteResult | None:
    return _safe_shadow(lambda persistence: persistence.delete_course(course_id))


def shadow_upsert_membership(
    membership: Mapping[str, Any],
) -> ShadowWriteResult | None:
    return _safe_shadow(
        lambda persistence: persistence.upsert_membership(membership)
    )


def shadow_delete_membership(
    course_id: str, user_id: str
) -> ShadowWriteResult | None:
    return _safe_shadow(
        lambda persistence: persistence.delete_membership(course_id, user_id)
    )
