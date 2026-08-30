from __future__ import annotations

from app.chat.memory.domain import MemoryCandidate, MemoryPolicyDecision


ALLOWED_MEMORY_TYPES = {
    "preference",
    "profile_fact",
    "episode",
    "correction",
    "strategy_hint",
}

PROTECTED_FACT_MARKERS = (
    "完成了学习任务",
    "已完成学习任务",
    "通过这次测评",
    "通过了测评",
    "掌握递归",
    "掌握了",
    "已经掌握",
    "完全掌握",
    "已经批改",
    "批改了",
    "测评得分",
    "考试得分",
    "标准答案",
    "课程成员",
    "assessment score",
    "mastered",
    "completed the learning task",
)

NON_DURABLE_MEMORY_MARKERS = (
    "不要记住",
    "别记住",
    "不用记住",
    "只是举例",
    "只是引用",
    "不代表我的偏好",
    "不是我的偏好",
    "别因为",
    "如果有人说",
    "假设我",
    "我不喜欢",
    "我不偏好",
    "今天我",
    "今天请",
    "这一次",
    "这次先",
    "临时",
    "目前这道题",
    "现在这题",
)

EXPLICIT_PROFILE_MARKERS = (
    "我喜欢",
    "我更喜欢",
    "我偏好",
    "我习惯",
    "我希望",
    "请叫我",
    "我的名字",
    "我是",
    "请用",
    "请一直",
    "回答尽量",
    "以后",
    "改为",
    "不要直接",
    "长期习惯",
    "i prefer",
    "call me",
    "please use",
    "i am",
)


class MemoryWritePolicy:
    def __init__(self, *, min_confidence: float = 0.72):
        self.min_confidence = min_confidence

    def evaluate(self, candidate: MemoryCandidate) -> MemoryPolicyDecision:
        if candidate.memory_type not in ALLOWED_MEMORY_TYPES:
            return MemoryPolicyDecision(
                allowed=False, reason="unsupported_memory_type", candidate=candidate
            )
        if not candidate.content.strip():
            return MemoryPolicyDecision(
                allowed=False, reason="empty_content", candidate=candidate
            )
        if not candidate.source_span.strip():
            return MemoryPolicyDecision(
                allowed=False, reason="missing_source_span", candidate=candidate
            )
        protected_text = f"{candidate.content} {candidate.source_span}".lower()
        if any(marker.lower() in protected_text for marker in PROTECTED_FACT_MARKERS):
            return MemoryPolicyDecision(
                allowed=False, reason="protected_learning_fact", candidate=candidate
            )
        if any(
            marker in candidate.source_span for marker in NON_DURABLE_MEMORY_MARKERS
        ):
            return MemoryPolicyDecision(
                allowed=False, reason="non_durable_source", candidate=candidate
            )
        if candidate.confidence < self.min_confidence:
            return MemoryPolicyDecision(
                allowed=False, reason="low_confidence", candidate=candidate
            )
        if (
            candidate.memory_type in {"preference", "profile_fact", "correction"}
            and not candidate.profile_axis
        ):
            return MemoryPolicyDecision(
                allowed=False, reason="missing_profile_axis", candidate=candidate
            )
        if candidate.memory_type in {
            "preference",
            "profile_fact",
            "correction",
        } and not any(
            marker in candidate.source_span.lower()
            for marker in EXPLICIT_PROFILE_MARKERS
        ):
            return MemoryPolicyDecision(
                allowed=False,
                reason="profile_fact_not_explicit",
                candidate=candidate,
            )
        return MemoryPolicyDecision(allowed=True, reason="allowed", candidate=candidate)
