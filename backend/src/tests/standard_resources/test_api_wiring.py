from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

from app.api import standard_resources as api
from app.api.course_dependencies import require_course_generate


class _Materials:
    def list(self, _course_id):
        return []

    def get(self, *_args):
        return None

    def get_version(self, *_args):
        return None


def _context() -> dict:
    return {
        "course_id": "course-1",
        "owner_user_id": "teacher-1",
        "scope_type": "knowledge_point",
        "scope_id": "leaf-1",
        "origin_type": "standard",
        "standard_kind": "study_guide",
        "generation_batch_id": "batch-1",
        "current_review_status": "pending",
        "review_status": "pending",
        "title": "关系与键学习指南",
        "idempotency_key": "batch-1:leaf-1:study_guide:1",
        "deadline_seconds": 86400,
        "execution_timeout_seconds": 900,
        "action": "repair",
        "generation_context": {
            "bundle_spec": {
                "skill": "edu-standard-resource-bundle",
                "skill_version": "1.0.0",
                "objectives": ["区分候选键与主键"],
            },
            "baseline_version": 3,
            "baseline_summary": "旧版本把候选键等同于主键",
            "rejection_reason": "修正候选键与主键的区别",
        },
    }


def test_standard_resource_submitter_injects_skill_and_required_review(monkeypatch) -> None:
    submitted = []
    manager = SimpleNamespace(get_knowledge_graph=lambda _course_id: {})
    repository = SimpleNamespace()
    monkeypatch.setattr(api, "_manager", lambda: manager)
    monkeypatch.setattr(api, "get_postgres_material_repository", lambda: _Materials())
    monkeypatch.setattr(api, "get_standard_resource_repository", lambda: repository)
    monkeypatch.setattr(
        api.generation_command_service,
        "submit",
        lambda command: submitted.append(command) or SimpleNamespace(edu_job_id="job-1"),
    )
    service = api.get_standard_resource_batch_service()
    item = {
        "leaf_id": "leaf-1",
        "leaf_title": "关系与键",
        "standard_kind": "study_guide",
        "material_type": "report",
        "material_id": "standard-leaf-1-study_guide",
    }

    asyncio.run(service.submitter(item, _context()))

    command = submitted[0]
    assert command.review_policy == "required"
    assert command.config["entrypoint"] == "agent"
    assert command.config["standard_bundle_spec"]["skill_version"] == "1.0.0"
    assert "不得批准" in command.config["standard_bundle_contract"]
    assert command.config["baseline_version"] == 3
    assert "候选键与主键" in command.config["focus"]
    assert len(command.config["harness_chapters"]) == 4


def test_standard_classroom_uses_same_skill_contract_and_review_gate(monkeypatch) -> None:
    captured = {}
    manager = SimpleNamespace(get_knowledge_graph=lambda _course_id: {})
    monkeypatch.setattr(api, "_manager", lambda: manager)
    monkeypatch.setattr(api, "get_postgres_material_repository", lambda: _Materials())
    monkeypatch.setattr(api, "get_standard_resource_repository", lambda: SimpleNamespace())

    async def submit_classroom(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(edu_job_id="classroom-job")

    monkeypatch.setattr(api, "submit_classroom_generation_job", submit_classroom)
    service = api.get_standard_resource_batch_service()
    context = {**_context(), "standard_kind": "classroom"}
    item = {
        "leaf_id": "leaf-1",
        "leaf_title": "关系与键",
        "standard_kind": "classroom",
        "material_type": "classroom",
        "material_id": "standard-leaf-1-classroom",
    }

    asyncio.run(service.submitter(item, context))

    harness = captured["material_metadata"]["harness_config"]
    assert captured["material_metadata"]["review_policy"] == "required"
    assert harness["standard_bundle_spec"]["skill"] == "edu-standard-resource-bundle"
    assert "不得批准" in harness["standard_bundle_contract"]
    assert harness["baseline_version"] == 3


def test_batch_control_routes_require_course_generation_permission() -> None:
    for endpoint in (
        api.list_standard_resource_batches,
        api.get_standard_resource_batch,
    ):
        dependency = inspect.signature(endpoint).parameters["_principal"].default
        assert dependency.dependency is require_course_generate
