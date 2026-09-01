from __future__ import annotations

import uuid

from app.chat.runtime.agent_tools.constants import TOOL_TO_WORKFLOW
from app.chat.runtime.agent_tools.result import ok_result


def handle_generate_stub(name: str, args: dict, ctx) -> dict:
    workflow_type = TOOL_TO_WORKFLOW[name]
    task_id = f"stub-{workflow_type}-{uuid.uuid4().hex[:8]}"
    return ok_result(name, f"已提交 {workflow_type} 生成任务（stub）", {"task_id": task_id, "workflow_type": workflow_type})
