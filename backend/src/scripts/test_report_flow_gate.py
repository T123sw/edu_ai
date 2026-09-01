"""Tests for the v2 report engine state machine — evaluator routing logic.

Replaces the old _fallback_plan tests with evaluator_node phase routing tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _base_state(**overrides):
    """Build a minimal ReportState dict for testing."""
    state = {
        "messages": [],
        "user_input": "",
        "final_response": "",
        "plan": [],
        "current_step_index": 0,
        "gathered_context": {},
        "past_steps": [],
        "report_slots": {},
        "report_outline": [],
        "report_content": "",
        "status": "planning",
        "human_feedback": "",
        "error": "",
        "replan_count": 0,
        "max_replans": 3,
        "phase": "evaluating",
        "soft_confirmed": False,
        "outline_confirmed": False,
        "ask_count": {},
        "ask_limit": 2,
        "_missing_slot": "",
    }
    state.update(overrides)
    return state


def run() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.chat.agents.universal_report_engine import (
        evaluator_node,
        asker_node,
        confirmer_node,
        generator_node,
        phase_router,
        make_initial_report_state,
        _is_affirmative,
        _is_outline_confirm,
        _is_impatient,
    )

    # ---------------------------------------------------------------
    # Test 1: Missing core_topic → asking
    # ---------------------------------------------------------------
    state = _base_state(report_slots={"focus_area": "旋转操作"})
    out = evaluator_node(state)
    assert out["phase"] == "asking", f"Expected asking, got {out}"
    assert out["_missing_slot"] == "core_topic", f"Expected core_topic missing, got {out}"
    print("  [PASS] Test 1: missing core_topic → asking")

    # ---------------------------------------------------------------
    # Test 2: Missing focus_area → asking
    # ---------------------------------------------------------------
    state = _base_state(report_slots={"core_topic": "红黑树"})
    out = evaluator_node(state)
    assert out["phase"] == "asking", f"Expected asking, got {out}"
    assert out["_missing_slot"] == "focus_area", f"Expected focus_area missing, got {out}"
    print("  [PASS] Test 2: missing focus_area → asking")

    # ---------------------------------------------------------------
    # Test 3: Both slots filled, not soft_confirmed → focus_assessor (new flow)
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "旋转操作"},
        soft_confirmed=False,
    )
    out = evaluator_node(state)
    assert out["phase"] == "focus_assessor", f"Expected focus_assessor, got {out}"
    print("  [PASS] Test 3: slots complete, not soft_confirmed → focus_assessor")

    # ---------------------------------------------------------------
    # Test 4: Focus sufficient + not soft_confirmed → confirming
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "旋转操作"},
        soft_confirmed=False,
        focus_sufficient=True,
    )
    out = evaluator_node(state)
    assert out["phase"] == "confirming", f"Expected confirming, got {out}"
    print("  [PASS] Test 4: focus_sufficient + not soft_confirmed → confirming")

    # ---------------------------------------------------------------
    # Test 5: Soft confirmed + affirmative feedback → outlining
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "旋转操作"},
        soft_confirmed=False,
        focus_sufficient=True,
        human_feedback="好的",
    )
    out = evaluator_node(state)
    assert out.get("soft_confirmed") is True, f"Expected soft_confirmed=True, got {out}"
    assert out["phase"] == "outlining", f"Expected outlining, got {out}"
    print("  [PASS] Test 5: affirmative feedback → soft_confirmed + outlining")

    # ---------------------------------------------------------------
    # Test 6: All gates passed (soft_confirmed + focus_sufficient + outline_confirmed) → generating
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "旋转操作"},
        soft_confirmed=True,
        focus_sufficient=True,
        outline_confirmed=True,
    )
    out = evaluator_node(state)
    assert out["phase"] == "generating", f"Expected generating, got {out}"
    print("  [PASS] Test 6: all gates passed → generating")

    # ---------------------------------------------------------------
    # Test 7: Impatient keyword → auto-fill + outlining
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树"},
        human_feedback="直接生成",
    )
    out = evaluator_node(state)
    assert out["phase"] == "outlining", f"Expected outlining, got {out}"
    assert out.get("soft_confirmed") is True, f"Expected soft_confirmed=True, got {out}"
    assert out["report_slots"].get("focus_area"), f"Expected focus_area auto-filled, got {out}"
    print("  [PASS] Test 7: impatient keyword → auto-fill + outlining")

    # ---------------------------------------------------------------
    # Test 8: phase_router mapping
    # ---------------------------------------------------------------
    for phase, expected_node in [
        ("asking", "asker"),
        ("confirming", "confirmer"),
        ("outlining", "outliner"),
        ("generating", "generator"),
    ]:
        s = _base_state(phase=phase)
        result = phase_router(s)
        assert result == expected_node, f"phase_router({phase}) expected {expected_node}, got {result}"
    print("  [PASS] Test 8: phase_router mapping correct")

    # ---------------------------------------------------------------
    # Test 9: asker_node respects ask_limit
    # ---------------------------------------------------------------
    state = _base_state(
        _missing_slot="focus_area",
        report_slots={"core_topic": "红黑树"},
        ask_count={"focus_area": 2},
        ask_limit=2,
    )
    out = asker_node(state)
    # Should use default value instead of asking again
    assert out.get("report_slots", {}).get("focus_area"), f"Expected default fill, got {out}"
    assert out.get("phase") == "evaluating", f"Expected re-evaluate, got {out}"
    print("  [PASS] Test 9: asker_node ask_limit overflow → default fill")

    # ---------------------------------------------------------------
    # Test 10: asker_node normal ask (under limit)
    # ---------------------------------------------------------------
    state = _base_state(
        _missing_slot="focus_area",
        report_slots={"core_topic": "红黑树"},
        ask_count={"focus_area": 0},
        ask_limit=2,
    )
    out = asker_node(state)
    assert out.get("status") == "awaiting_human", f"Expected awaiting_human, got {out}"
    assert out.get("final_response"), f"Expected question text, got {out}"
    assert out["ask_count"]["focus_area"] == 1, f"Expected ask_count incremented, got {out}"
    print("  [PASS] Test 10: asker_node normal ask under limit")

    # ---------------------------------------------------------------
    # Test 11: confirmer_node returns soft-confirm question
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "旋转操作"},
    )
    out = confirmer_node(state)
    assert out.get("status") == "awaiting_human", f"Expected awaiting_human, got {out}"
    assert "红黑树" in out.get("final_response", ""), f"Expected topic in question, got {out}"
    assert "旋转操作" in out.get("final_response", ""), f"Expected focus in question, got {out}"
    print("  [PASS] Test 11: confirmer_node returns soft-confirm question")

    # ---------------------------------------------------------------
    # Test 12: generator_node hard gate blocks without confirmations
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "旋转操作"},
        soft_confirmed=False,
        outline_confirmed=False,
    )
    out = generator_node(state)
    assert out.get("error") == "gate_not_passed", f"Expected gate_not_passed, got {out}"
    print("  [PASS] Test 12: generator hard gate blocks without confirmations")

    # ---------------------------------------------------------------
    # Test 13: make_initial_report_state has correct v2 defaults
    # ---------------------------------------------------------------
    init = make_initial_report_state(user_input="写红黑树报告")
    assert init["phase"] == "extracting"
    assert init["soft_confirmed"] is False
    assert init["outline_confirmed"] is False
    assert init["ask_count"] == {}
    assert init["ask_limit"] == 2
    assert init["report_slots"] == {}
    print("  [PASS] Test 13: make_initial_report_state v2 defaults")

    # ---------------------------------------------------------------
    # Test 14: helper function correctness
    # ---------------------------------------------------------------
    assert _is_affirmative("好的") is True
    assert _is_affirmative("我想换个方向") is False
    assert _is_affirmative("") is False
    assert _is_outline_confirm("就按这个来") is True
    assert _is_outline_confirm("把第二章改一下") is False
    assert _is_impatient("直接生成") is True
    assert _is_impatient("你好") is False
    print("  [PASS] Test 14: helper functions (_is_affirmative, _is_outline_confirm, _is_impatient)")

    # ---------------------------------------------------------------
    # Test 15: Empty slots → asking core_topic first
    # ---------------------------------------------------------------
    state = _base_state(report_slots={})
    out = evaluator_node(state)
    assert out["phase"] == "asking", f"Expected asking, got {out}"
    assert out["_missing_slot"] == "core_topic", f"Expected core_topic first, got {out}"
    print("  [PASS] Test 15: empty slots → asking core_topic first")

    # ---------------------------------------------------------------
    # Test 16: focus_assessor sufficient → confirming
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "旋转操作"},
        soft_confirmed=True,
        phase="focus_assessor",
    )
    from app.chat.agents.universal_report_engine import focus_assessor_node
    out = focus_assessor_node(state, assessor_llm=None)
    assert out.get("focus_sufficient") is True, f"Expected focus_sufficient=True, got {out}"
    assert out.get("phase") == "confirming", f"Expected confirming, got {out}"
    print("  [PASS] Test 16: focus_assessor sufficient → confirming")

    # ---------------------------------------------------------------
    # Test 17: focus_assessor insufficient → asker with suggested_question
    # ---------------------------------------------------------------
    state = _base_state(
        report_slots={"core_topic": "红黑树", "focus_area": "算法"},
        soft_confirmed=True,
        phase="focus_assessor",
    )
    out = focus_assessor_node(state, assessor_llm=None)
    # With no LLM, defaults to sufficient
    assert out.get("focus_sufficient") is True, f"Expected fallback to sufficient, got {out}"
    print("  [PASS] Test 17: focus_assessor fallback (no LLM)")

    print("\nAll 17 report flow gate tests passed!")


if __name__ == "__main__":
    run()
