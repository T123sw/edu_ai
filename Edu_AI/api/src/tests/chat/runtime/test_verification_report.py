from app.chat.runtime.verification.plan_verifier import verify_plan_execution


def test_verifier_flags_generation_as_submitted_not_completed():
    report = verify_plan_execution(
        {
            "steps": [
                {"expected_tools": ["rag_search"], "tool_allowlist": ["rag_search"]},
                {"expected_tools": ["generate_report"], "tool_allowlist": ["generate_report"]},
                {"expected_tools": ["verify_task"], "tool_allowlist": ["verify_task"]},
            ],
        },
        {
            "agent_steps": [
                {"tool": "rag_search", "ok": True, "evidence_count": 2, "args": {"query": "快速排序"}},
                {"tool": "generate_report", "ok": True, "args": {"subject": "快速排序"}},
            ],
        },
    )

    assert report.decision == "partial"
    assert report.artifact_readable is None
    assert "任务成功且材料可读" in report.warnings[0]
    assert report.repair_directive.action == "await_artifact"


def test_verifier_rejects_out_of_allowlist_execution():
    report = verify_plan_execution(
        {"steps": [{"expected_tools": ["rag_search"], "tool_allowlist": ["rag_search"]}]},
        {"agent_steps": [{"tool": "generate_report", "ok": True, "args": {}}]},
    )

    assert report.decision == "fail"
    assert report.forbidden_tools_absent is False
    assert report.repair_directive.action == "stop"
