from __future__ import annotations

from app.services.course_knowledge_artifacts import validate_requested_artifacts
from app.services.course_generated_material import generate_reviewed_supplement


DELIVERABLES = [
    {
        "requirement_id": "req-case",
        "type": "worked_case",
        "count": 1,
        "hardness": "hard",
    },
    {
        "requirement_id": "req-exercises",
        "type": "exercise_with_solution",
        "count": 3,
        "hardness": "hard",
    },
]


def _artifact_content():
    introduction = "cgroups v2 使用统一层级控制 CPU、内存和 I/O 资源。" * 50
    case = (
        "## 完整案例 1\n\n"
        "背景：限制 Docker 容器资源。\n\n步骤：设置 --cpus 与 --memory。\n\n"
        "输入：docker run 参数。\n\n输出：容器限制值。\n\n验证：检查 cpu.max 与 memory.max。"
    )
    exercises = "\n\n".join(
        f"## 练习 {index}\n\n题目：分析限制 {index}。\n\n答案：给出配置。\n\n"
        "解析：逐步解释控制器行为。\n\n评分点：参数、结果和边界。\n\n"
        "难度：应用。\n\n学习目标：能够配置并验证资源限制。"
        for index in range(1, 4)
    )
    return (
        "# Linux cgroups 与容器资源隔离学习材料\n\n"
        f"## 概念说明\n\n{introduction}\n\n{case}\n\n{exercises}\n\n"
        "## 常见错误与小结\n\n不要混淆权重和硬限制。"
    )


def test_artifact_validator_counts_only_complete_schema_records():
    artifacts, issues = validate_requested_artifacts(
        _artifact_content(), topic_id="cgroups", deliverables=DELIVERABLES
    )

    assert issues == []
    assert [item["type"] for item in artifacts].count("worked_case") == 1
    assert [item["type"] for item in artifacts].count("exercise_with_solution") == 3
    assert all(item["validation_status"] == "passed" for item in artifacts)
    assert len({item["artifact_id"] for item in artifacts}) == 4


def test_reviewed_supplement_persists_validated_artifact_records():
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        if "质量审查员" in prompt:
            return '{"score": 94, "approved": true, "issues": []}'
        return _artifact_content()

    result = generate_reviewed_supplement(
        course_title="操作系统",
        leaf_title="Linux cgroups 与容器资源隔离",
        sequence=1,
        topic_id="cgroups",
        deliverables=DELIVERABLES,
        call_model=model,
    )

    assert len(result.audit["learning_artifacts"]) == 4
    assert "严格生成 3 道练习" in prompts[0]
    assert "评分点" in prompts[0]


def test_incomplete_exercise_is_not_counted_as_teacher_deliverable():
    content = "## 练习 1\n\n题目：说明 cgroups。\n\n答案：资源控制。"
    artifacts, issues = validate_requested_artifacts(
        content,
        topic_id="cgroups",
        deliverables=[DELIVERABLES[1]],
    )

    assert artifacts == []
    assert any("数量应为 3" in issue for issue in issues)
    assert any("解析" in issue and "评分点" in issue for issue in issues)
