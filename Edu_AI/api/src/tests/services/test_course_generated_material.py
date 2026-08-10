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
            return '{"score": 92, "approved": true, "issues": []}'
        return content

    result = generate_reviewed_supplement(
        course_title="Python 控制流程入门",
        leaf_title="条件判断",
        sequence=1,
        call_model=call_model,
    )

    assert result.review_score == 92
    assert result.approved is True
    assert result.content.startswith("# 条件判断学习材料")
    assert len(result.content) >= 800
    assert result.audit["generation_attempts"] == 1
    assert len(prompts) == 2
