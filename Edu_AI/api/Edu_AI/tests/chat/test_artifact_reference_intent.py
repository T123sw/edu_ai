from app.chat.application.artifact_reference_intent import classify_artifact_reference_intent


def test_classify_report_question_with_section_mention_as_ask():
    result = classify_artifact_reference_intent(
        "第二部分主要讲了什么？",
        artifact_type="report",
    )

    assert result["intent_class"] == "ask"
    assert result["requires_confirmation"] is False


def test_classify_ppt_question_with_page_mention_as_ask():
    result = classify_artifact_reference_intent(
        "第三页主要讲了什么？",
        artifact_type="ppt_deck",
    )

    assert result["intent_class"] == "ask"
    assert result["requires_confirmation"] is False


def test_classify_vague_edit_without_target_as_unclear():
    result = classify_artifact_reference_intent(
        "帮我优化一下这个报告",
        artifact_type="report",
    )

    assert result["intent_class"] == "unclear"
    assert result["requires_confirmation"] is True


def test_classify_explicit_ppt_edit_with_page_as_edit():
    result = classify_artifact_reference_intent(
        "把第3页改成流程图风格",
        artifact_type="ppt_deck",
    )

    assert result["intent_class"] == "edit"
    assert result["requires_confirmation"] is False
