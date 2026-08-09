from types import SimpleNamespace

from app.chat.runtime.agent_tools.handlers.resource import handle_generate_resource


def _ctx():
    return SimpleNamespace(
        capability=SimpleNamespace(allow_rag=False, selected_doc_ids=[]),
        request=SimpleNamespace(
            owner="teacher-a", course_id="course-1", conversation_id="conv-1",
            scope_type="course", scope_id=None,
        ),
        task_contract={
            "schema_version": "2026-08-09", "intent": "generate_single",
            "topic": "快速排序", "resource_types": ["blog"],
        },
        logical_task_id="task-stable-1",
        _call_cache={},
    )


def test_agent_generation_uses_a_deterministic_idempotency_key(monkeypatch):
    captured = []

    class Service:
        def submit(self, command):
            captured.append(command)
            return SimpleNamespace(edu_job_id="job-blog-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.resource.generation_command_service", Service()
    )

    first = handle_generate_resource("generate_blog", {"topic": "快速排序"}, _ctx())
    second = handle_generate_resource("generate_blog", {"topic": "快速排序"}, _ctx())

    assert first["ok"] and second["ok"]
    assert captured[0].idempotency_key == captured[1].idempotency_key
    assert captured[0].idempotency_key.startswith("agent-blog-")


def test_agent_generation_key_changes_when_contract_changes(monkeypatch):
    captured = []

    class Service:
        def submit(self, command):
            captured.append(command)
            return SimpleNamespace(edu_job_id="job-blog-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.resource.generation_command_service", Service()
    )
    first_ctx = _ctx()
    second_ctx = _ctx()
    second_ctx.task_contract = {**second_ctx.task_contract, "topic": "归并排序"}

    handle_generate_resource("generate_blog", {"topic": "快速排序"}, first_ctx)
    handle_generate_resource("generate_blog", {"topic": "归并排序"}, second_ctx)

    assert captured[0].idempotency_key != captured[1].idempotency_key
