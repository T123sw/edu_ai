"""Versioned assessments for course learning tasks."""

import os
import threading
from pathlib import Path

from .models import (
    AssessmentAnswerRecord,
    AssessmentAssignmentRecord,
    AssessmentAttemptRecord,
    AssessmentItemRecord,
    AssessmentRecord,
    AssessmentReviewRecord,
    AssessmentVersionRecord,
)
from .policies import AssessmentPolicyError
from .service import AssessmentRuleError, AssessmentService
from .store import AssessmentStore


_service_lock = threading.RLock()
_cached_service: AssessmentService | None = None
_cached_store: AssessmentStore | None = None
_cached_path: Path | None = None


def get_assessment_service() -> AssessmentService:
    global _cached_service, _cached_store, _cached_path
    from app.learning import get_learning_service
    from app.services import course_service
    from core import Config

    path = Path(
        os.getenv(
            "ASSESSMENT_DB_PATH",
            str(Path(Config.LEARNING_DB_PATH).with_name("assessments.db")),
        )
    )
    with _service_lock:
        if _cached_service is None or _cached_path != path:
            if _cached_store is not None:
                _cached_store.close()
            manager = course_service._get_manager()
            learning_service = get_learning_service()
            _cached_path = path
            _cached_store = AssessmentStore(path)
            _cached_service = AssessmentService(
                store=_cached_store,
                learning_service=learning_service,
                material_lookup=lambda course_id, material_type, material_id, user_id: (
                    manager.get_generated_material(
                        course_id,
                        material_type,
                        material_id,
                        owner_user_id=user_id,
                    )
                ),
            )
        return _cached_service

__all__ = [
    "AssessmentAnswerRecord",
    "AssessmentAssignmentRecord",
    "AssessmentAttemptRecord",
    "AssessmentItemRecord",
    "AssessmentPolicyError",
    "AssessmentRuleError",
    "AssessmentRecord",
    "AssessmentReviewRecord",
    "AssessmentVersionRecord",
    "AssessmentService",
    "AssessmentStore",
    "get_assessment_service",
]
