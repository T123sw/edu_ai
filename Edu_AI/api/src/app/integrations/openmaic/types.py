"""OpenMaicClient 类型 stub —— 只建"够用"的类型，不重定义 DSL 字段语义。

见 docs/spec/SPEC-07 §2。`stage`/`scenes` 在 `JobEnvelope.result` 里保持
原样 dict 透传，不拆成 Pydantic 字段，避免跟上游 DSL 契约漂移（SPEC-02）。
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class JobEnvelope(TypedDict):
    """`generate-classroom` 提交 / 轮询的统一信封（SPEC-04 §1、SPEC-05）。"""

    jobId: str
    status: str
    step: str
    progress: NotRequired[int]
    message: str
    pollUrl: str
    pollIntervalMs: int
    scenesGenerated: NotRequired[int]
    totalScenes: NotRequired[int]
    result: NotRequired[dict[str, Any]]
    """完成时含 GenerateClassroomResult：{id,url,stage,scenes,scenesCount,createdAt}。"""
    error: NotRequired[str]
    done: NotRequired[bool]
