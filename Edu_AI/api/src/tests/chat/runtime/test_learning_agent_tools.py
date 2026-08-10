from types import SimpleNamespace

from app.chat.runtime.agent_tools import ToolExecutionContext, execute_tool
from app.chat.runtime.agent_tools.registry import get_tool_handler
from app.chat.runtime.nodes.executor import _build_mandatory_plan_calls
from app.learning.service import LearningService
from app.learning.store import LearningStore


def _tool_ctx(*, actor_role: str, learning_context: dict):
    ctx = ToolExecutionContext(
        capability=SimpleNamespace(
            allow_rag=False,
            allow_web=False,
            allow_image_search=False,
        ),
        request=SimpleNamespace(
            actor_role=actor_role,
            course_id="course-a",
            owner=f"{actor_role}-a",
        ),
        snapshot=SimpleNamespace(learning_context=learning_context),
        max_steps=4,
    )
    ctx.pending_tasks = [{"task_id": "job_old", "workflow_type": "report"}]
    return ctx


def test_student_learning_tool_returns_only_student_projection():
    ctx = _tool_ctx(
        actor_role="student",
        learning_context={
            "projection": "student",
            "as_of": "2026-08-10T12:00:00Z",
            "completed_tasks": [
                {
                    "task_id": "lt_1",
                    "title": "递归基础",
                    "completion_basis": "self_reported",
                }
            ],
            "pending_tasks": [{"task_id": "lt_2", "title": "递归练习"}],
        },
    )

    result = execute_tool("get_my_learning_progress", {}, ctx)

    assert result["ok"] is True
    assert result["payload"]["completed_tasks"][0]["task_id"] == "lt_1"
    assert result["payload"]["pending_tasks"][0]["task_id"] == "lt_2"
    assert "job_old" not in str(result)


def test_student_learning_tool_filters_lt_task_without_reclassifying_it():
    ctx = _tool_ctx(
        actor_role="student",
        learning_context={
            "projection": "student",
            "completed_tasks": [{"task_id": "lt_1", "title": "递归基础"}],
            "pending_tasks": [{"task_id": "lt_2", "title": "递归练习"}],
        },
    )

    result = execute_tool("get_my_learning_progress", {"task_id": "lt_2"}, ctx)

    assert result["ok"] is True
    assert result["payload"]["completed_tasks"] == []
    assert [item["task_id"] for item in result["payload"]["pending_tasks"]] == ["lt_2"]


def test_student_cannot_call_teacher_learning_tool():
    ctx = _tool_ctx(actor_role="student", learning_context={"projection": "student"})

    result = execute_tool("get_course_learning_progress", {}, ctx)

    assert result["ok"] is False
    assert result["error"] == "permission_denied"


def test_teacher_learning_tool_returns_aggregate_projection_only():
    ctx = _tool_ctx(
        actor_role="teacher",
        learning_context={
            "projection": "teacher",
            "as_of": "2026-08-10T12:00:00Z",
            "task_summaries": [
                {
                    "task_id": "lt_1",
                    "title": "递归基础",
                    "completed_students": 2,
                    "enrolled_students": 3,
                }
            ],
        },
    )

    result = execute_tool("get_course_learning_progress", {}, ctx)

    assert result["ok"] is True
    assert result["payload"]["task_summaries"][0]["task_id"] == "lt_1"
    assert "student_ids" not in str(result)


def test_teacher_tool_uses_real_service_minimal_aggregate_projection(tmp_path):
    memberships = [
        SimpleNamespace(user_id="teacher-secret", role="owner"),
        SimpleNamespace(user_id="student-secret-1", role="viewer"),
        SimpleNamespace(user_id="student-secret-2", role="viewer"),
    ]
    service = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda *_args: {
            "visibility": "course",
            "material_type": "report",
            "material_id": "private-kb-ref",
        },
        membership_lookup=lambda _course_id: memberships,
    )
    task = service.create_task(
        course_id="course-a",
        teacher_id="teacher-secret",
        title="递归基础",
        instructions="不应进入教师进度工具",
        resource_refs=[
            {"material_type": "report", "material_id": "private-kb-ref"}
        ],
        knowledge_point_ids=["private-knowledge-point"],
    )
    service.publish_task(
        course_id="course-a",
        task_id=task.task_id,
        teacher_id="teacher-secret",
    )
    service.record_student_event(
        course_id="course-a",
        task_id=task.task_id,
        student_id="student-secret-1",
        event_id="evt-in-progress",
        event_type="progress_updated",
        progress_percent=50,
        resource_ref=None,
    )
    service.record_student_event(
        course_id="course-a",
        task_id=task.task_id,
        student_id="student-secret-2",
        event_id="evt-completed",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )
    snapshot = SimpleNamespace(
        learning_context=service.get_teacher_agent_context(
            course_id="course-a", teacher_id="teacher-secret"
        )
    )
    ctx = ToolExecutionContext(
        capability=SimpleNamespace(
            allow_rag=False,
            allow_web=False,
            allow_image_search=False,
        ),
        request=SimpleNamespace(
            actor_role="teacher",
            course_id="course-a",
            owner="teacher-secret",
        ),
        snapshot=snapshot,
        max_steps=4,
    )

    result = execute_tool("get_course_learning_progress", {}, ctx)

    assert result["ok"] is True
    summary = result["payload"]["task_summaries"][0]
    assert set(summary) == {
        "task_id",
        "title",
        "status",
        "enrolled_students",
        "not_started_students",
        "in_progress_students",
        "started_students",
        "completed_students",
        "completion_rate",
        "completion_basis_counts",
        "latest_activity_at",
    }
    assert summary["in_progress_students"] == 1
    assert summary["completed_students"] == 1
    assert summary["completion_basis_counts"]["self_reported"] == 1
    serialized = str(result)
    assert "teacher-secret" not in serialized
    assert "student-secret" not in serialized
    assert "private-kb-ref" not in serialized
    assert "private-knowledge-point" not in serialized


def test_teacher_cannot_call_student_learning_tool():
    ctx = _tool_ctx(actor_role="teacher", learning_context={"projection": "teacher"})

    result = execute_tool("get_my_learning_progress", {}, ctx)

    assert result["ok"] is False
    assert result["error"] == "permission_denied"


def test_missing_learning_projection_never_falls_back_to_historical_generation_job():
    ctx = _tool_ctx(actor_role="student", learning_context={})

    result = execute_tool("get_my_learning_progress", {}, ctx)

    assert result["ok"] is False
    assert result["error"] == "permission_denied"
    assert "job_old" not in str(result)


def test_generation_status_rejects_learning_task_id_and_traces_domain_error():
    ctx = _tool_ctx(actor_role="student", learning_context={"projection": "student"})

    result = execute_tool("query_generation_job_status", {"task_id": "lt_1"}, ctx)

    assert result["ok"] is False
    assert result["error"] == "task_domain_mismatch"
    assert ctx.trace["agent_steps"][0]["error"] == "task_domain_mismatch"


def test_learning_tool_rejects_generation_job_id():
    ctx = _tool_ctx(actor_role="student", learning_context={"projection": "student"})

    result = execute_tool("get_my_learning_progress", {"task_id": "job_1"}, ctx)

    assert result["ok"] is False
    assert result["error"] == "task_domain_mismatch"


def test_generation_status_rejects_legacy_job_id_at_execution_boundary():
    ctx = _tool_ctx(actor_role="student", learning_context={"projection": "student"})

    result = execute_tool("query_generation_job_status", {"task_id": "job-legacy"}, ctx)

    assert result["ok"] is False
    assert result["error"] == "task_domain_mismatch"


def test_generation_status_does_not_return_another_owners_job(monkeypatch):
    ctx = _tool_ctx(actor_role="student", learning_context={"projection": "student"})
    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.control.get_job",
        lambda _task_id: SimpleNamespace(
            owner_user_id="student-b",
            status="running",
            result_ref=None,
            error_message=None,
        ),
    )

    result = execute_tool("query_generation_job_status", {"task_id": "job_1"}, ctx)

    assert result["ok"] is False
    assert result["error"] == "task_not_found"


def test_legacy_query_task_status_is_not_registered_for_model_execution():
    assert get_tool_handler("query_task_status") is None


def _strict_status_state(tool: str, refs: dict):
    return {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {
            "subject": "",
            "contract": {"conversation_refs": refs},
            "steps": [{"expected_tools": [tool]}],
        },
    }


def test_strict_learning_step_uses_learning_id_not_historical_generation_job():
    state = _strict_status_state(
        "get_my_learning_progress",
        {
            "current_learning_task_ids": ["lt_current"],
            "generation_job_ids": ["job_old"],
        },
    )

    calls = _build_mandatory_plan_calls(
        state, {}, SimpleNamespace(trace={"agent_steps": []})
    )

    assert calls[0]["args"] == {"task_id": "lt_current"}


def test_strict_generation_step_does_not_pass_legacy_job_id():
    state = _strict_status_state(
        "query_generation_job_status",
        {"generation_job_ids": ["job-legacy"]},
    )

    calls = _build_mandatory_plan_calls(
        state, {}, SimpleNamespace(trace={"agent_steps": []})
    )

    assert calls[0]["args"] == {}


def test_strict_generation_step_preserves_invalid_current_id_instead_of_history():
    state = _strict_status_state(
        "query_generation_job_status",
        {
            "current_generation_job_ids": ["job-explicit-legacy"],
            "generation_job_ids": ["job_historical"],
        },
    )

    calls = _build_mandatory_plan_calls(
        state, {}, SimpleNamespace(trace={"agent_steps": []})
    )

    assert calls[0]["args"] == {"task_id": "job-explicit-legacy"}
    result = execute_tool(
        calls[0]["name"],
        calls[0]["args"],
        _tool_ctx(actor_role="student", learning_context={"projection": "student"}),
    )
    assert result["error"] == "task_domain_mismatch"


def test_strict_learning_step_preserves_invalid_current_id_instead_of_history():
    state = _strict_status_state(
        "get_my_learning_progress",
        {
            "current_learning_task_ids": ["lt-explicit-legacy"],
            "learning_task_ids": ["lt_historical"],
        },
    )

    calls = _build_mandatory_plan_calls(
        state, {}, SimpleNamespace(trace={"agent_steps": []})
    )

    assert calls[0]["args"] == {"task_id": "lt-explicit-legacy"}
    result = execute_tool(
        calls[0]["name"],
        calls[0]["args"],
        _tool_ctx(actor_role="student", learning_context={"projection": "student"}),
    )
    assert result["error"] == "task_domain_mismatch"
