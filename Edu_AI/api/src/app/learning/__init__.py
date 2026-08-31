"""Course learning interaction domain."""

import threading
from pathlib import Path

from .service import LearningRuleError, LearningService
from .store import LearningStore


_service_lock = threading.RLock()
_cached_path: Path | None = None
_cached_store: LearningStore | None = None
_cached_service: LearningService | None = None


def get_learning_service() -> LearningService:
    """Return the process-level learning service shared by API and Agents."""
    global _cached_path, _cached_store, _cached_service
    from app.api.course_dependencies import get_course_membership_store
    from app.services import course_service
    from core import Config

    path = Path(Config.LEARNING_DB_PATH)
    with _service_lock:
        if _cached_service is None or _cached_path != path:
            if _cached_store is not None:
                _cached_store.close()
            membership_store = get_course_membership_store()
            manager = course_service._get_manager()
            from app.persistence.dependencies import get_postgres_material_repository
            from app.persistence.dependencies import get_resource_learning_repository
            from app.resource_learning.task_evidence import TaskResourceEvidenceAdapter
            from app.database.session import DatabaseNotConfigured

            try:
                evidence_adapter = TaskResourceEvidenceAdapter(
                    get_resource_learning_repository()
                )
            except DatabaseNotConfigured:
                evidence_adapter = None

            _cached_path = path
            _cached_store = LearningStore(path)
            _cached_service = LearningService(
                store=_cached_store,
                material_lookup=lambda course_id, material_type, material_id, user_id: (
                    manager.get_generated_material(
                        course_id,
                        material_type,
                        material_id,
                        owner_user_id=user_id,
                    )
                ),
                material_version_lookup=lambda course_id, material_type, material_id, version: (
                    get_postgres_material_repository().get_version(
                        course_id, material_type, material_id, version
                    )
                ),
                membership_lookup=membership_store.list_for_course,
                task_evidence_adapter=evidence_adapter,
            )
        return _cached_service


__all__ = [
    "LearningRuleError",
    "LearningService",
    "LearningStore",
    "get_learning_service",
]
