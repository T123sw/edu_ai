from types import SimpleNamespace

from app.chat.runtime.agent_tools.handlers.control import handle_cancel_task, handle_query_task_status


def _ctx():
    return SimpleNamespace(
        request=SimpleNamespace(owner="teacher-a"),
        pending_tasks=[{"task_id": "job-1", "workflow_type": "report"}],
    )


def test_status_reads_pending_task_without_creating_resources(monkeypatch):
    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.control.get_job",
        lambda job_id: SimpleNamespace(edu_job_id=job_id, status="running", result_ref=None, error_message=None),
    )
    result = handle_query_task_status("query_task_status", {}, _ctx())

    assert result["ok"] is True
    assert result["payload"]["tasks"][0]["status"] == "running"


def test_cancel_uses_pending_task_owner_scope(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.control.cancel_job",
        lambda task_id, owner_user_id: captured.update(task_id=task_id, owner=owner_user_id) or SimpleNamespace(status="cancel_requested"),
    )
    result = handle_cancel_task("cancel_task", {}, _ctx())

    assert result["ok"] is True
    assert captured == {"task_id": "job-1", "owner": "teacher-a"}


def test_status_marks_succeeded_job_readable_only_with_result_reference(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.control.get_job",
        lambda job_id: SimpleNamespace(
            edu_job_id=job_id, status="succeeded", result_ref={"material_id": "mat-1"}, error_message=None
        ),
    )

    result = handle_query_task_status("query_task_status", {}, ctx)

    assert result["payload"]["tasks"][0]["artifact_readable"] is True
    assert result["payload"]["artifact_readback"] == {"checked": 1, "readable": True}
