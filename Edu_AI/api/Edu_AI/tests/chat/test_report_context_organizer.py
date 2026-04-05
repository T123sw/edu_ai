from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer


def test_report_context_organizer_creates_subject_focus_and_summary_from_generation_context():
    context = GenerationContext(
        conversation_id="conv-1",
        resource_type="report",
        summary_text="当前围绕关羽北伐失败原因展开分析，重点涉及军资供应与内部失和。",
        current_topics=["关羽北伐失败原因"],
        user_goals=["生成报告"],
        confirmed_facts=["军资问题与内部失和相互影响"],
        constraints={"audience": "教研组"},
        teaching_issues=["军资供应如何引发内部失和"],
        student_signals=[],
        evidence_points=[{"type": "observation", "content": "军资短缺导致军心波动"}],
        recent_relevant_messages=[{"role": "user", "content": "请基于前面的分析生成一份报告"}],
        source_scope={"from_summary": True, "from_memory": True},
    )

    result = ReportContextOrganizer().organize(
        context=context,
        request_question="请基于当前内容生成一份报告",
    )

    assert result.report_intent == "generate_report"
    assert result.report_subject == "关羽北伐失败原因"
    assert result.report_focus == "军资供应如何引发内部失和"
    assert result.key_points
    assert result.report_context_summary.subject_summary


def test_report_context_organizer_falls_back_to_comprehensive_focus_when_subject_exists():
    context = GenerationContext(
        conversation_id="conv-2",
        resource_type="report",
        summary_text="当前围绕 Skills 与 MCP 的差异继续讨论。",
        current_topics=["Skills 与 MCP 的差异"],
        user_goals=["生成报告"],
        confirmed_facts=["Skills 更偏内置能力，MCP 更偏开放协议"],
        constraints={},
        teaching_issues=[],
        student_signals=[],
        evidence_points=[
            {"type": "observation", "content": "Skills 更偏内置能力"},
            {"type": "observation", "content": "MCP 更偏开放协议"},
        ],
        recent_relevant_messages=[{"role": "user", "content": "基于这些内容生成一份报告"}],
        source_scope={"from_summary": True, "from_memory": True},
    )

    result = ReportContextOrganizer().organize(
        context=context,
        request_question="基于这些内容生成一份报告",
    )

    assert result.report_subject == "Skills 与 MCP 的差异"
    assert result.report_focus == "综合分析Skills 与 MCP 的差异下的主要问题与结论"
    assert result.missing_critical_fields == []
