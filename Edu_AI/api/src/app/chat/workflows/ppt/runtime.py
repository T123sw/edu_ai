"""Compatibility handoff for the retired chat-to-PPT workflow.

OpenMAIC Classroom Studio is the single supported courseware generation path.
Keeping this small runtime lets old chat intents fail closed with a useful,
stable migration message instead of importing the removed service.
"""

from __future__ import annotations


class PptWorkflowRuntime:
    def __init__(self, **_kwargs) -> None:
        pass

    def run(self, *, request, snapshot, decision) -> dict:
        del snapshot, decision
        course_id = str(getattr(request, "course_id", "") or "").strip()
        classroom_url = "#classroom-studio"
        if course_id:
            classroom_url = f"{classroom_url}?course_id={course_id}"

        return {
            "message": {
                "role": "assistant",
                "content": "旧版聊天 PPT 生成已下线，请从“AI 课堂”进入 Classroom Studio 生成同源课件并导出 PPTX。",
            },
            "conversation": {
                "conversation_id": str(getattr(request, "conversation_id", "") or ""),
            },
            "action": {"name": "generate.ppt"},
            "artifacts": [],
            "workflow": {
                "type": "ppt",
                "status": "completed",
                "phase": "classroom_handoff",
                "progress": 100,
            },
            "sources": [],
            "trace": {
                "path": "classroom_handoff",
                "classroom_url": classroom_url,
                "legacy_retired": True,
            },
        }

