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


def test_blog_adapter_forwards_visible_config_and_grounding_to_engine(monkeypatch):
    captured = {}
    state = SimpleNamespace(
        status="completed",
        outline=[],
        pending_chapters=None,
        pending_outline=None,
        error_message=None,
    )

    def _create(**kwargs):
        captured.update(kwargs)
        return state

    monkeypatch.setattr(module, "create_task_state", _create)
    monkeypatch.setattr(module, "run_blog_task", lambda _job_id: None)
    monkeypatch.setattr(module, "load_task_state", lambda _job_id: state)

    module.BlogGenerationAdapterV2().generate(
        SimpleNamespace(
            course_id="course-1",
            topic="链表",
            audience="本科一年级",
            tone="popular",
            length="long",
            structure="概念—例子—总结",
            special_requirements="加入代码示例",
            source_context="课程资料：链表节点含 next 指针。",
            research_context="Agent evidence：尾插法会更新尾节点。",
            research_bundle_id="bundle-1",
            source_mode="selected_documents",
        ),
        job_id="job-2",
        config_snapshot_id="cfg-2",
    )

    assert captured["generation_config"] == {
        "audience": "本科一年级",
        "tone": "popular",
        "length": "long",
        "structure": "概念—例子—总结",
        "special_requirements": "加入代码示例",
        "source_context": "课程资料：链表节点含 next 指针。\n\nAgent evidence：尾插法会更新尾节点。",
        "source_mode": "selected_documents",
        "research_bundle_id": "bundle-1",
    }


def test_blog_adapter_plans_visuals_before_running_body_engine(monkeypatch):
    events = []
    captured = {}
    state = SimpleNamespace(
        status="completed",
        outline=[],
        pending_chapters=None,
        pending_outline=None,
        error_message=None,
    )

    class Pipeline:
        def plan_with_model(self, llm, **kwargs):
            events.append("plan_visuals")
            return SimpleNamespace(name="brief")

        def run(self, brief, **kwargs):
            events.append("select_visuals")
            return SimpleNamespace(
                to_snapshot=lambda: {
                    "brief": {"slots": [{"slot_id": "slot-1"}]},
                    "selected": [
                        {
                            "slot_id": "slot-1",
                            "local_url": "/api/images/searched/linked-list.png",
                            "title": "链表图",
                            "caption": "链表节点连接",
                            "source_page": "https://example.com/source",
                            "source_type": "web",
                            "score": 1.0,
                        }
                    ],
                    "candidate_count": 1,
                    "rejected_counts": {},
                }
            )

    def _create(**kwargs):
        captured.update(kwargs)
        events.append("create_body_task")
        return state

    monkeypatch.setattr(module, "create_task_state", _create)
    monkeypatch.setattr(module, "run_blog_task", lambda _job_id: events.append("run_body"))
    monkeypatch.setattr(module, "load_task_state", lambda _job_id: state)

    module.BlogGenerationAdapterV2(
        visual_pipeline=Pipeline(),
        llm=object(),
    ).generate(
        SimpleNamespace(
            course_id="course-1",
            topic="链表",
            include_visuals=True,
            source_context="next 指针",
            source_mode="selected_documents",
            selected_doc_ids=["doc-1"],
        ),
        job_id="job-visual-blog",
        config_snapshot_id="cfg-visual-blog",
    )

    assert events[:3] == ["plan_visuals", "select_visuals", "create_body_task"]
    assert captured["generation_config"]["visual_plan"]["selected"][0]["slot_id"] == "slot-1"
