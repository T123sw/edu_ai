from __future__ import annotations

import json

import pytest

from app.services.runtime_config_resolver import RuntimeConfigResolver
from app.services.runtime_config_store import RuntimeConfigStore


def _values(model: str = "model-a"):
    return {
        "base_url": "https://provider.example/v1",
        "api_key": "sk-secret-value-123456",
        "model": model,
    }


def _verified(store: RuntimeConfigStore, *, scope: str, owner: str, model: str):
    draft = store.create_draft(
        scope=scope, owner_id=owner, provider="llm", values=_values(model)
    )
    store.mark_verification(
        scope=scope,
        owner_id=owner,
        provider="llm",
        revision_id=draft["revision_id"],
        ok=True,
    )
    return draft["revision_id"]


def test_runtime_config_encrypts_secrets_and_masks_api_responses(tmp_path):
    store = RuntimeConfigStore(root=tmp_path, master_key="test-master-key")
    draft = store.create_draft(
        scope="user", owner_id="teacher-a", provider="llm", values=_values()
    )

    raw_files = list(tmp_path.rglob("*.json"))
    assert len(raw_files) == 1
    raw_text = raw_files[0].read_text(encoding="utf-8")
    assert "sk-secret-value-123456" not in raw_text
    assert json.loads(raw_text)["revisions"][0]["encrypted_payload"]
    assert draft["values"]["api_key"] != "sk-secret-value-123456"
    assert "••••••" in draft["values"]["api_key"]


def test_only_verified_revisions_activate_and_rollback_preserves_history(tmp_path):
    store = RuntimeConfigStore(root=tmp_path, master_key="test-master-key")
    first = store.create_draft(
        scope="user", owner_id="teacher-a", provider="llm", values=_values("first")
    )
    with pytest.raises(ValueError, match="verified"):
        store.activate(
            scope="user",
            owner_id="teacher-a",
            provider="llm",
            revision_id=first["revision_id"],
        )

    first_id = _verified(store, scope="user", owner="teacher-a", model="first-active")
    store.activate(
        scope="user", owner_id="teacher-a", provider="llm", revision_id=first_id
    )
    second_id = _verified(store, scope="user", owner="teacher-a", model="second-active")
    store.activate(
        scope="user", owner_id="teacher-a", provider="llm", revision_id=second_id
    )

    rolled_back = store.rollback(scope="user", owner_id="teacher-a", provider="llm")
    assert rolled_back["revision_id"] == first_id
    assert store.get_active_values(
        scope="user", owner_id="teacher-a", provider="llm"
    )[1]["model"] == "first-active"


def test_resolver_applies_user_then_system_precedence_and_frozen_snapshot(tmp_path):
    store = RuntimeConfigStore(root=tmp_path, master_key="test-master-key")
    system_id = _verified(store, scope="system", owner="system", model="system-model")
    store.activate(
        scope="system", owner_id="system", provider="llm", revision_id=system_id
    )
    first_user_id = _verified(
        store, scope="user", owner="teacher-a", model="user-model-v1"
    )
    store.activate(
        scope="user",
        owner_id="teacher-a",
        provider="llm",
        revision_id=first_user_id,
    )
    resolver = RuntimeConfigResolver(store)
    frozen = resolver.capture_snapshot("teacher-a")

    second_user_id = _verified(
        store, scope="user", owner="teacher-a", model="user-model-v2"
    )
    store.activate(
        scope="user",
        owner_id="teacher-a",
        provider="llm",
        revision_id=second_user_id,
    )

    assert resolver.resolve("llm", owner_user_id="teacher-a")["model"] == "user-model-v2"
    assert resolver.resolve(
        "llm", owner_user_id="teacher-a", snapshot=frozen
    )["model"] == "user-model-v1"
    assert resolver.resolve("llm", owner_user_id="teacher-b")["model"] == "system-model"


def test_failed_activation_write_keeps_previous_active_revision(tmp_path, monkeypatch):
    store = RuntimeConfigStore(root=tmp_path, master_key="test-master-key")
    first_id = _verified(store, scope="user", owner="teacher-a", model="first")
    store.activate(
        scope="user", owner_id="teacher-a", provider="llm", revision_id=first_id
    )
    second_id = _verified(store, scope="user", owner="teacher-a", model="second")
    original_replace = __import__("os").replace

    def _fail_once(source, destination):
        monkeypatch.setattr("os.replace", original_replace)
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", _fail_once)
    with pytest.raises(OSError, match="disk full"):
        store.activate(
            scope="user",
            owner_id="teacher-a",
            provider="llm",
            revision_id=second_id,
        )

    active = store.get_active_values(
        scope="user", owner_id="teacher-a", provider="llm"
    )
    assert active[0] == first_id
    assert active[1]["model"] == "first"
