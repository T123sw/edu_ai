from app.chat.domain.generation_context import GenerationContext
from app.chat.workflows.report.assembler import ReportAssembler


def test_report_assembler_builds_slot_hints_and_context_digest():
    context = GenerationContext(
        conversation_id="conv-1",
        resource_type="report",
        summary_text="课堂问题集中在参与度和开场控制",
        current_topics=["课堂参与度"],
        user_goals=["生成报告"],
        confirmed_facts=["前10分钟学生分心明显"],
        constraints={"audience": "教研组", "style_notes": []},
        teaching_issues=["开场吸引力不足"],
        student_signals=["前10分钟注意力分散"],
        evidence_points=[{"type": "observation", "content": "前10分钟学生分心明显"}],
        selected_doc_ids=["doc-1"],
        referenced_artifact_ids=["artifact-1"],
        current_course_id="course-1",
        active_artifact_id="artifact-2",
        active_artifact_type="report_outline",
        recent_relevant_messages=[{"role": "user", "content": "课堂前10分钟学生容易分心"}],
        source_scope={
            "from_summary": True,
            "from_memory": True,
            "from_recent_messages": True,
            "from_docs": True,
            "from_artifacts": True,
        },
    )

    gathered = ReportAssembler().from_generation_context(context)

    assert gathered["slot_hints"]["core_topic"] == "课堂参与度"
    assert gathered["slot_hints"]["focus_area"] == "开场吸引力不足"
    assert gathered["slot_hints"]["length_requirement"] == ""
    assert "课堂问题集中在参与度和开场控制" in gathered["context_digest"]
