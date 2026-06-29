"""Phase 3 tests: guided execution, LLM/Vision reflectors, plan_step_update events."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.chat.runtime.react_agent import ReActAgent
from app.chat.runtime.reflection.llm_eval import (
    ContentRelevanceReflector,
    OutlineCoherenceReflector,
)
from app.chat.runtime.reflection.vision import VisionReflector


# ─── Helpers ──────────────────────────────────────────────────────────────────

class _NoopWriter:
    def __call__(self, event): pass


def _run_reflect(state: dict) -> dict:
    from app.chat.runtime.nodes.reflect import reflect_node
    with patch("app.chat.runtime.nodes.reflect.get_stream_writer", return_value=_NoopWriter()):
        return reflect_node(state)


def _make_tool_result(tool_name: str, payload: dict) -> dict:
    return {
        "tool_name": tool_name,
        "raw_result": {"ok": True, "payload": payload, "summary": "ok"},
    }


# ─── Guided step advancement ──────────────────────────────────────────────────

def test_reflect_advances_step_index_in_guided_mode():
    state = {
        "last_tool_results": [
            _make_tool_result("rag_search", {"answer": "A" * 200, "sources": []})
        ],
        "retry_counts": {},
        "plan_step_index": 0,
        "plan_mode": "guided",
        "current_plan": {
            "steps": [
                {"index": 0, "user_title": "检索资料", "internal_action": "retrieve_context",
                 "expected_tools": ["rag_search"], "constraints": {}, "status": "pending"},
                {"index": 1, "user_title": "生成报告", "internal_action": "generate_resource",
                 "expected_tools": ["generate_report"], "constraints": {}, "status": "pending"},
            ],
            "global_constraints": {"max_retries_per_step": 2, "max_total_reflect_retries": 4},
        },
    }
    result = _run_reflect(state)
    assert result["reflect_verdict"] == "pass"
    assert result["plan_step_index"] == 1  # advanced


def test_reflect_does_not_advance_step_on_retry():
    state = {
        "last_tool_results": [
            _make_tool_result("rag_search", {"answer": "", "sources": []})
        ],
        "retry_counts": {},
        "plan_step_index": 0,
        "plan_mode": "guided",
        "current_plan": {
            "steps": [{"index": 0, "user_title": "检索", "internal_action": "retrieve_context",
                        "expected_tools": ["rag_search"], "constraints": {}, "status": "pending"}],
            "global_constraints": {"max_retries_per_step": 2, "max_total_reflect_retries": 4},
        },
    }
    result = _run_reflect(state)
    assert result["reflect_verdict"] == "retry"
    assert result.get("plan_step_index") is None  # NOT advanced


def test_reflect_does_not_advance_in_display_only_mode():
    state = {
        "last_tool_results": [
            _make_tool_result("rag_search", {"answer": "A" * 200, "sources": []})
        ],
        "retry_counts": {},
        "plan_step_index": 0,
        "plan_mode": "display_only",
        "current_plan": {
            "steps": [{"index": 0, "user_title": "检索", "internal_action": "retrieve_context",
                        "expected_tools": ["rag_search"], "constraints": {}, "status": "pending"}],
            "global_constraints": {},
        },
    }
    result = _run_reflect(state)
    assert result["reflect_verdict"] == "pass"
    assert result.get("plan_step_index") is None  # not in display_only mode


def test_reflect_marks_step_done_in_current_plan():
    state = {
        "last_tool_results": [
            _make_tool_result("rag_search", {"answer": "A" * 200})
        ],
        "retry_counts": {},
        "plan_step_index": 0,
        "plan_mode": "guided",
        "current_plan": {
            "steps": [
                {"index": 0, "user_title": "检索", "internal_action": "retrieve_context",
                 "expected_tools": ["rag_search"], "constraints": {}, "status": "pending"}
            ],
            "global_constraints": {},
        },
    }
    result = _run_reflect(state)
    assert result["current_plan"]["steps"][0]["status"] == "done"


# ─── executor_node helpers ────────────────────────────────────────────────────

def test_inject_plan_step_hint_adds_system_note_in_guided_mode():
    from app.chat.runtime.nodes.executor import _inject_plan_step_hint

    messages = [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "帮我生成报告"},
    ]
    state = {
        "plan_mode": "guided",
        "plan_step_index": 0,
        "current_plan": {
            "steps": [
                {"index": 0, "user_title": "起草大纲", "expected_tools": ["draft_outline"],
                 "internal_action": "draft_outline", "constraints": {}, "status": "pending"}
            ]
        },
    }
    result = _inject_plan_step_hint(messages, state)
    # Should insert a system note before the last user message
    assert len(result) == 3
    assert result[-2]["role"] == "system"
    assert "起草大纲" in result[-2]["content"]
    assert result[-1]["role"] == "user"


def test_inject_plan_step_hint_skips_display_only():
    from app.chat.runtime.nodes.executor import _inject_plan_step_hint

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    state = {"plan_mode": "display_only", "plan_step_index": 0, "current_plan": {"steps": []}}
    result = _inject_plan_step_hint(messages, state)
    assert result == messages  # unchanged


# ─── Integration: plan_step_update events in full agent run ──────────────────

class _FakePlannerGateway:
    def stream_chat_with_tools(self, messages, tools, tool_choice="auto", **kw):
        yield {
            "type": "tool_calls",
            "calls": [{
                "id": "call-plan",
                "name": "create_plan",
                "args": {
                    "subject": "Python基础",
                    "resource_type": "report",
                    "steps": [
                        {"index": 0, "user_title": "起草大纲", "internal_action": "draft_outline",
                         "expected_tools": ["draft_outline"]},
                    ],
                },
            }],
        }
        yield {"type": "done"}


class _FakeExecutorGateway:
    def stream_chat_with_tools(self, messages, tools, tool_choice="auto", **kw):
        yield {"type": "text_delta", "content": "已为您生成计划。"}
        yield {"type": "done"}


class _FakeFastRuntime:
    def run_stream(self, *, request, snapshot, decision):
        yield {"type": "result", "payload": {
            "message": {"role": "assistant", "content": "fallback"},
            "conversation": {"conversation_id": request.conversation_id},
            "action": {"name": "chat.reply"},
            "workflow": None, "artifacts": [], "sources": [], "trace": {"path": "fast"},
        }}


def test_full_agent_emits_plan_step_running_in_guided_mode():
    capability = SimpleNamespace(allow_rag=False, allow_web=False)
    request = SimpleNamespace(question="帮我生成Python基础报告", conversation_id="guided-1")
    snapshot = SimpleNamespace(capability=capability, recent_messages=[], workflow_state=None)

    agent = ReActAgent(
        agent_gateway=_FakeExecutorGateway(),
        planner_gateway=_FakePlannerGateway(),
        fast_runtime=_FakeFastRuntime(),
        max_steps=4,
        timeout_seconds=5,
    )
    events = list(agent.run_stream(request=request, snapshot=snapshot))
    event_types = [e["type"] for e in events]

    assert "plan" in event_types
    assert "plan_step_update" in event_types

    running_events = [e for e in events if e["type"] == "plan_step_update" and e["payload"]["status"] == "running"]
    assert len(running_events) >= 1
    assert running_events[0]["payload"]["user_title"] == "起草大纲"


# ─── LLMReflector unit tests ──────────────────────────────────────────────────

class _FakeLLMGateway:
    def __init__(self, response: str):
        self._response = response

    def stream_chat_with_tools(self, messages, tools, tool_choice="auto", **kw):
        yield {"type": "text_delta", "content": self._response}
        yield {"type": "done"}


def test_content_relevance_reflector_skips_when_not_required():
    r = ContentRelevanceReflector(_FakeLLMGateway("不相关"))
    result = {"ok": True, "payload": {"answer": "A" * 100}}
    state = {"current_plan": {"subject": "Python"}}
    v = r.evaluate("rag_search", result, state, {})  # check_relevance not set
    assert v.verdict == "pass"  # opt-in not triggered


def test_content_relevance_reflector_retries_on_irrelevant():
    r = ContentRelevanceReflector(_FakeLLMGateway("不相关：内容与主题无关"))
    result = {"ok": True, "payload": {"answer": "A" * 100}}
    state = {"current_plan": {"subject": "Python编程"}}
    v = r.evaluate("rag_search", result, state, {"check_relevance": True})
    assert v.verdict == "retry"
    assert v.severity == "warning"


def test_content_relevance_reflector_passes_relevant():
    r = ContentRelevanceReflector(_FakeLLMGateway("相关：内容与Python编程直接匹配"))
    result = {"ok": True, "payload": {"answer": "A" * 100}}
    state = {"current_plan": {"subject": "Python编程"}}
    v = r.evaluate("rag_search", result, state, {"check_relevance": True})
    assert v.verdict == "pass"


def test_outline_coherence_reflector_passes_by_default():
    r = OutlineCoherenceReflector(_FakeLLMGateway("合格"))
    result = {"ok": True, "payload": {"outline_markdown": "## 第一章\n内容"}}
    v = r.evaluate("draft_outline", result, {}, {})  # check_coherence not set
    assert v.verdict == "pass"


def test_outline_coherence_reflector_retries_on_incoherent():
    r = OutlineCoherenceReflector(_FakeLLMGateway("不合格：结构不清晰"))
    result = {"ok": True, "payload": {"outline_markdown": "## 第一章"}}
    state = {"current_plan": {"subject": "量子计算"}}
    v = r.evaluate("draft_outline", result, state, {"check_coherence": True})
    assert v.verdict == "retry"


# ─── VisionReflector unit tests ───────────────────────────────────────────────

class _FakeVisionGateway:
    def __init__(self, response: str):
        self._response = response

    def stream_chat_with_tools(self, messages, tools, **kw):
        yield {"type": "text_delta", "content": self._response}
        yield {"type": "done"}


def test_vision_reflector_skips_when_not_required():
    r = VisionReflector(_FakeVisionGateway("不合格"))
    result = {"ok": True, "payload": {"images": ["http://img.example.com/1.jpg"]}}
    v = r.evaluate("web_search", result, {}, {})  # require_images not set
    assert v.verdict == "pass"


def test_vision_reflector_warns_on_no_images():
    r = VisionReflector(_FakeVisionGateway("合格"))
    result = {"ok": True, "payload": {"summary": "some content", "images": []}}
    v = r.evaluate("web_search", result, {}, {"require_images": True})
    assert v.verdict == "pass_with_warning"
    assert v.severity == "info"


def test_vision_reflector_passes_suitable_image():
    r = VisionReflector(_FakeVisionGateway("合格：图片与教学内容匹配"))
    result = {"ok": True, "payload": {"images": ["http://img.example.com/python.jpg"]}}
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}
    v = r.evaluate("web_search", result, state, {"require_images": True})
    assert v.verdict == "pass"
    assert "http://img.example.com/python.jpg" in v.filtered_data.get("images", [])


def test_vision_reflector_retries_unsuitable_images():
    r = VisionReflector(_FakeVisionGateway("不合格：图片模糊无关"))
    result = {"ok": True, "payload": {"images": ["http://img.example.com/bad.jpg"]}}
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}
    v = r.evaluate("web_search", result, state, {"require_images": True})
    assert v.verdict == "retry"
    assert v.severity == "blocking"


# ─── VisionReflector × image_search (list[dict] payload, Phase 6-A) ───────────


@pytest.fixture
def vlm_review_enabled(monkeypatch):
    """Enable image_search VLM review (off by default in this deployment)."""
    from core import Config
    monkeypatch.setattr(Config, "IMAGE_SEARCH_VLM_REVIEW", True, raising=False)


def _image_search_payload(*urls):
    """Build an image_search-style payload (handler returns list of full dicts)."""
    return {
        "ok": True,
        "payload": {
            "images": [
                {
                    "url": u,
                    "source_page": u + "-page",
                    "title": "img",
                    "width": 800,
                    "height": 600,
                    "thumbnail": u,
                    "license": None,
                    "proxy_url": None,
                    "provenance": {"provider": "fake", "fetched_at": "2026-06-11T00:00:00Z"},
                }
                for u in urls
            ],
        },
    }


def test_vision_reflector_applies_to_image_search_tool_name():
    r = VisionReflector(_FakeVisionGateway("合格"))
    assert r.applies_to("image_search") is True
    assert r.applies_to("web_search") is True
    assert r.applies_to("draft_outline") is False


def test_vision_reflector_handles_image_search_dict_items(vlm_review_enabled):
    r = VisionReflector(_FakeVisionGateway("合格：图片相关清晰"))
    result = _image_search_payload("https://img.example.com/python.jpg")
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass"
    filtered = v.filtered_data.get("images") or []
    # filtered_data preserves the full dict shape from upstream
    assert len(filtered) == 1
    assert isinstance(filtered[0], dict)
    assert filtered[0]["url"] == "https://img.example.com/python.jpg"
    assert filtered[0]["source_page"] == "https://img.example.com/python.jpg-page"


def test_vision_reflector_filters_image_search_dicts_partially(vlm_review_enabled):
    """When VLM rejects some images, only the good ones remain — as dicts."""
    class _SelectiveGateway:
        """Approve only URLs containing 'good'."""

        def stream_chat_with_tools(self, messages, _tools, **_kwargs):
            url = ""
            for block in messages[0]["content"]:
                if block.get("type") == "image_url":
                    url = block["image_url"]["url"]
                    break
            verdict_text = "合格" if "good" in url else "不合格"
            yield {"type": "text_delta", "content": verdict_text}
            yield {"type": "done"}

    r = VisionReflector(_SelectiveGateway())
    result = _image_search_payload(
        "https://img.example.com/good1.jpg",
        "https://img.example.com/bad1.jpg",
        "https://img.example.com/good2.jpg",
    )
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass"
    urls = [img["url"] for img in v.filtered_data.get("images") or []]
    assert sorted(urls) == [
        "https://img.example.com/good1.jpg",
        "https://img.example.com/good2.jpg",
    ]


def test_vision_reflector_retries_when_all_image_search_dicts_rejected(vlm_review_enabled):
    r = VisionReflector(_FakeVisionGateway("不合格：与主题无关"))
    result = _image_search_payload("https://img.example.com/x.jpg")
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "retry"
    assert v.severity == "blocking"
    assert "Python" in v.hint


def test_vision_reflector_rejects_when_vlm_emits_error_event(vlm_review_enabled):
    """Provider-level error (e.g. DashScope download timeout) must NOT be treated as pass."""
    class _ErrorGateway:
        def stream_chat_with_tools(self, messages, tools, **_):
            yield {"type": "error", "message": "Failed to download multimodal content"}

    r = VisionReflector(_ErrorGateway())
    result = _image_search_payload("https://geo-blocked.example.com/x.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    # All images rejected → retry blocking
    assert v.verdict == "retry"
    assert v.severity == "blocking"


def test_vision_reflector_rejects_when_vlm_returns_empty_text(vlm_review_enabled):
    """Empty / blank model response also must not be treated as pass."""
    class _EmptyGateway:
        def stream_chat_with_tools(self, messages, tools, **_):
            yield {"type": "text_delta", "content": "   "}
            yield {"type": "done"}

    r = VisionReflector(_EmptyGateway())
    result = _image_search_payload("https://example.com/x.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "retry"


def test_vision_reflector_warns_on_image_search_zero_images_does_not_retry(monkeypatch):
    """Phase 6-A.2: 0 raw candidates returns pass_with_warning (let the step
    advance). Returning 'retry' caused the LLM to spin on image_search when
    one query in a parallel batch had no results, busting the time budget."""
    from core import Config
    monkeypatch.setattr(Config, "IMAGE_SEARCH_VLM_REVIEW", True, raising=False)
    r = VisionReflector(_FakeVisionGateway("合格"))
    result = {"ok": True, "payload": {"images": []}}
    state = {"current_plan": {"subject": "RAG"}}
    v = r.evaluate("image_search", result, state, {"require_images": True})
    assert v.verdict == "pass_with_warning"
    assert v.severity == "info"


def test_vision_reflector_skips_image_search_when_vlm_disabled(monkeypatch):
    """Default deployment: VLM review of image_search is OFF (DashScope can't
    fetch external URLs). Reflector must pass immediately so heuristic-filtered
    images flow through to accumulation without slow/failing VLM calls."""
    from core import Config
    monkeypatch.setattr(Config, "IMAGE_SEARCH_VLM_REVIEW", False, raising=False)

    calls = {"n": 0}

    class _CountingGateway:
        def stream_chat_with_tools(self, *a, **k):
            calls["n"] += 1
            yield {"type": "text_delta", "content": "不合格"}
            yield {"type": "done"}

    r = VisionReflector(_CountingGateway())
    result = _image_search_payload("https://img.example.com/a.jpg", "https://img.example.com/b.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}
    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass"
    assert calls["n"] == 0  # VLM never invoked


def test_vision_reflector_runs_image_search_when_vlm_enabled(monkeypatch):
    """When explicitly enabled, VLM review still works for image_search."""
    from core import Config
    monkeypatch.setattr(Config, "IMAGE_SEARCH_VLM_REVIEW", True, raising=False)
    r = VisionReflector(_FakeVisionGateway("合格：清晰相关"))
    result = _image_search_payload("https://img.example.com/good.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}
    v = r.evaluate("image_search", result, state, {"require_images": True})
    assert v.verdict == "pass"
    assert v.filtered_data.get("images")  # VLM-approved subset present


def test_vision_reflector_rejects_ambiguous_reply_without_pass_keyword(vlm_review_enabled):
    """A reply that omits both '合格' and '不合格' is not approval."""
    class _AmbiguousGateway:
        def stream_chat_with_tools(self, messages, tools, **_):
            yield {"type": "text_delta", "content": "我无法评估这张图片"}
            yield {"type": "done"}

    r = VisionReflector(_AmbiguousGateway())
    result = _image_search_payload("https://example.com/x.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "retry"
