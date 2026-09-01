from __future__ import annotations

import asyncio

from app.chat.agents.report_generation import _ConfiguredFallbackChatModel


class _Model:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = 0

    def invoke(self, _input, config=None, **_kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result

    async def ainvoke(self, _input, config=None, **_kwargs):
        return self.invoke(_input, config=config, **_kwargs)


def test_configured_fallback_uses_backup_after_primary_provider_error():
    primary = _Model(error=RuntimeError("provider unavailable"))
    backup = _Model(result="ok")

    model = _ConfiguredFallbackChatModel([primary, backup])

    assert model.invoke("prompt") == "ok"
    assert primary.calls == 1
    assert backup.calls == 1


def test_configured_fallback_keeps_primary_when_it_is_healthy():
    primary = _Model(result="primary")
    backup = _Model(result="backup")

    model = _ConfiguredFallbackChatModel([primary, backup])

    assert model.invoke("prompt") == "primary"
    assert primary.calls == 1
    assert backup.calls == 0


def test_configured_fallback_supports_async_invocation():
    model = _ConfiguredFallbackChatModel(
        [_Model(error=RuntimeError("quota")), _Model(result="backup")]
    )

    assert asyncio.run(model.ainvoke("prompt")) == "backup"
