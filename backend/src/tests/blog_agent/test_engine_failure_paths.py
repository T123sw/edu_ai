from types import SimpleNamespace

import pytest

from app.blog_agent import engine
from app.blog_agent import langgraph_workflow
from app.blog_agent.models import BlogTaskState


@pytest.mark.parametrize(
    ("length", "expected"),
    [("short", (2, 2)), ("medium", (3, 3)), ("long", (5, 4))],
)
def test_blog_structure_limits_match_visible_length_option(length, expected):
    assert engine._blog_structure_limits({"length": length}) == expected


def test_blog_llm_config_prefers_runtime_provider(monkeypatch):
    monkeypatch.setattr(
        engine.runtime_config_resolver,
        "resolve",
        lambda provider: {
            "model": "working-model",
            "api_key": "working-key",
            "base_url": "https://working.example/v1",
        },
    )

    config = engine._resolve_blog_llm_config()

    assert config == {
        "model_name": "working-model",
        "api_key": "working-key",
        "api_base": "https://working.example/v1",
    }


def test_blog_llm_call_prefers_shared_runtime_client():
    class RuntimeClient:
        def invoke(self, prompt):
            assert prompt == "生成正文"
            return SimpleNamespace(content="统一模型返回")

    class RagMustNotBeCalled:
        def _call_llm(self, *_args, **_kwargs):
            raise AssertionError("raw RAG LLM path should not be used")

    result = engine._call_blog_llm(
        rag=RagMustNotBeCalled(),
        prompt="生成正文",
        model_config={},
        llm=RuntimeClient(),
    )

    assert result == "统一模型返回"


def test_chapter_planner_reports_llm_failure_without_unbound_cleaned(monkeypatch):
    state = SimpleNamespace(
        course_id="course-1",
        topic="链表",
        generation_config={},
        knowledge_graph_match={},
        status="planning",
        error_message=None,
    )

    class FailingRag:
        def _call_llm(self, *_args, **_kwargs):
            raise RuntimeError("provider unavailable")

    def run_graph(**kwargs):
        kwargs["planner_chapters_func"]({"thread_id": "job-1"})

    monkeypatch.setattr(engine, "get_rag_system", lambda: FailingRag())
    monkeypatch.setattr(engine, "load_task_state", lambda _thread_id: state)
    monkeypatch.setattr(engine, "save_task_state", lambda _state: None)
    monkeypatch.setattr(
        engine,
        "_match_knowledge_graph_subtrees",
        lambda *_args, **_kwargs: ([], []),
    )
    monkeypatch.setattr(engine, "run_blog_task_langgraph", run_graph)

    with pytest.raises(ValueError, match="provider unavailable"):
        engine.run_blog_task("job-1")

    assert state.status == "failed"
    assert "模型返回内容" in state.error_message


def test_blog_task_resumes_both_reviews_without_restarting_chapter_planning(
    monkeypatch,
):
    state = BlogTaskState(
        thread_id="job-resume",
        course_id="course-1",
        topic="链表",
        created_at="2026-08-09T00:00:00",
        updated_at="2026-08-09T00:00:00",
        status="planning",
    )
    calls: list[str] = []

    class RuntimeClient:
        def invoke(self, prompt):
            calls.append(prompt)
            if "一级目录" in prompt:
                return SimpleNamespace(
                    content='{"chapters":[{"id":"sec-1","title":"概念","estimated_word_count":300}]}'
                )
            if "二级目录" in prompt:
                return SimpleNamespace(
                    content='{"children":[{"id":"pt-1","title":"节点","key_concepts":["next"],"estimated_word_count":200}]}'
                )
            return SimpleNamespace(content="链表节点通过 next 指针连接。")

    monkeypatch.setattr(engine, "get_rag_system", lambda: object())
    monkeypatch.setattr(engine, "_resolve_blog_llm_config", lambda: {})
    monkeypatch.setattr(
        engine,
        "_match_knowledge_graph_subtrees",
        lambda *_args, **_kwargs: ([], []),
    )
    monkeypatch.setattr(engine, "load_task_state", lambda _thread_id: state)
    monkeypatch.setattr(engine, "save_task_state", lambda _state: None)
    monkeypatch.setattr(
        langgraph_workflow,
        "load_task_state",
        lambda _thread_id: state,
    )
    monkeypatch.setattr(
        engine.storage_manager,
        "save_generated_material",
        lambda **_kwargs: True,
    )

    client = RuntimeClient()
    engine.run_blog_task(state.thread_id, llm=client)
    assert state.status == "waiting_for_chapter_review"
    state.pending_chapters = list(state.outline)

    engine.run_blog_task(state.thread_id, llm=client)
    assert state.status == "waiting_for_outline_review"
    state.pending_outline = list(state.outline)

    engine.run_blog_task(state.thread_id, llm=client)
    assert state.status == "completed"
    assert "next 指针" in str(state.final_markdown)
    assert sum("一级目录" in prompt for prompt in calls) == 1
