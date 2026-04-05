"""Test report_service module with complete flow."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.report_service import ReportService
    from app.chat.agents.universal_report_engine import SlotExtractOut, SlotFields

    # Mock LLM to return structured output
    mock_llm = Mock()

    def mock_structured_output(model, method=None):
        mock_structured = Mock()
        mock_structured.invoke = Mock(side_effect=lambda prompt: SlotExtractOut(
            report_slots=SlotFields(
                core_topic="数组" if "数组" in prompt else None,
                focus_area="背包问题中的应用" if "背包问题" in prompt else None,
            )
        ))
        return mock_structured

    mock_llm.with_structured_output = mock_structured_output
    mock_llm.invoke = Mock(return_value=Mock(content="{}"))

    service = ReportService(llm=mock_llm)
    session_id = "test_session_001"

    print("=" * 60)
    print("Test 1: Start new report generation")
    print("=" * 60)
    result = service.generate(
        session_id=session_id,
        user_input="帮我生成数组的报告",
    )
    print(f"Status: {result['status']}")
    print(f"Phase: {result['phase']}")
    print(f"Slots: {result['slots']}")
    print(f"Response: {result['response'][:100]}...")
    assert result["status"] == "awaiting_human", f"Expected awaiting_human, got {result['status']}"
    print("PASS\n")

    print("=" * 60)
    print("Test 2: User provides core_topic")
    print("=" * 60)
    result = service.continue_with_feedback(
        session_id=session_id,
        feedback="数组",
    )
    print(f"Status: {result['status']}")
    print(f"Phase: {result['phase']}")
    print(f"Slots: {result['slots']}")
    print(f"Response: {result['response'][:100]}...")
    assert result["status"] == "awaiting_human", f"Expected awaiting_human, got {result['status']}"
    assert result["slots"].get("core_topic") == "数组", "core_topic should be extracted"
    print("PASS\n")

    print("=" * 60)
    print("Test 3: User provides focus_area")
    print("=" * 60)
    result = service.continue_with_feedback(
        session_id=session_id,
        feedback="focus_area是背包问题中的应用",
    )
    print(f"Status: {result['status']}")
    print(f"Phase: {result['phase']}")
    print(f"Slots: {result['slots']}")
    print(f"Response: {result['response'][:100]}...")
    assert result["status"] == "awaiting_human", f"Expected awaiting_human, got {result['status']}"
    print("PASS\n")

    print("=" * 60)
    print("Test 4: Session state preservation")
    print("=" * 60)
    state = service.get_session_state(session_id)
    print(f"Preserved phase: {state['phase']}")
    print(f"Preserved slots: {state['slots']}")
    assert state is not None, "Session state should be preserved"
    print("PASS\n")

    print("=" * 60)
    print("Test 5: Session deletion")
    print("=" * 60)
    service.delete_session(session_id)
    state = service.get_session_state(session_id)
    assert state is None, "Session should be deleted"
    print("PASS\n")

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run()
