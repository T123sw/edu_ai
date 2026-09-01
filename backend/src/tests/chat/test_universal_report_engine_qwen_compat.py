from app.chat.agents.universal_report_engine import _assess_focus_sufficiency_llm, extractor_node


class StubQwenJsonReportLlm:
    model = "qwen3.5-plus"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, payload: str):
        self.payload = payload
        self.structured_calls = 0

    def with_structured_output(self, *_args, **_kwargs):
        self.structured_calls += 1
        raise AssertionError("qwen-compatible llm should not use function_calling structured output")

    def invoke(self, _prompt: str):
        return self.payload


def test_extractor_node_uses_raw_json_directly_for_qwen_compatible_models():
    llm = StubQwenJsonReportLlm(
        """```json
{
  "report_slots": {
    "core_topic": "Python 变量定义",
    "focus_area": "命名规则与常见错误",
    "length_requirement": "800字"
  },
  "notes": ""
}
```"""
    )

    patch = extractor_node(
        {
            "user_input": "根据以上内容生成报告",
            "human_feedback": "",
            "phase": "extracting",
            "report_slots": {},
            "gathered_context": {"slot_hints": {}, "context_digest": "围绕 Python 变量定义继续讨论"},
        },
        extractor_llm=llm,
    )

    assert llm.structured_calls == 0
    assert patch["report_slots"]["core_topic"] == "Python 变量定义"
    assert patch["report_slots"]["focus_area"] == "命名规则与常见错误"


def test_focus_assessor_uses_raw_json_directly_for_qwen_compatible_models():
    llm = StubQwenJsonReportLlm(
        """```json
{
  "is_sufficient": false,
  "reason": "focus 仍然偏泛",
  "suggested_question": "你更想聚焦命名规则、赋值语法，还是常见错误？"
}
```"""
    )

    decision = _assess_focus_sufficiency_llm(
        {"core_topic": "Python 变量定义", "focus_area": "基础内容"},
        assessor_llm=llm,
    )

    assert llm.structured_calls == 0
    assert decision["is_sufficient"] is False
    assert decision["suggested_question"] == "你更想聚焦命名规则、赋值语法，还是常见错误？"
