from __future__ import annotations

from app.services.course_generated_material import generate_reviewed_supplement


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
