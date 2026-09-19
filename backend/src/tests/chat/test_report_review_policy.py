"""Keep legacy report routing and publication on the same server policy."""

from types import SimpleNamespace

import pytest

from app.services.generation_source_resolver import ResolvedGenerationSource
from app.services.generation_task_handlers import GenerationTaskHandler


POLICIES = [
    pytest.param({}, "standard", id="ordinary-workbench"),
    pytest.param({"review_policy": "standard"}, "standard", id="explicit-standard"),
    pytest.param({"review_policy": "required"}, "required", id="explicit-required"),
    pytest.param({"config": {"harness_review_required": True}}, "required", id="server-required"),
    pytest.param({"config": {"harness_outline_id": "outline"}}, "required", id="legacy-harness"),
    pytest.param({"config": {"harness_outline_id": "outline", "harness_review_required": False}}, "required", id="legacy-marker-preserved"),
    pytest.param({"review_policy": "standard", "config": {"harness_outline_id": "outline"}}, "standard", id="explicit-standard-with-outline"),
    pytest.param({"review_policy": "standard", "config": {"harness_review_required": True}}, "required", id="client-cannot-relax-server"),
    pytest.param({"review_policy": "required", "config": {"review_policy": "standard"}}, "required", id="config-cannot-relax-command"),
    pytest.param({"review_policy": "standard", "config": {"review_policy": "required"}}, "required", id="nested-required"),
    pytest.param({"config": {"harness_review_required": False}}, "standard", id="false-without-outline"),
    pytest.param({"config": {"harness_outline_id": ""}}, "standard", id="empty-outline"),
]


@pytest.mark.parametrize("fields,expected", POLICIES)
@pytest.mark.parametrize("as_namespace", [False, True], ids=["mapping", "namespace"])
def test_policy_matrix(fields, expected, as_namespace):
    from app.chat.harness.review_policy import resolve_review_policy

    value = SimpleNamespace(**fields) if as_namespace else fields
    assert resolve_review_policy(value) == expected


@pytest.mark.parametrize("fields,expected", POLICIES)
def test_generation_and_publication_agree_on_policy(fields, expected, monkeypatch):
    calls = []
    saved = []
    artifact = {"artifact_type": "report", "content": "Unreviewed report"}

    class DirectGenerator:
        def generate(self, payload, **kwargs):
            calls.append(("standard", payload.review_policy))
            return {"artifacts": [artifact]}

    def reviewed_generate(payload):
        calls.append(("required", payload.review_policy))
        # Missing review must be caught before publication, even after a
        # generator returned successfully.
        return artifact["content"], {}

    monkeypatch.setattr(
        "app.chat.harness.reviewed_report.generate_reviewed_report", reviewed_generate
    )
    source = ResolvedGenerationSource(
        course_id="course", mode="none", requested_document_ids=(),
        documents=(), context_text="", resolved_at="",
    )
    storage = SimpleNamespace(
        save_generated_material=lambda **kwargs: saved.append(kwargs) or True,
        get_generated_material=lambda *args, **kwargs: {"version": 1},
    )
    handler = GenerationTaskHandler(
        course_storage_manager=storage,
        service_factories={"report": DirectGenerator},
        source_resolver=SimpleNamespace(resolve=lambda *args: source),
    )
    context = SimpleNamespace(
        task_id="job", course_id="course", owner_user_id="owner",
        config_snapshot_id="snapshot", progress=lambda *args: None,
        is_cancel_requested=lambda: False,
    )
    command = {
        "resource_type": "report", "course_id": "course", "source_mode": "none",
        "material_id": "report", **fields,
        "config": {"subject": "Subject", **fields.get("config", {})},
    }
    if expected == "required":
        with pytest.raises(ValueError, match="review_missing_or_stale"):
            handler(command, context)
        assert not saved
    else:
        assert handler(command, context)["saved"] is True
        assert len(saved) == 1
    assert calls == [(expected, expected)]
