from app.services.platform_task_handlers import _classroom_requirement


def test_classroom_requirement_applies_every_visible_generation_setting():
    result = _classroom_requirement(
        {
            "requirement": "链表课堂",
            "audience": "本科一年级",
            "objectives": ["理解节点", "实现遍历"],
            "scene_count": 8,
            "duration_minutes": 40,
            "teaching_style": "inquiry",
        }
    )

    assert "本科一年级" in result
    assert "理解节点" in result
    assert "实现遍历" in result
    assert "8" in result
    assert "40" in result
    assert "inquiry" in result
