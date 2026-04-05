from app.chat.domain.extraction_candidate import ExtractionCandidate
from app.chat.orchestrator.extraction_guard import ExtractionGuard


def test_extraction_guard_merges_allowed_llm_candidates_without_losing_rule_patch():
    guard = ExtractionGuard()
    existing_state = {
        "conversation_summary": {"summary_text": "之前在分析课堂参与度"},
        "conversation_memory": {
            "current_topics": ["课堂参与度"],
            "teaching_issues": ["互动推进不足"],
            "constraints": {
                "audience": "教研组",
                "extra_constraints": ["保留案例"],
            },
            "evidence_points": [
                {
                    "type": "observation",
                    "content": "前10分钟举手响应较少",
                    "source_type": "assistant_message",
                    "source_message_ids": ["msg-1"],
                    "confidence": "low",
                }
            ],
        },
    }
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂参与度继续分析"},
        "conversation_memory": {
            "current_topics": ["课堂参与度"],
            "teaching_issues": ["互动推进不足"],
            "constraints": {
                "audience": "教研组",
                "extra_constraints": ["保留案例"],
            },
            "evidence_points": [
                {
                    "type": "observation",
                    "content": "前10分钟举手响应较少",
                    "source_type": "assistant_message",
                    "source_message_ids": ["msg-1"],
                    "confidence": "low",
                }
            ],
        },
    }
    candidates = [
        ExtractionCandidate(
            field="summary_text",
            value="当前围绕课堂参与度与后排学生走神问题继续分析",
            source="llm",
            operation="replace",
        ),
        ExtractionCandidate(
            field="student_signals",
            value=["后排学生多次走神"],
            source="llm",
        ),
        ExtractionCandidate(
            field="constraints",
            value={"extra_constraints": ["突出改进建议"]},
            source="llm",
        ),
        ExtractionCandidate(
            field="evidence_points",
            value=[
                {
                    "type": "observation",
                    "content": "前10分钟举手响应较少",
                    "source_type": "assistant_message",
                    "source_message_ids": ["msg-2"],
                    "confidence": "medium",
                }
            ],
            source="llm",
        ),
    ]

    merged = guard.merge(
        existing_state=existing_state,
        rule_patch=rule_patch,
        candidates=candidates,
    )

    assert merged["conversation_summary"]["summary_text"] == "当前围绕课堂参与度与后排学生走神问题继续分析"
    assert merged["conversation_memory"]["student_signals"] == ["后排学生多次走神"]
    assert merged["conversation_memory"]["constraints"]["extra_constraints"] == ["突出改进建议", "保留案例"]
    evidence = merged["conversation_memory"]["evidence_points"][0]
    assert evidence["source_message_ids"] == ["msg-1", "msg-2"]
    assert evidence["confidence"] == "medium"


def test_extraction_guard_rejects_direct_llm_writes_to_protected_fields():
    guard = ExtractionGuard()
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂参与度继续分析"},
        "conversation_memory": {
            "confirmed_facts": ["前10分钟举手响应较少"],
        },
    }
    candidates = [
        ExtractionCandidate(
            field="confirmed_facts",
            value=["教师提问设计存在明显缺陷"],
            source="llm",
        ),
        ExtractionCandidate(
            field="active_context",
            value={"active_workflow_type": "report"},
            source="llm",
        ),
    ]

    merged = guard.merge(existing_state={}, rule_patch=rule_patch, candidates=candidates)

    assert merged["conversation_memory"]["confirmed_facts"] == ["前10分钟举手响应较少"]
    assert "active_context" not in merged


def test_extraction_guard_merge_with_report_describes_accepted_and_rejected_fields():
    guard = ExtractionGuard()
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂参与度继续分析"},
        "conversation_memory": {
            "current_topics": ["课堂参与度"],
            "confirmed_facts": ["前10分钟举手响应较少"],
        },
    }
    candidates = [
        ExtractionCandidate(
            field="summary_text",
            value="当前围绕课堂参与度与后排学生走神问题继续分析",
            source="llm",
            operation="replace",
        ),
        ExtractionCandidate(
            field="student_signals",
            value=["后排学生多次走神"],
            source="llm",
        ),
        ExtractionCandidate(
            field="confirmed_facts",
            value=["教师提问设计存在明显缺陷"],
            source="llm",
        ),
    ]

    merged, report = guard.merge_with_report(
        existing_state={},
        rule_patch=rule_patch,
        candidates=candidates,
    )

    assert merged["conversation_memory"]["student_signals"] == ["后排学生多次走神"]
    assert report["candidate_fields"] == ["summary_text", "student_signals", "confirmed_facts"]
    assert report["accepted_fields"] == ["summary_text", "student_signals"]
    assert report["rejected_fields"] == ["confirmed_facts"]


def test_extraction_guard_summary_candidate_does_not_mutate_fact_buckets():
    guard = ExtractionGuard()
    rule_patch = {
        "conversation_summary": {"summary_text": "当前围绕课堂参与度继续分析"},
        "conversation_memory": {
            "user_stated_facts": ["前10分钟学生多次走神"],
            "confirmed_facts": ["前10分钟学生多次走神"],
        },
    }
    candidates = [
        ExtractionCandidate(
            field="summary_text",
            value="前10分钟学生多次走神，后排回应也比较少，当前围绕课堂参与度继续分析",
            source="llm",
            operation="replace",
        )
    ]

    merged = guard.merge(existing_state={}, rule_patch=rule_patch, candidates=candidates)

    assert merged["conversation_summary"]["summary_text"].startswith("前10分钟学生多次走神")
    assert merged["conversation_memory"]["user_stated_facts"] == ["前10分钟学生多次走神"]
    assert merged["conversation_memory"]["confirmed_facts"] == ["前10分钟学生多次走神"]
