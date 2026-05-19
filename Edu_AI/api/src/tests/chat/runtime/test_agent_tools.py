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


def test_tool_workflow_mapping_is_available_from_constants_module():
    assert TOOL_TO_WORKFLOW == {
        "generate_report": "report",
        "generate_ppt": "ppt",
        "generate_lesson_plan": "lesson_plan",
        "generate_quiz": "quiz",
    }


def test_execute_tool_returns_stub_task_for_generate_quiz():
    ctx = ToolExecutionContext(capability=SimpleNamespace(allow_rag=False, allow_web=False), max_steps=4)

    result = execute_tool("generate_quiz", {"subject": "Python 基础"}, ctx)

    assert result["ok"] is True
    assert result["tool"] == "generate_quiz"
    assert result["payload"]["workflow_type"] == "quiz"
    assert result["payload"]["task_id"].startswith("stub-quiz-")
    assert ctx.step_count == 1
    assert ctx.trace["agent_steps"][0]["tool"] == "generate_quiz"


def test_execute_tool_reuses_cached_result_for_same_call_without_incrementing_budget():
    ctx = ToolExecutionContext(capability=SimpleNamespace(allow_rag=False, allow_web=False), max_steps=4)

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
