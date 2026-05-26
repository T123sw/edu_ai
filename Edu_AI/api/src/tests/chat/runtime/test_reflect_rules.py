"""Phase 2-C: unit tests for Reflect Pipeline code rules and retry dead-loop protection."""
from app.chat.runtime.reflection.base import ReflectVerdict
from app.chat.runtime.reflection.rules import (
    ChapterCountReflector,
    LengthReflector,
    ReflectorPipeline,
    SourcesReflector,
)
from app.chat.runtime.nodes.reflect import reflect_node


# ─── LengthReflector ──────────────────────────────────────────────────────────

def test_length_reflector_blocks_empty_rag_answer():
    r = LengthReflector()
    result = {"ok": True, "payload": {"answer": ""}, "summary": ""}
    v = r.evaluate("rag_search", result, {}, {})
    assert v.verdict == "retry"
    assert v.severity == "blocking"


def test_length_reflector_passes_sufficient_content():
    r = LengthReflector()
    result = {"ok": True, "payload": {"answer": "A" * 100}, "summary": ""}
    v = r.evaluate("rag_search", result, {}, {})
    assert v.verdict == "pass"


def test_length_reflector_blocks_short_web_summary():
    r = LengthReflector()
    result = {"ok": True, "payload": {"summary": "Too short"}, "summary": ""}
    v = r.evaluate("web_search", result, {}, {"min_answer_length": 50})
    assert v.verdict == "retry"
    assert v.severity == "blocking"


def test_length_reflector_ignores_failed_tool():
    r = LengthReflector()
    result = {"ok": False, "payload": {}, "summary": ""}
    v = r.evaluate("rag_search", result, {}, {})
    assert v.verdict == "pass"


# ─── SourcesReflector ─────────────────────────────────────────────────────────

def test_sources_reflector_skips_when_not_required():
    r = SourcesReflector()
    result = {"ok": True, "payload": {"answer": "content", "sources": []}}
    v = r.evaluate("rag_search", result, {}, {})
    assert v.verdict == "pass"


def test_sources_reflector_warns_when_required_and_empty():
    r = SourcesReflector()
    result = {"ok": True, "payload": {"answer": "content", "sources": []}}
    v = r.evaluate("rag_search", result, {}, {"require_sources": True, "min_sources": 2})
    assert v.verdict == "retry"
    assert v.severity == "warning"


def test_sources_reflector_passes_with_enough_sources():
    r = SourcesReflector()
    result = {"ok": True, "payload": {"sources": ["s1", "s2", "s3"]}}
    v = r.evaluate("rag_search", result, {}, {"require_sources": True, "min_sources": 2})
    assert v.verdict == "pass"


# ─── ChapterCountReflector ────────────────────────────────────────────────────

def test_chapter_count_blocks_too_few_chapters():
    r = ChapterCountReflector()
    outline = "## 第一章\n内容\n## 第二章\n内容"  # 2 chapters
    result = {"ok": True, "payload": {"outline_markdown": outline}}
    v = r.evaluate("draft_outline", result, {}, {"min_chapters": 5})
    assert v.verdict == "retry"
    assert v.severity == "blocking"


def test_chapter_count_passes_sufficient_chapters():
    r = ChapterCountReflector()
    outline = "\n".join(f"## 第{i}章\n内容足够多" + "x" * 50 for i in range(1, 6))
    result = {"ok": True, "payload": {"outline_markdown": outline}}
    v = r.evaluate("draft_outline", result, {}, {"min_chapters": 5})
    assert v.verdict == "pass"


def test_chapter_count_blocks_too_short_outline():
    r = ChapterCountReflector()
    outline = "## 第一章\n内容\n## 第二章\n内容\n## 第三章\n内容"  # enough chapters, too short
    result = {"ok": True, "payload": {"outline_markdown": outline}}
    v = r.evaluate("draft_outline", result, {}, {"min_chapters": 3, "min_outline_length": 500})
    assert v.verdict == "retry"


# ─── ReflectorPipeline ────────────────────────────────────────────────────────

def test_pipeline_returns_pass_for_unknown_tool():
    pipeline = ReflectorPipeline.default()
    result = {"ok": True, "payload": {}}
    verdicts = pipeline.evaluate_all("unknown_tool", result, {}, {})
    assert verdicts[0].verdict == "pass"


def test_pipeline_stops_early_on_blocking():
    pipeline = ReflectorPipeline.default()
    # Empty answer → LengthReflector blocks first (priority=0), SourcesReflector should not run
    result = {"ok": True, "payload": {"answer": "", "sources": []}}
    verdicts = pipeline.evaluate_all(
        "rag_search", result, {}, {"min_answer_length": 50, "require_sources": True}
    )
    # LengthReflector blocking → only one verdict returned
    assert len(verdicts) == 1
    assert verdicts[0].verdict == "retry"
    assert verdicts[0].severity == "blocking"


# ─── reflect_node (T4 anti-deadloop) ─────────────────────────────────────────

def _make_rag_empty_result_item():
    return {
        "tool_name": "rag_search",
        "raw_result": {"ok": True, "payload": {"answer": ""}, "summary": ""},
    }


class _NoopWriter:
    def __call__(self, event): pass


def _run_reflect(state: dict) -> dict:
    """Run reflect_node with a no-op stream writer (outside LangGraph graph context)."""
    from langgraph.config import get_stream_writer
    import contextlib

    # Patch: inject a no-op writer for tests running outside graph.stream()
    from unittest.mock import patch
    with patch("app.chat.runtime.nodes.reflect.get_stream_writer", return_value=_NoopWriter()):
        return reflect_node(state)


def test_reflect_node_retry_increments_count():
    state = {
        "last_tool_results": [_make_rag_empty_result_item()],
        "retry_counts": {},
        "plan_step_index": 0,
        "current_plan": None,
    }
    result = _run_reflect(state)
    assert result["reflect_verdict"] == "retry"
    assert result["retry_counts"].get("step_0:rag_search", 0) == 1


def test_reflect_node_degrades_retry_to_pass_with_warning_at_limit():
    """T4: after max_retries_per_step=2, verdict degrades from retry to pass_with_warning."""
    state = {
        "last_tool_results": [_make_rag_empty_result_item()],
        "retry_counts": {"step_0:rag_search": 2},  # already at limit
        "plan_step_index": 0,
        "current_plan": {"global_constraints": {"max_retries_per_step": 2, "max_total_reflect_retries": 4}},
    }
    result = _run_reflect(state)
    assert result["reflect_verdict"] == "pass_with_warning"
    assert "重试上限" in result["reflect_hint"]


def test_reflect_node_clears_last_tool_results():
    state = {
        "last_tool_results": [_make_rag_empty_result_item()],
        "retry_counts": {},
        "plan_step_index": 0,
        "current_plan": None,
    }
    result = _run_reflect(state)
    assert result["last_tool_results"] == []


def test_reflect_node_pass_when_no_results():
    state = {
        "last_tool_results": [],
        "retry_counts": {},
        "plan_step_index": 0,
        "current_plan": None,
    }
    result = _run_reflect(state)
    assert result["reflect_verdict"] == "pass"
    assert result["reflect_hint"] == ""
