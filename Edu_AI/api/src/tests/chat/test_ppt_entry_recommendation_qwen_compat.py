from app.chat.application.ppt_entry_recommendation_generator import PptEntryRecommendationGenerator


class StubQwenJsonPptRecommendationLlm:
    model = "qwen3.5-plus"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, payload: str):
        self.payload = payload
        self.structured_calls = 0

    def with_structured_output(self, *_args, **_kwargs):
        self.structured_calls += 1
        raise AssertionError("qwen-compatible llm should not use function_calling structured output")

    def invoke(self, _prompt: str):
        return type("RawResponse", (), {"content": self.payload})()


def test_ppt_entry_recommendation_generator_uses_raw_json_directly_for_qwen_compatible_models():
    generator = PptEntryRecommendationGenerator(
        llm=StubQwenJsonPptRecommendationLlm(
            """```json
{
  "cards": [
    {
      "recommendation_type": "comparison_view",
      "title": "Compare topics",
      "description": "Compare the source materials.",
      "objective_hint": "帮助学生比较关键概念",
      "length_option": "long",
      "fit_score": "high",
      "prefill_config": {
        "deck_title": "Python 变量定义",
        "audience": "编程初学者",
        "objective": "帮助学生比较关键概念",
        "theme_id": "heu_academic_basic",
        "length_option": "long",
        "target_slide_count": 24,
        "key_points": ["赋值即定义", "命名规则"],
        "style_hint": "concise"
      }
    }
  ]
}
```"""
        )
    )

    result = generator.generate_recommendations(
        documents=[{"title": "Python 变量定义", "summary": "赋值、命名规则与常见错误"}],
        recommendation_types=["comparison_view"],
    )

    assert generator.llm.structured_calls == 0
    assert generator.last_generation_mode == "llm_raw_json"
    assert result[0]["recommendation_type"] == "comparison_view"
    assert result[0]["prefill_config"]["deck_title"] == "Python 变量定义 PPT"
