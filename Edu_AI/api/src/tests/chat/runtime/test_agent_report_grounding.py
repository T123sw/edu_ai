from types import SimpleNamespace

from app.chat.runtime.agent_tools import ToolExecutionContext, execute_tool


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        capability=SimpleNamespace(
            allow_rag=True,
            allow_web=True,
            selected_doc_ids=["doc-1"],
        ),
        request=SimpleNamespace(
            owner="teacher-a",
            course_id="course-1",
            conversation_id="conv-1",
            scope_type="course",
            scope_id=None,
        ),
        max_steps=6,
    )


def test_generate_report_carries_successful_retrieval_evidence(monkeypatch):
    captured = {}

    class CommandService:
        def submit(self, command):
            captured["command"] = command
            return SimpleNamespace(edu_job_id="job-report-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.report.generation_command_service",
        CommandService(),
    )
    ctx = _context()
    ctx.cache_result(
        "web_search",
        {"query": "快速排序"},
        {
            "ok": True,
            "tool": "web_search",
            "payload": {
                "summary": "快速排序采用分治策略。",
                "sources": [
                    {
                        "title": "Quicksort reference",
                        "url": "https://example.test/quicksort",
                        "snippet": "Partition around a pivot.",
                    }
                ],
            },
        },
    )
    ctx.cache_result(
        "rag_search",
        {"query": "快速排序"},
        {
            "ok": True,
            "tool": "rag_search",
            "payload": {
                "answer": "课程讲义强调原地分区。",
                "sources": [{"title": "算法讲义", "document_id": "doc-1"}],
            },
        },
    )

    result = execute_tool(
        "generate_report",
        {"subject": "快速排序", "confirmed_outline": "## 原理"},
        ctx,
    )

    assert result["ok"] is True
    config = captured["command"].config
    assert "快速排序采用分治策略" in config["research_context"]
    assert "课程讲义强调原地分区" in config["research_context"]
    assert config["research_sources"] == [
        {
            "tool": "web_search",
            "title": "Quicksort reference",
            "url": "https://example.test/quicksort",
            "snippet": "Partition around a pivot.",
        },
        {
            "tool": "rag_search",
            "title": "算法讲义",
            "document_id": "doc-1",
        },
    ]


def test_agent_report_adapter_merges_resolved_kb_and_retrieval_context(monkeypatch):
    from app.services.generation_task_handlers import _AgentReportGenerationAdapter

    captured = {}

    def fake_build_report_markdown(*, skill_manager, slots, outline, mode):
        captured["slots"] = slots
        return "## 报告\n正文", {"chapter_count": 1}

    monkeypatch.setattr(
        "app.chat.agents.report_generation.build_report_markdown",
        fake_build_report_markdown,
    )
    monkeypatch.setattr("app.chat.skill_manager.SkillManager", lambda: object())
    payload = SimpleNamespace(
        subject="快速排序",
        focus="",
        length_hint="",
        confirmed_outline="## 原理",
        accumulated_images=[],
        allow_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id="course-1",
        source_context="[来源: 算法讲义]\n原地分区内容。",
        research_context="[联网检索摘要]\n平均复杂度 O(n log n)。",
        research_sources=[
            {"tool": "web_search", "title": "Reference", "url": "https://example.test/q"}
        ],
    )

    result = _AgentReportGenerationAdapter().generate(
        payload,
        job_id="job-report-1",
        config_snapshot_id="cfg-1",
    )

    evidence = captured["slots"]["evidence_context"]
    assert "算法讲义" in evidence
    assert "平均复杂度" in evidence
    artifact = result["artifacts"][0]
    assert artifact["generation_state"]["grounding"] == {
        "knowledge_base_context_used": True,
        "retrieval_context_used": True,
        "research_source_count": 1,
    }
