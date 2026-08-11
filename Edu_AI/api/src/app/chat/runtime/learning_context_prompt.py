"""Shared rendering of trusted, role-scoped course learning facts."""

from __future__ import annotations

import json


def build_learning_context_prompt(context: dict | None) -> str:
    if not context:
        return ""
    return (
        "【当前学习状态】\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"), default=str)
        + "\n这些是当前课程、当前角色可读取的系统学习事实。"
        + "\n课程学习任务 ID 以 lt_ 标识，与后台内容生成任务完全不同。"
        + "\n回答学习进度时只能使用本段事实或课程学习只读工具；不得使用历史 job_ 任务代替。"
        + "\ncompletion_basis=self_reported 只表示学生自报，不代表测评通过或知识点已掌握。"
        + "\n测评 result=pending_review 表示仍待教师最终确认，禁止表述为已通过。"
        + "\n学生测评事实只可使用本人投影；answers_revealed=false 时不得推断或输出答案、解析或评分密钥。"
        + "\n教师测评事实是班级聚合，不得推断逐人答案；所有比例必须同时说明 numerator/denominator。"
    )
