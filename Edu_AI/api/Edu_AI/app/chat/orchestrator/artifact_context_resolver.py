from __future__ import annotations

from dataclasses import dataclass


EXIT_PATTERNS = (
    "不要基于这个了",
    "清除引用",
    "移除引用",
    "不看这个了",
    "我们聊别的",
    "新开话题",
)

EDIT_PATTERNS = (
    "修改",
    "重写",
    "改写",
    "扩写",
    "精简",
    "删除",
    "调整结构",
    "改标题",
    "改短",
    "合并",
    "拆分",
    "补充",
    "rewrite",
    "edit",
    "change",
    "make slide",
    "simpler",
    "shorter",
)


@dataclass(slots=True)
class ArtifactContextDecision:
    action: str
    clear_reference: bool = False


def resolve_artifact_context(*, question: str, request_reference, snapshot) -> ArtifactContextDecision:
    text = str(question or "").strip()
    has_request_reference = request_reference is not None
    has_active_artifact = bool(getattr(snapshot, "active_artifact", None)) if snapshot is not None else False

    if not has_request_reference and not has_active_artifact:
        return ArtifactContextDecision(action="no_artifact")

    if any(pattern in text for pattern in EXIT_PATTERNS):
        return ArtifactContextDecision(action="exit_artifact_context", clear_reference=True)

    if any(pattern in text for pattern in EDIT_PATTERNS):
        return ArtifactContextDecision(action="edit_current_artifact")

    return ArtifactContextDecision(action="discuss_current_artifact")
