"""Tests for the v2 report engine — outliner_node logic.

Replaces the old plan_validator_node tests. Tests outline generation,
confirmation, and revision flows.
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
        "report_slots": {
            "core_topic": "红黑树",
            "focus_area": "旋转操作",
            "length_requirement": "常规（3-4章）",
            "depth_level": "中等深度",
            "format_style": "结构化分块论述",
        },
        "report_outline": [],
        "report_content": "",
        "status": "executing",
        "human_feedback": "",
        "error": "",
        "replan_count": 0,
        "max_replans": 3,
        "phase": "outlining",
        "soft_confirmed": True,
        "outline_confirmed": False,
        "ask_count": {},
        "ask_limit": 2,
        "_missing_slot": "",
    }
    state.update(overrides)
    return state


SAMPLE_OUTLINE = [
    {
        "chapter_id": 1,
        "chapter_title": "红黑树问题界定",
        "chapter_goal": "明确旋转操作的研究范围",
        "sections": [
            {"section_id": "1.1", "title": "背景与问题提出"},
            {"section_id": "1.2", "title": "旋转操作切口定义"},
        ],
    },
    {
        "chapter_id": 2,
        "chapter_title": "红黑树旋转机制分析",
        "chapter_goal": "深入分析旋转的规则与复杂度",
        "sections": [
            {"section_id": "2.1", "title": "左旋与右旋规则"},
            {"section_id": "2.2", "title": "插入与删除中的旋转"},
        ],
    },
    {
        "chapter_id": 3,
        "chapter_title": "结论与工程建议",
        "chapter_goal": "总结旋转操作的实践意义",
        "sections": [
            {"section_id": "3.1", "title": "核心结论"},
            {"section_id": "3.2", "title": "工程选型建议"},
        ],
    },
]


def run() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.chat.agents.universal_report_engine import (
        outliner_node,
        _fallback_outline,
    )

    # ---------------------------------------------------------------
    # Test 1: No outline → generate new outline (no LLM → fallback)
    # ---------------------------------------------------------------
    state = _base_state(report_outline=[])
    out = outliner_node(state)
    assert out.get("status") == "awaiting_human", f"Expected awaiting_human, got {out}"
    assert out.get("report_outline"), f"Expected outline generated, got {out}"
    assert isinstance(out["report_outline"], list), f"Expected list, got {type(out['report_outline'])}"
    assert len(out["report_outline"]) >= 2, f"Expected ≥2 chapters, got {len(out['report_outline'])}"
    assert "final_response" in out and out["final_response"], f"Expected response text, got {out}"
    print("  [PASS] Test 1: no outline → generate fallback outline")

    # ---------------------------------------------------------------
    # Test 2: Existing outline + user confirms → outline_confirmed
    # ---------------------------------------------------------------
    state = _base_state(
        report_outline=SAMPLE_OUTLINE,
        human_feedback="就按这个来",
    )
    out = outliner_node(state)
    assert out.get("outline_confirmed") is True, f"Expected outline_confirmed=True, got {out}"
    assert out.get("phase") == "generating", f"Expected generating, got {out}"
    print("  [PASS] Test 2: existing outline + confirm → outline_confirmed")

    # ---------------------------------------------------------------
    # Test 3: Existing outline + non-confirm feedback → revision attempt
    # ---------------------------------------------------------------
    state = _base_state(
        report_outline=SAMPLE_OUTLINE,
        human_feedback="把第二章改成删除修复",
    )
    out = outliner_node(state)
    assert out.get("status") == "awaiting_human", f"Expected awaiting_human, got {out}"
    assert out.get("final_response"), f"Expected response text, got {out}"
    # The revision might succeed or fail (since no LLM), but should not crash
    print("  [PASS] Test 3: existing outline + modification feedback → revision attempt")

    # ---------------------------------------------------------------
    # Test 4: _fallback_outline produces valid structure
    # ---------------------------------------------------------------
    outline = _fallback_outline({"core_topic": "哈希表", "focus_area": "冲突处理"})
    assert isinstance(outline, list), f"Expected list, got {type(outline)}"
    assert len(outline) == 3, f"Expected 3 chapters, got {len(outline)}"
    for ch in outline:
        assert "chapter_id" in ch, f"Missing chapter_id: {ch}"
        assert "chapter_title" in ch, f"Missing chapter_title: {ch}"
        assert "sections" in ch, f"Missing sections: {ch}"
        assert isinstance(ch["sections"], list) and len(ch["sections"]) >= 1, f"Empty sections: {ch}"
    # Check topic and focus appear in titles
    titles = " ".join(ch["chapter_title"] for ch in outline)
    assert "哈希表" in titles, f"Expected topic in titles: {titles}"
    print("  [PASS] Test 4: _fallback_outline valid structure")

    # ---------------------------------------------------------------
    # Test 5: Outline confirm with various confirm phrases
    # ---------------------------------------------------------------
    for phrase in ["确认", "可以", "ok", "好", "继续", "开始生成"]:
        state = _base_state(
            report_outline=SAMPLE_OUTLINE,
            human_feedback=phrase,
        )
        out = outliner_node(state)
        assert out.get("outline_confirmed") is True, f"Phrase '{phrase}' did not confirm: {out}"
    print("  [PASS] Test 5: various confirm phrases all work")

    # ---------------------------------------------------------------
    # Test 6: Outline not confirmed when no feedback
    # ---------------------------------------------------------------
    state = _base_state(
        report_outline=SAMPLE_OUTLINE,
        human_feedback="",
    )
    out = outliner_node(state)
    # No feedback + existing outline → should generate new (treating as first visit)
    assert out.get("outline_confirmed") is not True, f"Should not confirm without feedback: {out}"
    print("  [PASS] Test 6: no feedback → not auto-confirmed")

    print("\nAll 6 outliner tests passed!")


if __name__ == "__main__":
    run()
