from app.chat.domain.ppt_preparation import PptPreparationResult
from app.chat.workflows.ppt.readiness_judge import PptReadinessJudge


def test_ppt_readiness_judge_allows_outline_generation_when_summary_is_already_sufficient():
    preparation = PptPreparationResult(
        topic="网络安全入门",
        objective="讲清基础防护意识",
        key_points=["账号密码安全", "公共 Wi-Fi 风险", "社交工程识别"],
        source_basis=["conversation_summary"],
    )

    decision = PptReadinessJudge().judge(preparation, followup_rounds=0)

    assert decision["action"] == "generate_outline"
    assert decision["question"] == ""
    assert decision["missing_core_fields"] == ["audience"]
    assert any("通用学习者" in item for item in decision["assumptions"])


def test_ppt_readiness_judge_asks_followup_when_topic_is_missing():
    preparation = PptPreparationResult(
        objective="课堂讲解",
        key_points=["重点一", "重点二"],
        source_basis=["conversation_summary"],
    )

    decision = PptReadinessJudge().judge(preparation, followup_rounds=0)

    assert decision["action"] == "ask_followup"
    assert decision["missing_core_fields"][0] == "topic"
    assert "主要想讲哪个主题" in decision["question"]


def test_ppt_readiness_judge_allows_outline_generation_after_two_followup_rounds():
    preparation = PptPreparationResult(
        source_basis=["conversation_summary"],
    )

    decision = PptReadinessJudge().judge(preparation, followup_rounds=2)

    assert decision["action"] == "generate_outline"
    assert decision["question"] == ""
    assert decision["assumptions"]
    assert any("主题" in item for item in decision["assumptions"])


def test_ppt_readiness_judge_still_asks_followup_when_key_points_are_too_thin():
    preparation = PptPreparationResult(
        topic="关羽：历史地位与民间形象",
        audience="高中历史课堂",
        objective="课堂讲解",
        key_points=["关羽"],
        source_basis=["conversation_summary"],
    )

    decision = PptReadinessJudge().judge(preparation, followup_rounds=0)

    assert decision["action"] == "ask_followup"
    assert "key_points" in decision["missing_core_fields"]
    assert "重点覆盖哪 2 到 4 个部分" in decision["question"]
