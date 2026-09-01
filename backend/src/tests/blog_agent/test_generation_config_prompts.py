from app.blog_agent.engine import (
    _assemble_selected_visuals,
    _executor_prompt,
    _planner_chapters_prompt,
)


def test_blog_prompts_apply_configuration_and_grounding():
    config = {
        "audience": "本科一年级",
        "tone": "popular",
        "length": "long",
        "structure": "概念—例子—总结",
        "special_requirements": "加入代码示例",
        "source_context": "课程资料：链表节点含 next 指针。",
        "source_mode": "selected_documents",
        "visual_plan": {
            "selected": [
                {
                    "slot_id": "linked-list",
                    "local_url": "/api/images/searched/linked-list.png",
                    "title": "链表图",
                    "caption": "链表节点连接",
                    "source_page": "https://example.com/source",
                    "source_type": "web",
                    "score": 1.0,
                }
            ]
        },
    }
    planner = _planner_chapters_prompt("链表", "course-1", [], config)
    executor = _executor_prompt(
        "链表",
        "实现",
        {"title": "节点", "estimated_word_count": 500},
        generation_config=config,
    )

    for prompt in (planner, executor):
        assert "本科一年级" in prompt
        assert "popular" in prompt
        assert "long" in prompt
        assert "概念—例子—总结" in prompt
        assert "加入代码示例" in prompt
        assert "链表节点含 next 指针" in prompt
        assert "{{VISUAL:linked-list}}" in prompt


def test_blog_assembler_replaces_only_locked_visual_slots():
    config = {
        "visual_plan": {
            "selected": [
                {
                    "slot_id": "linked-list",
                    "local_url": "/api/images/searched/linked-list.png",
                    "title": "链表图",
                    "caption": "链表节点连接",
                    "source_page": "https://example.com/source",
                    "source_type": "web",
                    "score": 1.0,
                }
            ]
        }
    }
    result = _assemble_selected_visuals(
        "正文\n\n{{VISUAL:linked-list}}\n\n{{VISUAL:not-locked}}",
        config,
    )
    assert "![链表节点连接](/api/images/searched/linked-list.png)" in result
    assert "{{VISUAL:" not in result
