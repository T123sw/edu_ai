"""Compatibility handler for the retired chat PPT generator."""
from __future__ import annotations

from app.chat.runtime.agent_tools.result import ok_result


def handle_generate_ppt(name: str, args: dict, ctx) -> dict:
    topic = str(args.get("topic", "")).strip()
    if not topic:
        topic = "未命名课件"

    return ok_result(
        name,
        "旧版聊天 PPT 生成已下线，请从“AI 课堂”进入 Classroom Studio。",
        {
            "status": "classroom_handoff",
            "topic": topic,
            "classroom_url": "#classroom-studio",
        },
    )
