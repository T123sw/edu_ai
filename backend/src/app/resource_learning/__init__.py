"""Versioned learning evidence for published course resources."""

from .manifest import build_classroom_learning_manifest
from .repository import ResourceLearningRepository
from .service import ResourceLearningRuleError, ResourceLearningService

__all__ = [
    "ResourceLearningRepository",
    "ResourceLearningRuleError",
    "ResourceLearningService",
    "build_classroom_learning_manifest",
]
