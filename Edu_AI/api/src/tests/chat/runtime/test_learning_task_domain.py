from types import SimpleNamespace

from app.chat.runtime.agent_tools import ToolExecutionContext, execute_tool
from app.chat.runtime.agent_tools.schemas import build_tool_schemas
from app.chat.runtime.planning.compiler import compile_plan
from app.chat.runtime.planning.task_contract_extractor import extract_task_contract
from app.chat.domain.task_domain import resolve_task_domain


def capability():
    return SimpleNamespace(
        allow_rag=False,
        allow_web=False,
        allow_image_search=False,
        selected_doc_ids=[],
        source_mode="none",
    )


def learning_tool_context(*, actor_role: str, learning_context: dict):
    return ToolExecutionContext(
        capability=capability(),
        request=SimpleNamespace(
            actor_role=actor_role,
            course_id="course-a",
            owner=f"{actor_role}-a",
        ),
        snapshot=SimpleNamespace(learning_context=learning_context),
        max_steps=4,
    )


def test_teacher_learning_status_uses_course_learning_tool():
    request = SimpleNamespace(
        question="这门课最新学习任务完成情况怎样？",
        actor_role="teacher",
        course_id="course-a",
        conversation_id="conv-a",
    )
    contract = extract_task_contract(request, capability(), {"pending_tasks": [{"task_id": "job_old"}]})
    assert contract.intent == "status"
    assert contract.task_domain == "course_learning"
    plan = compile_plan(contract)
    assert plan.steps[0].expected_tools == ["get_course_learning_progress"]
    assert all(
        "query_generation_job_status" not in step.expected_tools
        for step in plan.steps
    )

    ctx = learning_tool_context(
        actor_role="teacher",
        learning_context={
            "projection": "teacher",
            "task_summaries": [
                {
                    "task_id": "lt_loop2",
                    "title": "E2E-LOOP2-deterministic-teacher",
                    "enrolled_students": 1,
                    "started_students": 1,
                    "completed_students": 1,
                    "completion_rate": 1.0,
                    "completion_basis_counts": {"self_reported": 1},
                }
            ],
        },
    )
    result = execute_tool(plan.steps[0].expected_tools[0], {}, ctx)

    assert result["ok"] is True
    assert result["payload"]["task_summaries"][0]["title"].startswith("E2E-LOOP2-")
    assert result["payload"]["task_summaries"][0]["completion_basis_counts"] == {
        "self_reported": 1
    }
    assert [step["tool"] for step in ctx.trace["agent_steps"]] == [
        "get_course_learning_progress"
    ]


def test_student_completed_learning_never_falls_back_to_generation_job():
    request = SimpleNamespace(
        question="我刚完成了哪个学习任务？",
        actor_role="student",
        course_id="course-a",
        conversation_id="conv-a",
    )
    contract = extract_task_contract(request, capability(), {"pending_tasks": [{"task_id": "job_old"}]})
    assert contract.task_domain == "course_learning"
    assert contract.conversation_refs["generation_job_ids"] == ["job_old"]
    assert contract.conversation_refs["learning_task_ids"] == []
    plan = compile_plan(contract)
    assert plan.steps[0].expected_tools == ["get_my_learning_progress"]

    ctx = learning_tool_context(
        actor_role="student",
        learning_context={
            "projection": "student",
            "completed_tasks": [
                {
                    "task_id": "lt_loop2",
                    "title": "E2E-LOOP2-deterministic-student",
                    "status": "completed",
                    "completion_basis": "self_reported",
                }
            ],
            "pending_tasks": [],
        },
    )
    ctx.pending_tasks = [{"task_id": "job_old", "workflow_type": "report"}]
    result = execute_tool(plan.steps[0].expected_tools[0], {}, ctx)

    assert result["ok"] is True
    assert result["payload"]["completed_tasks"][0]["task_id"] == "lt_loop2"
    assert result["payload"]["completed_tasks"][0]["completion_basis"] == "self_reported"
    assert "job_old" not in str(result)
    assert [step["tool"] for step in ctx.trace["agent_steps"]] == [
        "get_my_learning_progress"
    ]


def test_current_learning_semantics_override_historical_generation_job():
    assert resolve_task_domain("我刚完成了哪个学习任务？", ["job_old"]) == "course_learning"


def test_public_tool_schemas_are_role_scoped_and_hide_legacy_status_tool():
    student_tools = {
        schema["function"]["name"]
        for schema in build_tool_schemas(capability(), actor_role="student")
    }
    teacher_tools = {
        schema["function"]["name"]
        for schema in build_tool_schemas(capability(), actor_role="teacher")
    }

    assert "get_my_learning_progress" in student_tools
    assert "get_course_learning_progress" not in student_tools
    assert "get_course_learning_progress" in teacher_tools
    assert "get_my_learning_progress" not in teacher_tools
    assert "query_generation_job_status" in student_tools | teacher_tools
    assert "query_task_status" not in student_tools | teacher_tools


def test_page_learning_task_context_outranks_historical_generation_job():
    request = SimpleNamespace(
        question="做到哪了？",
        actor_role="student",
        course_id="course-a",
        conversation_id="conv-a",
    )
    snapshot = SimpleNamespace(
        learning_context={"pending_tasks": [{"task_id": "lt_page"}]},
        active_context={},
        active_task=None,
        workflow_state=None,
        referenced_artifact_ids=[],
    )

    contract = extract_task_contract(
        request,
        capability(),
        {"pending_tasks": [{"task_id": "job_old"}]},
        snapshot=snapshot,
    )

    assert contract.task_domain == "course_learning"
    assert contract.conversation_refs["page_learning_task_ids"] == ["lt_page"]
    assert contract.conversation_refs["generation_job_ids"] == ["job_old"]


def test_page_generation_job_context_outranks_historical_learning_task():
    request = SimpleNamespace(
        question="做到哪了？",
        actor_role="teacher",
        course_id="course-a",
        conversation_id="conv-a",
    )
    snapshot = SimpleNamespace(
        learning_context={},
        active_context={"task_id": "job_page"},
        active_task=None,
        workflow_state=None,
        referenced_artifact_ids=[],
    )

    contract = extract_task_contract(
        request,
        capability(),
        {"pending_tasks": [{"task_id": "lt_old"}]},
        snapshot=snapshot,
    )

    assert contract.task_domain == "generation_job"
    assert contract.conversation_refs["page_generation_job_ids"] == ["job_page"]
    assert contract.conversation_refs["learning_task_ids"] == ["lt_old"]


def test_current_learning_semantics_outrank_page_generation_context():
    request = SimpleNamespace(
        question="学习任务完成情况怎样？",
        actor_role="student",
        course_id="course-a",
        conversation_id="conv-a",
    )
    snapshot = SimpleNamespace(
        learning_context={},
        active_context={"task_id": "job_page"},
        active_task=None,
        workflow_state=None,
        referenced_artifact_ids=[],
    )

    contract = extract_task_contract(request, capability(), {}, snapshot=snapshot)

    assert contract.task_domain == "course_learning"


def test_legacy_generation_job_id_is_compatible_but_legacy_learning_prefix_is_not():
    request = SimpleNamespace(
        question="做到哪了？",
        actor_role="teacher",
        course_id="course-a",
        conversation_id="conv-a",
    )
    contract = extract_task_contract(
        request,
        capability(),
        {"pending_tasks": [{"task_id": "job-1"}]},
    )

    assert contract.task_domain == "generation_job"
    assert contract.conversation_refs["generation_job_ids"] == ["job-1"]
    assert resolve_task_domain("查看 lt-legacy") == "none"


def test_non_task_page_metadata_does_not_block_historical_generation_job_fallback():
    request = SimpleNamespace(
        question="做到哪了？",
        actor_role="teacher",
        course_id="course-a",
        conversation_id="conv-a",
    )
    snapshot = SimpleNamespace(
        learning_context={},
        active_context={"current_course_id": "course-a"},
        active_task="agent.completed",
        workflow_state=SimpleNamespace(workflow_id="conv-a"),
        referenced_artifact_ids=["material-a"],
    )

    contract = extract_task_contract(
        request,
        capability(),
        {"pending_tasks": [{"task_id": "job-1"}]},
        snapshot=snapshot,
    )

    assert contract.task_domain == "generation_job"
    assert contract.conversation_refs["page_generation_job_ids"] == []


def test_conflicting_ids_within_any_precedence_layer_require_clarification():
    assert resolve_task_domain("查看 lt_current 和 job_current") == "none"
    assert resolve_task_domain(
        "做到哪了？",
        page_task_ids=["lt_page", "job_page"],
    ) == "none"
    assert resolve_task_domain("做到哪了？", ["lt_old", "job-old"]) == "none"
