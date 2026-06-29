"""Test isolation for LangGraph runtime tests.

Phase 6-A.2 moved the MemorySaver to module scope so checkpoints survive
across requests (which fixed the real bug of active_draft_outline /
accumulated_images vanishing between user messages).

Side effect for tests: a single shared MemorySaver leaks state across test
cases that reuse conversation_ids. Reset it before each test.
"""
import pytest


@pytest.fixture(autouse=True)
def _reset_runtime_checkpointer():
    from app.chat.runtime.graph import builder
    builder._SHARED_CHECKPOINTER = None
    yield
    builder._SHARED_CHECKPOINTER = None
