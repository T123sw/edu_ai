from types import SimpleNamespace

from app.services.platform_task_handlers import _plan_classroom_visuals


def test_classroom_visual_brief_is_selected_before_sidecar_generation():
    events = []

    class Pipeline:
        def plan_with_model(self, llm, **kwargs):
            events.append(("plan", kwargs["resource_type"], kwargs["topic"]))
            return object()

        def run(self, brief, **kwargs):
            events.append(("select", kwargs["selected_document_ids"]))
            return SimpleNamespace(
                to_snapshot=lambda: {
                    "selected": [
                        {
                            "slot_id": "scene-1",
                            "local_url": "/api/images/searched/classroom.png",
                            "caption": "课堂示意图",
                        }
                    ]
                }
            )

    resolved = SimpleNamespace(
        context_text="课程证据",
        documents=(SimpleNamespace(document_id="doc-1"),),
    )
    snapshot = _plan_classroom_visuals(
        {
            "include_visuals": True,
            "topic": "链表",
            "course_id": "course-1",
        },
        resolved,
        owner="teacher-a",
        pipeline=Pipeline(),
        llm=object(),
    )

    assert events == [("plan", "classroom", "链表"), ("select", ["doc-1"])]
    assert snapshot["selected"][0]["slot_id"] == "scene-1"
