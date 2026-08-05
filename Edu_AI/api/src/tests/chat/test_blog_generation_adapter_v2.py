from __future__ import annotations

from types import SimpleNamespace

from app.chat.application import blog_generation_adapter_v2 as module


def test_blog_adapter_accepts_generated_reviews_and_returns_saved_resource(monkeypatch):
    state = SimpleNamespace(
        status="planning",
        outline=[],
        pending_chapters=None,
        pending_outline=None,
        error_message=None,
    )
    calls = []

    monkeypatch.setattr(module, "create_task_state", lambda **_kwargs: state)
    monkeypatch.setattr(module, "load_task_state", lambda _job_id: state)
    monkeypatch.setattr(module, "save_task_state", lambda value: calls.append(value.status))

    def _run(_job_id):
        if state.status == "planning":
            state.status = "waiting_for_chapter_review"
            state.outline = [{"title": "第一章"}]
        elif state.status == "waiting_for_chapter_review":
            assert state.pending_chapters == state.outline
            state.status = "waiting_for_outline_review"
            state.outline = [{"title": "第一章", "children": [{"title": "概念"}]}]
        else:
            assert state.pending_outline == state.outline
            state.status = "completed"

    monkeypatch.setattr(module, "run_blog_task", _run)

    result = module.BlogGenerationAdapterV2().generate(
        SimpleNamespace(course_id="course-1", topic="变量"),
        job_id="job-1",
        config_snapshot_id="cfg-1",
    )

    assert calls == ["waiting_for_chapter_review", "waiting_for_outline_review"]
    assert result["saved"] is True
    assert result["result_ref"] == {
        "resource_type": "course_material",
        "course_id": "course-1",
        "material_type": "blog",
        "material_id": "job-1",
    }
