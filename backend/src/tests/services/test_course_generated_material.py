from __future__ import annotations

from app.services.course_generated_material import generate_reviewed_supplement
from app.services.course_knowledge_artifacts import validate_requested_artifacts


def test_model_supplement_is_chinese_long_structured_and_independently_reviewed():
    content = (
        "# 条件判断学习材料\n\n"
        "## 概念说明\n" + "条件判断用于根据布尔条件选择执行路径。" * 45 +
        "\n\n## 示例\n```python\nif score >= 60:\n    print('通过')\n```\n" +
        "\n## 常见错误\n" + "注意缩进、条件边界和分支覆盖。" * 35 +
        "\n\n## 练习与小结\n" + "请分别设计互斥分支和嵌套分支，并解释执行结果。" * 25
    )
    prompts = []

    def call_model(prompt: str) -> str:
        prompts.append(prompt)
        if "质量审查员" in prompt:
            return '{"score": 92, "approved": true, "issues": ["可进一步增加一个边界案例"]}'
        return content

    result = generate_reviewed_supplement(
        course_title="Python 控制流程入门",
        leaf_title="条件判断",
        sequence=1,
        call_model=call_model,
    )

    assert result.review_score == 92
    assert result.approved is True
    assert result.issues == ("可进一步增加一个边界案例",)
    assert result.content.startswith("# 条件判断学习材料")
    assert len(result.content) >= 800
    assert result.audit["generation_attempts"] == 1
    assert len(prompts) == 2


def test_additional_requirements_do_not_change_the_leaf_title_contract():
    content = (
        "# Linux cgroups学习材料\n\n## 概念说明\n" + "cgroups 用于资源控制。" * 80
        + "\n\n## 示例与步骤\n" + "设置 CPU 和内存限制并验证结果。" * 70
        + "\n\n## 常见错误\n" + "检查控制器是否启用。" * 60
    )
    prompts = []

    def call_model(prompt: str) -> str:
        prompts.append(prompt)
        if "质量审查员" in prompt:
            return '{"score": 90, "approved": true, "issues": []}'
        return content

    result = generate_reviewed_supplement(
        course_title="操作系统",
        leaf_title="Linux cgroups",
        sequence=1,
        call_model=call_model,
        additional_requirements="包含 Docker 案例和三道练习",
    )

    assert result.approved is True
    assert "教师补充要求：包含 Docker 案例和三道练习" in prompts[0]
    assert "Linux cgroups；本次补充要求" not in prompts[0]


def test_failed_review_feedback_is_injected_into_the_single_regeneration():
    content = (
        "# 循环控制学习材料\n\n## 概念说明\n" + "循环用于按明确条件重复执行步骤。" * 60
        + "\n\n## 示例\n" + "示例逐步检查循环变量、终止条件和输出结果。" * 50
        + "\n\n## 常见错误\n" + "区分 for 遍历与 while 条件循环的终止机制。" * 50
        + "\n\n## 练习与小结\n" + "练习要求与终止条件保持一致。" * 40
    )
    generation_prompts = []
    review_count = 0

    def call_model(prompt: str) -> str:
        nonlocal review_count
        if "质量审查员" in prompt:
            review_count += 1
            if review_count == 1:
                return '{"score": 75, "approved": false, "issues": ["for 与 while 的终止机制表述混淆"]}'
            return '{"score": 90, "approved": true, "issues": []}'
        generation_prompts.append(prompt)
        return content

    result = generate_reviewed_supplement(
        course_title="Python 控制流程入门",
        leaf_title="循环控制",
        sequence=3,
        call_model=call_model,
    )

    assert result.review_score == 90
    assert len(generation_prompts) == 2
    assert "for 与 while 的终止机制表述混淆" in generation_prompts[1]


def test_transient_model_failure_is_retried(monkeypatch):
    content = (
        "# 条件判断学习材料\n\n## 概念说明\n" + "条件判断根据布尔值选择执行路径。" * 60
        + "\n\n## 示例与步骤\n" + "逐步计算条件并验证分支输出。" * 50
        + "\n\n## 常见错误\n" + "检查边界、缩进以及分支覆盖。" * 50
        + "\n\n## 练习与小结\n" + "设计互斥分支并解释结果。" * 40
    )
    calls = 0

    def flaky_model(prompt: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("provider timeout")
        if "质量审查员" in prompt:
            return '{"score": 91, "approved": true, "issues": []}'
        return content

    monkeypatch.setattr(
        "app.services.course_generated_material.time.sleep", lambda _seconds: None
    )

    result = generate_reviewed_supplement(
        course_title="Python 入门",
        leaf_title="条件判断",
        sequence=1,
        call_model=flaky_model,
    )

    assert result.approved is True
    assert calls == 3


def test_artifact_validator_ignores_empty_table_of_contents_heading():
    specification = [{
        "requirement_id": "req-case",
        "type": "worked_case",
        "count": 1,
    }]
    content = (
        "## 完整案例 1\n\n"
        "## 正文\n\n"
        "## 完整案例 1\n\n"
        "背景：一次调度任务。输入：三个进程。步骤：逐步计算等待时间。"
        "输出：平均等待时间。验证：使用时间线重新计算并得到相同结果。"
    )

    artifacts, issues = validate_requested_artifacts(
        content,
        topic_id="scheduling",
        deliverables=specification,
    )

    assert issues == []
    assert len(artifacts) == 1


def test_semaphore_generation_prompt_includes_compilable_ordering_guardrails():
    content = (
        "# 信号量 P/V 操作学习材料\n\n## 概念说明\n"
        + "P 操作等待资源，V 操作释放资源并唤醒等待者。" * 60
        + "\n\n## 示例与步骤\n" + "使用初值为零的事件信号量建立先后关系。" * 50
        + "\n\n## 常见错误\n" + "不要把互斥与事件同步混为一谈。" * 50
        + "\n\n## 练习与小结\n" + "逐步记录信号量值和阻塞队列。" * 40
    )
    prompts = []

    def call_model(prompt: str) -> str:
        prompts.append(prompt)
        if "质量审查员" in prompt:
            return '{"score": 94, "approved": true, "issues": []}'
        return content

    result = generate_reviewed_supplement(
        course_title="操作系统",
        leaf_title="信号量 P/V 操作",
        sequence=1,
        call_model=call_model,
    )

    assert result.approved is True
    assert "<semaphore.h>" in prompts[0]
    assert "初值 1 不能证明固定执行顺序" in prompts[0]
    assert "happens-before" in prompts[0]
