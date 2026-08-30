from app.chat.memory.domain import MemoryCandidate
from app.chat.memory.policy import MemoryWritePolicy


def test_policy_accepts_explicit_preference_and_rejects_learning_fact() -> None:
    policy = MemoryWritePolicy(min_confidence=0.7)

    accepted = policy.evaluate(
        MemoryCandidate(
            memory_type="preference",
            content="用户偏好用生活中的例子解释概念",
            confidence=0.95,
            source_span="我喜欢用生活中的例子来理解概念",
            profile_axis="learning_style",
        )
    )
    rejected = policy.evaluate(
        MemoryCandidate(
            memory_type="profile_fact",
            content="学生已经掌握递归",
            confidence=0.99,
            source_span="我已经完全掌握递归了",
            profile_axis="strength",
        )
    )

    assert accepted.allowed is True
    assert rejected.allowed is False
    assert rejected.reason == "protected_learning_fact"


def test_policy_requires_source_and_supported_kind() -> None:
    policy = MemoryWritePolicy()

    no_source = policy.evaluate(
        MemoryCandidate(
            memory_type="preference",
            content="用户偏好简短回答",
            confidence=0.9,
            source_span="",
        )
    )
    unsupported = policy.evaluate(
        MemoryCandidate(
            memory_type="assessment_result",
            content="测评得分 100 分",
            confidence=1.0,
            source_span="我得了 100 分",
        )
    )

    assert no_source.allowed is False
    assert unsupported.allowed is False
