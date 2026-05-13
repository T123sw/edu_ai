from app.chat.application.ppt_direct_draft_store import InMemoryPptDirectDraftStore


def test_ppt_direct_draft_store_round_trips_draft():
    store = InMemoryPptDirectDraftStore()
    draft = {
        "draft_id": "ppt-draft-1",
        "selected_doc_ids": ["doc-1"],
        "selected_doc_snapshot_id": "snap-1",
        "normalized_ppt_config": {"deck_title": "Agent Basics"},
        "draft_outline": {"deck_title": "Agent Basics", "slides": []},
        "status": "outline_ready",
    }

    store.save(draft)
    loaded = store.get("ppt-draft-1")

    assert loaded["draft_id"] == "ppt-draft-1"
    assert loaded["selected_doc_snapshot_id"] == "snap-1"


def test_ppt_direct_draft_store_updates_existing_draft():
    store = InMemoryPptDirectDraftStore()
    store.save({"draft_id": "ppt-draft-1", "status": "outline_ready"})

    updated = store.update("ppt-draft-1", {"status": "generating", "run_id": "ppt-run-1"})

    assert updated["status"] == "generating"
    assert store.get("ppt-draft-1")["run_id"] == "ppt-run-1"
