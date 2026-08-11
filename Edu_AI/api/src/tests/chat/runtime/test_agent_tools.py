from types import SimpleNamespace

from app.chat.runtime.agent_tools import ToolExecutionContext, build_tool_schemas, execute_tool
from app.chat.runtime.agent_tools.constants import TOOL_TO_WORKFLOW


def _tool_names(schemas):
    return [schema["function"]["name"] for schema in schemas]


def test_build_tool_schemas_filters_retrieval_tools_by_capability():
    cap = SimpleNamespace(allow_rag=True, allow_web=False)

    names = _tool_names(build_tool_schemas(cap))

    assert "rag_search" in names
    assert "web_search" not in names
    assert "draft_outline" in names
    assert "generate_report" in names
    assert "generate_ppt" in names
    assert "generate_lesson_plan" in names
    assert "generate_quiz" in names
    assert "generate_blog" in names
    assert "generate_flashcard" not in names
    assert "generate_graph" in names
    assert "generate_game" not in names
    assert "generate_classroom" in names


def test_build_tool_schemas_exposes_student_tools_only():
    cap = SimpleNamespace(allow_rag=False, allow_web=False)
    names = _tool_names(build_tool_schemas(cap, actor_role="student"))

    assert "generate_flashcard" in names
    assert "generate_game" in names
    assert "generate_classroom" in names
    assert "generate_lesson_plan" not in names
    assert "generate_blog" not in names


def test_learning_and_generation_status_schemas_are_typed_and_role_scoped():
    cap = SimpleNamespace(allow_rag=False, allow_web=False, allow_image_search=False)
    student = {
        schema["function"]["name"]: schema["function"]
        for schema in build_tool_schemas(cap, actor_role="student")
    }
    teacher = {
        schema["function"]["name"]: schema["function"]
        for schema in build_tool_schemas(cap, actor_role="teacher")
    }

    assert "get_my_learning_progress" in student
    assert "get_course_learning_progress" not in student
    assert "get_course_learning_progress" in teacher
    assert "get_my_learning_progress" not in teacher
    assert student["get_my_learning_progress"]["parameters"]["properties"]["task_id"]["pattern"] == "^lt_"
    assert teacher["get_course_learning_progress"]["parameters"]["properties"]["task_id"]["pattern"] == "^lt_"
    assert student["query_generation_job_status"]["parameters"]["properties"]["task_id"]["pattern"] == "^job_"
    assert "query_task_status" not in student | teacher


def test_tool_workflow_mapping_is_available_from_constants_module():
    assert TOOL_TO_WORKFLOW == {
        "generate_report": "report",
        "generate_ppt": "ppt",
        "generate_lesson_plan": "lesson_plan",
        "generate_quiz": "quiz",
        "generate_blog": "blog",
        "generate_flashcard": "flashcard",
        "generate_graph": "graph",
        "generate_game": "game",
        "generate_classroom": "classroom",
    }


def _generation_context(actor_role="teacher"):
    return ToolExecutionContext(
        capability=SimpleNamespace(
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
        ),
        request=SimpleNamespace(
            owner="teacher-a",
            course_id="course-1",
            conversation_id="conv-1",
            scope_type="course",
            scope_id=None,
            actor_role=actor_role,
        ),
        max_steps=4,
    )


def test_execute_tool_returns_stub_task_for_generate_quiz(monkeypatch):
    class CommandService:
        def submit(self, command):
            return SimpleNamespace(edu_job_id="job-quiz-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.quiz.generation_command_service",
        CommandService(),
    )
    ctx = _generation_context()

    result = execute_tool("generate_quiz", {"subject": "Python 基础"}, ctx)

    assert result["ok"] is True
    assert result["tool"] == "generate_quiz"
    assert result["payload"]["workflow_type"] == "quiz"
    assert result["payload"]["task_id"]  # non-empty UUID
    assert ctx.step_count == 1
    assert ctx.trace["agent_steps"][0]["tool"] == "generate_quiz"


def test_execute_tool_reuses_cached_result_for_same_call_without_incrementing_budget(
    monkeypatch,
):
    class CommandService:
        def submit(self, command):
            return SimpleNamespace(edu_job_id="job-quiz-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.quiz.generation_command_service",
        CommandService(),
    )
    ctx = _generation_context()

    first = execute_tool("generate_quiz", {"subject": "Python 基础"}, ctx)
    second = execute_tool("generate_quiz", {"subject": "Python 基础"}, ctx)

    assert second == first
    assert ctx.step_count == 1


def test_execute_tool_denies_web_search_when_capability_disallows_it():
    ctx = ToolExecutionContext(capability=SimpleNamespace(allow_rag=False, allow_web=False), max_steps=4)

    result = execute_tool("web_search", {"query": "latest AI news"}, ctx)

    assert result == {
        "ok": False,
        "tool": "web_search",
        "error": "permission_denied",
        "summary": "capability 不允许此工具",
    }


def test_execute_tool_submits_role_allowed_resource_commands(monkeypatch):
    captured = []

    class CommandService:
        def submit(self, command):
            captured.append(command)
            return SimpleNamespace(edu_job_id=f"job-{command.resource_type}-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.resource.generation_command_service",
        CommandService(),
    )
    cases = [
        ("generate_blog", {"topic": "快速排序"}, "blog", "teacher"),
        ("generate_flashcard", {"topic": "快速排序"}, "flashcard", "student"),
        ("generate_graph", {"topic": "快速排序"}, "graph", "student"),
        ("generate_game", {"topic": "快速排序"}, "game", "student"),
    ]

    for tool_name, args, resource_type, role in cases:
        result = execute_tool(tool_name, args, _generation_context(role))
        assert result["ok"] is True
        assert result["payload"]["workflow_type"] == resource_type

    assert [command.resource_type for command in captured] == [
        "blog",
        "flashcard",
        "graph",
        "game",
    ]
    assert all(command.config["entrypoint"] == "agent" for command in captured)


def test_execute_tool_rejects_role_specific_resource_mismatch():
    student_lesson = execute_tool(
        "generate_lesson_plan",
        {"subject": "快速排序", "confirmed_outline": "# 大纲"},
        _generation_context("student"),
    )
    teacher_flashcard = execute_tool(
        "generate_flashcard",
        {"topic": "快速排序"},
        _generation_context("teacher"),
    )

    assert student_lesson["error"] == "permission_denied"
    assert teacher_flashcard["error"] == "permission_denied"


def test_execute_tool_submits_ai_classroom_job(monkeypatch):
    captured = {}

    async def fake_submit(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(edu_job_id="job-classroom-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.classroom.submit_classroom_generation_job",
        fake_submit,
    )

    result = execute_tool(
        "generate_classroom",
        {"topic": "快速排序", "scene_count": 5, "enable_tts": False},
        _generation_context(),
    )

    assert result["ok"] is True
    assert result["payload"] == {
        "task_id": "job-classroom-1",
        "workflow_type": "classroom",
    }
    assert captured["topic"] == "快速排序"
    assert captured["source_mode"] == "none"
    assert captured["scene_count"] == 5
