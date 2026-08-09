from types import SimpleNamespace

from app.chat.runtime.agent_tools.handlers.outline import handle_draft_outline


class _Gateway:
    def __init__(self):
        self.messages = []

    def chat(self, messages, **_kwargs):
        self.messages = messages
        return "# 场景一\n- 教师引导\n- 学生操作\n- 预期反馈"


def test_classroom_outline_uses_interactive_scene_contract():
    gateway = _Gateway()
    result = handle_draft_outline(
        "draft_outline",
        {
            "resource_type": "classroom",
            "subject": "链表",
            "audience": "高一学生",
            "duration_minutes": 25,
            "constraints": "{}",
        },
        SimpleNamespace(agent_gateway=gateway),
    )

    prompt = gateway.messages[0]["content"]
    assert result["ok"] is True
    assert "互动 AI 课堂" in prompt
    assert "学生操作" in prompt
    assert "高一学生" in prompt
    assert "25分钟" in prompt
