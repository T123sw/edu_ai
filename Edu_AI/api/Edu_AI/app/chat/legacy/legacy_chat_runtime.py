from __future__ import annotations

def _build_default_backend():
    from app.chat.service import ChatService

    return ChatService()


class LegacyChatRuntime:
    """Thin wrapper that exposes the legacy chat entrypoints as a stable runtime."""

    _BACKEND_CHAT_KWARGS = {
        "question",
        "conversation_id",
        "model_id",
        "use_rag",
        "selected_doc_ids",
        "owner",
        "course_id",
    }

    def __init__(self, *, backend=None, backend_factory=None):
        self._backend = backend
        self._backend_factory = backend_factory or _build_default_backend

    @property
    def backend(self):
        if self._backend is None:
            self._backend = self._backend_factory()
        return self._backend

    def chat(self, **kwargs):
        return self.backend.chat(**self._filter_backend_kwargs(kwargs))

    def chat_stream_with_meta(self, **kwargs):
        return self.backend.chat_stream_with_meta(**self._filter_backend_kwargs(kwargs))

    def skill_health_check(self, meta):
        return self.backend.skill_health_check(meta)

    def get_report_engine(self):
        return self.backend.get_report_engine()

    def get_lesson_plan_engine(self):
        return self.backend.get_lesson_plan_engine()

    def _filter_backend_kwargs(self, kwargs):
        return {key: value for key, value in kwargs.items() if key in self._BACKEND_CHAT_KWARGS}
