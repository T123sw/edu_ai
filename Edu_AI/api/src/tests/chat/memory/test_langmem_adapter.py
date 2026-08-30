from types import SimpleNamespace

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
