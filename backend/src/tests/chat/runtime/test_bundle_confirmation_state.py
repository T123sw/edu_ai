from app.chat.runtime.nodes.tools import _build_active_draft_outline


def test_bundle_outline_persists_original_resource_scope():
    outline = _build_active_draft_outline(
        payload={
            "subject": "快速排序",
            "resource_type": "lesson_plan",
            "outline_markdown": "# 教学大纲",
        },
        state={
            "current_plan": {
                "contract": {
                    "intent": "prepare_bundle",
                    "resource_types": ["lesson_plan", "quiz", "graph"],
                }
            }
        },
        task_contract=None,
        needs_visuals=False,
    )

    assert outline["origin_intent"] == "prepare_bundle"
    assert outline["resource_types"] == ["lesson_plan", "quiz", "graph"]
    assert outline["resource_type"] == "lesson_plan"
