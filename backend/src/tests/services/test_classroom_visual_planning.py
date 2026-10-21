from app.services.platform_task_handlers import _classroom_requirement


def test_video_brief_has_no_platform_story_or_visual_plan():
    result = _classroom_requirement({'requirement': '讲解截距，配图由制作工作流选择'})
    assert '讲解截距，配图由制作工作流选择' in result
    assert 'scene_count' not in result
    assert 'duration_minutes' not in result
    assert 'teaching_style' not in result
