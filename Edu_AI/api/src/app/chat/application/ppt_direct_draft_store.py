from __future__ import annotations

from typing import Any


class InMemoryPptDirectDraftStore:
    def __init__(self):
        self._drafts: dict[str, dict[str, Any]] = {}

    def save(self, draft: dict[str, Any]) -> None:
        draft_id = str((draft or {}).get("draft_id") or "").strip()
        if not draft_id:
            raise ValueError("draft_id is required")
        self._drafts[draft_id] = dict(draft or {})

    def get(self, draft_id: str) -> dict[str, Any]:
        normalized = str(draft_id or "").strip()
        if normalized not in self._drafts:
            raise KeyError(normalized)
        return dict(self._drafts[normalized])

    def update(self, draft_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.get(draft_id)
        current.update(dict(patch or {}))
        self.save(current)
        return dict(current)


_DEFAULT_PPT_DIRECT_DRAFT_STORE = InMemoryPptDirectDraftStore()


def get_default_ppt_direct_draft_store() -> InMemoryPptDirectDraftStore:
    return _DEFAULT_PPT_DIRECT_DRAFT_STORE
