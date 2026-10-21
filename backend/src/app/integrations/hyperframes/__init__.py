"""Edu_AI adapters for the unmodified native HyperFrames runtime."""
from .contracts import validate_content, resolve_position
from .projects import ProjectStore

__all__ = ['validate_content', 'resolve_position', 'ProjectStore']
