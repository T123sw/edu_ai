"""Shared rendering of trusted, role-scoped course learning facts."""

from __future__ import annotations

import json


def build_learning_context_prompt(context: dict | None) -> str:
    if not context:
        return ""
    return (
        "【当前学习状态】\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"), default=str)
        + "\n这些是系统记录的学习事实；不得补造未提供的完成情况、成绩或掌握度。"
    )
