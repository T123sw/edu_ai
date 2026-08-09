from types import SimpleNamespace

from app.chat.runtime.agent_tools.handlers.control import handle_query_task_status


def test_status_resolves_persisted_material_for_quality_audit(monkeypatch):
    ctx = SimpleNamespace(
        request=SimpleNamespace(owner="teacher-a"),
        pending_tasks=[{"task_id": "job-1", "workflow_type": "report"}],
    )
    result_ref = {
        "resource_type": "course_material",
        "course_id": "course-1",
        "material_type": "report",
        "material_id": "report-1",
    }
    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.control.get_job",
        lambda _job_id: SimpleNamespace(status="succeeded", result_ref=result_ref, error_message=None),
    )
    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.control.storage_manager.get_generated_material",
        lambda *_args, **_kwargs: {"title": "报告", "content": "## 核心内容\n" + "内容。" * 60},
    )
    result = handle_query_task_status("query_task_status", {}, ctx)
    readback = result["payload"]["artifact_readback"]
    assert readback["readable"] is True
    assert readback["artifacts"][0]["resource_type"] == "report"
    assert readback["artifacts"][0]["artifact"]["title"] == "报告"
