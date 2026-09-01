from app.chat.runtime.tool_policy import choose_retrieval_tools


def test_selected_course_evidence_is_prioritized_before_explicit_web():
    decision = choose_retrieval_tools(
        enabled_tools={"rag_search": True, "web_search": True},
        expected_tools={"rag_search", "web_search"},
        source_mode="selected_documents",
        already_executed=set(),
        failed_tools=set(),
        remaining_budget=4,
        supplemental=False,
    )

    assert decision.selected_tools == ["rag_search", "web_search"]
    assert decision.estimated_cost_units == 4
    assert decision.candidates[0].quality_priority > decision.candidates[1].quality_priority


def test_completed_tool_is_skipped_when_it_has_no_new_evidence_query():
    decision = choose_retrieval_tools(
        enabled_tools={"rag_search": True, "web_search": True},
        expected_tools={"rag_search", "web_search"},
        source_mode="course_auto",
        already_executed={"rag_search"},
        failed_tools=set(),
        remaining_budget=3,
        supplemental=False,
    )

    assert decision.selected_tools == ["web_search"]
    assert decision.skipped_tools["rag_search"] == "evidence_already_present"


def test_supplemental_query_can_reuse_read_only_tool_within_budget():
    decision = choose_retrieval_tools(
        enabled_tools={"rag_search": True, "web_search": False},
        expected_tools={"rag_search"},
        source_mode="course_auto",
        already_executed={"rag_search"},
        failed_tools=set(),
        remaining_budget=1,
        supplemental=True,
    )

    assert decision.selected_tools == ["rag_search"]


def test_budget_selects_highest_quality_required_source_and_records_skip():
    decision = choose_retrieval_tools(
        enabled_tools={"rag_search": True, "web_search": True},
        expected_tools={"rag_search", "web_search"},
        source_mode="course_auto",
        already_executed=set(),
        failed_tools=set(),
        remaining_budget=1,
        supplemental=False,
    )

    assert decision.selected_tools == ["rag_search"]
    assert decision.skipped_tools["web_search"] == "tool_budget_exhausted"


def test_failed_optional_source_is_not_repeated_without_recovery_gain():
    decision = choose_retrieval_tools(
        enabled_tools={"rag_search": True, "web_search": True},
        expected_tools={"rag_search"},
        source_mode="course_auto",
        already_executed=set(),
        failed_tools={"web_search"},
        remaining_budget=3,
        supplemental=False,
    )

    assert decision.selected_tools == ["rag_search"]
    assert decision.skipped_tools["web_search"] == "not_required_by_current_step"
