from types import SimpleNamespace

import pytest

from app.chat.memory.langmem_adapter import LangMemCandidateSchema
from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.settings import AgentMemorySettings


class _FakeManager:
    def invoke(self, payload):
        assert payload["messages"][0]["content"] == "以后请叫我小唐"
        content = SimpleNamespace(
            memory_type="profile_fact",
            content="用户希望被称为小唐",
            confidence=0.97,
            source_span="以后请叫我小唐",
            reason="用户明确要求",
            profile_axis="display_name",
            expires_at=None,
        )
        return [SimpleNamespace(id="candidate-1", content=content)]


def test_langmem_adapter_maps_structured_candidates() -> None:
    adapter = LangMemAdapter(
        settings=AgentMemorySettings(langmem_enabled=True),
        manager_factory=lambda: _FakeManager(),
    )

    result = adapter.extract_candidates(
        messages=[{"role": "user", "content": "以后请叫我小唐"}],
        existing_memories=[],
        policy_hint={},
    )

    assert result.status == "ok"
    assert result.provider == "langmem"
    assert result.candidates[0].profile_axis == "display_name"


def test_langmem_adapter_disabled_never_builds_manager() -> None:
    called = False

    def factory():
        nonlocal called
        called = True
        return _FakeManager()

    adapter = LangMemAdapter(
        settings=AgentMemorySettings(langmem_enabled=False),
        manager_factory=factory,
    )

    result = adapter.extract_candidates(
        messages=[], existing_memories=[], policy_hint={}
    )

    assert result.status == "disabled"
    assert called is False


def test_langmem_adapter_failure_degrades_without_raising() -> None:
    class BrokenManager:
        def invoke(self, payload):
            raise RuntimeError("provider unavailable")

    adapter = LangMemAdapter(
        settings=AgentMemorySettings(langmem_enabled=True),
        manager_factory=lambda: BrokenManager(),
    )

    result = adapter.extract_candidates(
        messages=[{"role": "user", "content": "记住我的偏好"}],
        existing_memories=[],
        policy_hint={},
    )

    assert result.status == "error"
    assert result.candidates == []
    assert "provider unavailable" in result.error


def test_langmem_adapter_treats_empty_schema_insert_as_no_candidates() -> None:
    class EmptyInsertManager:
        def invoke(self, payload):
            LangMemCandidateSchema.model_validate({})
            pytest.fail("validation should have raised")

    adapter = LangMemAdapter(
        settings=AgentMemorySettings(langmem_enabled=True),
        manager_factory=lambda: EmptyInsertManager(),
    )

    result = adapter.extract_candidates(
        messages=[{"role": "user", "content": "请解释递归"}],
        existing_memories=[],
        policy_hint={},
    )

    assert result.status == "empty"
    assert result.candidates == []
    assert result.error == ""


def test_langmem_adapter_normalizes_string_nulls() -> None:
    class StringNullManager:
        def invoke(self, payload):
            content = SimpleNamespace(
                memory_type="preference",
                content="用户偏好简短回答",
                confidence=0.95,
                source_span="以后请简短回答",
                reason="explicit preference",
                profile_axis="response_detail",
                expires_at="None",
            )
            return [SimpleNamespace(id="candidate-null", content=content)]

    adapter = LangMemAdapter(
        settings=AgentMemorySettings(langmem_enabled=True),
        manager_factory=lambda: StringNullManager(),
    )

    result = adapter.extract_candidates(
        messages=[{"role": "user", "content": "以后请简短回答"}],
        existing_memories=[],
        policy_hint={},
    )

    assert result.status == "ok"
    assert result.candidates[0].expires_at is None
