from types import SimpleNamespace

from app.chat.orchestrator.artifact_intent_classifier import classify_artifact_intent


class DummyModel:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=self.response)


def _snapshot():
    return SimpleNamespace(
        active_artifact={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        recent_messages=[
            {"role": "user", "content": "把这份报告加到对话"},
            {"role": "assistant", "content": "已加入当前对话上下文"},
        ],
    )


def test_classifier_returns_edit_action_from_valid_json():
    model = DummyModel(
        response='{"action":"edit_current_artifact","confidence":"high","reason":"user asks for rewrite"}'
    )

    result = classify_artifact_intent(
        question="把第三部分扩写一下",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
    )

    assert result.action == "edit_current_artifact"
    assert result.confidence == "high"
    assert result.source == "llm_json"


def test_classifier_treats_low_confidence_as_discussion():
    model = DummyModel(response='{"action":"edit_current_artifact","confidence":"low","reason":"uncertain"}')

    result = classify_artifact_intent(
        question="再展开一点",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
    )

    assert result.action == "discuss_current_artifact"
    assert result.confidence == "low"
    assert result.source == "llm_low_confidence"


def test_classifier_treats_invalid_json_as_discussion():
    model = DummyModel(response="not-json")

    result = classify_artifact_intent(
        question="把第三部分扩写一下",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
    )

    assert result.action == "discuss_current_artifact"
    assert result.source == "fallback_invalid_json"


def test_classifier_rejects_switch_without_new_request_reference():
    model = DummyModel(response='{"action":"switch_artifact","confidence":"high","reason":"switch"}')

    result = classify_artifact_intent(
        question="改这个新的",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
        has_new_reference=False,
    )

    assert result.action == "discuss_current_artifact"
    assert result.source == "fallback_invalid_switch"
