"""Thin dependency helpers for the backend bootstrap layer."""

from __future__ import annotations

from modules.rag_v2.api import get_rag_system as _get_rag_system


def get_rag_system():
    return _get_rag_system()

