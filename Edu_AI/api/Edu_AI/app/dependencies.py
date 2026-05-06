"""Thin dependency helpers for the backend bootstrap layer."""

from __future__ import annotations

from app.teaching_video_bridge import get_ai_lecturer_process_manager as _get_ai_lecturer_process_manager
from rag_v2.api import get_rag_system as _get_rag_system


def get_ai_lecturer_process_manager():
    return _get_ai_lecturer_process_manager()


def get_rag_system():
    return _get_rag_system()

