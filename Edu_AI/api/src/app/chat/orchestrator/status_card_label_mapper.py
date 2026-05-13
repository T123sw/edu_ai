from __future__ import annotations


class StatusCardLabelMapper:
    _WORKFLOW_LABELS = {
        "report": "报告",
        "ppt": "PPT",
        "ppt_deck": "PPT 文件",
        "ppt_content_markdown": "PPT 协议稿",
        "lesson_plan": "教案",
        "quiz": "练习",
        "ppt_outline": "PPT 大纲",
        "flashcard": "闪卡",
    }

    _WORKFLOW_GOALS = {
        "report": "生成报告",
        "ppt": "生成 PPT",
        "lesson_plan": "整理教案",
        "quiz": "生成练习",
        "ppt_outline": "整理 PPT 大纲",
        "flashcard": "生成闪卡",
    }

    def map_workflow_label(self, workflow_type: str | None) -> str | None:
        if not workflow_type:
            return None
        return self._WORKFLOW_LABELS.get(workflow_type, workflow_type)

    def map_workflow_goal(self, workflow_type: str | None) -> str | None:
        if not workflow_type:
            return None
        return self._WORKFLOW_GOALS.get(workflow_type)

    def map_status(self, *, workflow_type: str | None, status: str | None, phase: str | None, required_slots: list[str] | None) -> str:
        required_slots = list(required_slots or [])
        if not workflow_type or not status:
            return "普通对话"
        if status == "awaiting_confirm" and workflow_type == "report":
            return "等待你确认报告大纲"
        if status == "awaiting_confirm" and workflow_type == "ppt" and str(phase or "").strip() == "awaiting_outline_confirmation":
            return "等待你确认 PPT 大纲"
        if status == "awaiting_confirm" and workflow_type == "ppt":
            return "等待你补充 PPT 信息"
        if status == "awaiting_confirm":
            return "等待你确认并继续"
        if status == "running":
            label = self.map_workflow_label(workflow_type) or workflow_type
            if workflow_type == "lesson_plan":
                return f"正在整理{label}"
            return f"正在生成{label}"
        if status == "completed":
            return "当前流程已完成"
        if status == "interrupted":
            return "当前流程已中断"
        if status == "failed":
            return "当前流程执行失败"
        if required_slots:
            return "等待你补充信息"
        return "普通对话"

    def map_waiting_label(self, *, workflow_type: str | None, status: str | None, phase: str | None, required_slots: list[str] | None) -> str | None:
        required_slots = list(required_slots or [])
        if status == "awaiting_confirm" and workflow_type == "report":
            return "等待你确认报告大纲"
        if status == "awaiting_confirm" and workflow_type == "ppt" and str(phase or "").strip() == "awaiting_outline_confirmation":
            return "等待你确认 PPT 大纲"
        if status == "awaiting_confirm" and workflow_type == "ppt":
            return "等待你补充 PPT 关键信息"
        if status == "awaiting_confirm":
            return "等待你确认并继续"
        if "audience" in required_slots:
            return "等待你补充面向对象"
        if "source_docs" in required_slots:
            return "等待你选择资料"
        return None

    def map_suggested_actions(self, *, workflow_type: str | None, status: str | None, required_slots: list[str] | None) -> list[str]:
        required_slots = list(required_slots or [])
        if status == "awaiting_confirm":
            if workflow_type == "ppt":
                return ["确认并生成", "调整要求"]
            return ["确认并继续", "调整要求"]
        if "source_docs" in required_slots:
            return ["选择资料", "跳过资料直接生成"]
        if status == "running" and workflow_type:
            return ["继续生成"]
        if workflow_type == "ppt":
            return ["继续补充", "生成 PPT"]
        return ["继续提问", "生成报告"]
