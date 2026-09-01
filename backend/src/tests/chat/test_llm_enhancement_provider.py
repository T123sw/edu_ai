from app.chat.orchestrator.llm_enhancement_provider import LLMEnhancementProvider


class DummyGateway:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def chat(self, messages, temperature=0.0, max_tokens=600):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.response


def test_llm_enhancement_provider_builds_candidates_from_json_response():
    gateway = DummyGateway(
        """
        {
          "summary_text": "当前围绕课堂参与度与后排学生走神问题继续分析",
          "teaching_issues": ["互动推进不足"],
          "student_signals": ["后排学生多次走神"],
          "evidence_points": [
            {
              "type": "observation",
              "content": "课堂前10分钟举手响应较少",
              "confidence": "medium"
            }
          ]
        }
        """
    )
    provider = LLMEnhancementProvider(model_gateway=gateway)

    candidates = provider(
        trigger={"event": "reply.completed", "question": "继续分析课堂问题"},
        existing_state={
            "conversation_memory": {"current_topics": ["课堂参与度"]},
        },
        rule_patch={
            "conversation_summary": {"summary_text": "当前围绕课堂参与度继续分析"},
            "conversation_memory": {"current_topics": ["课堂参与度"]},
        },
        context={
            "resource_type": "chat",
            "recent_messages": [{"role": "assistant", "content": "课堂前10分钟举手响应较少。"}],
        },
    )

    assert [candidate.field for candidate in candidates] == [
        "summary_text",
        "teaching_issues",
        "student_signals",
        "evidence_points",
    ]
    assert candidates[0].operation == "replace"
    assert candidates[1].value == ["互动推进不足"]
    assert candidates[2].value == ["后排学生多次走神"]
    assert candidates[3].value[0]["source_type"] == "llm_enhancement"
    assert candidates[3].value[0]["confidence"] == "medium"
    assert gateway.calls


def test_llm_enhancement_provider_returns_empty_candidates_on_invalid_json():
    gateway = DummyGateway("not-json")
    provider = LLMEnhancementProvider(model_gateway=gateway)

    candidates = provider(
        trigger={"event": "reply.completed", "question": "继续分析课堂问题"},
        existing_state={},
        rule_patch={},
        context={},
    )

    assert candidates == []


def test_llm_enhancement_provider_builds_semantic_candidates_for_topics_goals_and_constraints():
    gateway = DummyGateway(
        """
        {
          "current_topics": ["课堂前10分钟学生参与度下降"],
          "user_goals": ["分析问题"],
          "constraints": {
            "audience": "教研组",
            "tone": "正式",
            "extra_constraints": ["突出改进建议"]
          }
        }
        """
    )
    provider = LLMEnhancementProvider(model_gateway=gateway)

    candidates = provider(
        trigger={"event": "reply.completed", "question": "帮我看看这节课前10分钟为什么学生参与度低"},
        existing_state={},
        rule_patch={
            "conversation_summary": {"summary_text": "当前围绕课堂参与度问题继续分析"},
            "conversation_memory": {"current_topics": ["课堂参与度"]},
        },
        context={"resource_type": "chat", "recent_messages": []},
    )

    assert [candidate.field for candidate in candidates] == [
        "current_topics",
        "user_goals",
        "constraints",
    ]
    assert candidates[0].value == ["课堂前10分钟学生参与度下降"]
    assert candidates[1].value == ["分析问题"]
    assert candidates[2].value["audience"] == "教研组"
    assert candidates[2].value["extra_constraints"] == ["突出改进建议"]


def test_llm_enhancement_provider_parses_semantic_field_confidence():
    gateway = DummyGateway(
        """
        {
          "current_topics": ["课堂前10分钟学生参与度下降"],
          "current_topics_confidence": "high",
          "user_goals": ["分析问题"],
          "user_goals_confidence": "low",
          "constraints": {"audience": "教研组"},
          "constraints_confidence": "medium"
        }
        """
    )
    provider = LLMEnhancementProvider(model_gateway=gateway)

    candidates = provider(
        trigger={"event": "reply.completed", "question": "帮我看看这节课前10分钟为什么学生参与度低"},
        existing_state={},
        rule_patch={},
        context={},
    )

    assert [candidate.field for candidate in candidates] == ["current_topics", "user_goals", "constraints"]
    assert candidates[0].confidence == "high"
    assert candidates[1].confidence == "low"
    assert candidates[2].confidence == "medium"
