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


def test_report_result_step_is_terminal_and_preserves_audit_trace():
    """A completed strict plan must not return to the model for another tool call."""
    from app.chat.runtime.nodes.executor import (
        _emit_compiled_report_result,
        _is_report_result_step,
    )

    captured = []
    state = {
        "plan_mode": "strict",
        "plan_step_index": 2,
        "messages": [{"role": "user", "content": "confirm"}],
        "tool_exchange": [],
        "retrieval_sources": [{"title": "source"}],
        "pending_tasks": [{"task_id": "job-1", "workflow_type": "report"}],
        "verification_report": {"passed": True, "decision": "pass"},
        "current_plan": {"steps": [
            {"internal_action": "generate_resource", "status": "done"},
            {"internal_action": "verify", "status": "done"},
            {"internal_action": "report_result", "user_title": "report", "status": "pending"},
        ]},
    }
    ctx = SimpleNamespace(
        trace={"agent_steps": [{"tool": "generate_report", "ok": True}]},
        verification_report={"passed": True, "decision": "pass"},
    )
    rt = {"request": SimpleNamespace(conversation_id="conv-1"), "conv_id": "conv-1"}

    assert _is_report_result_step(state) is True
    updates = _emit_compiled_report_result(captured.append, state, rt, ctx)

    result = next(event["payload"] for event in captured if event["type"] == "result")
    assert result["trace"] == ctx.trace
    assert result["verification"]["passed"] is True
    assert updates["plan_step_index"] == 3
    assert updates["current_plan"]["steps"][2]["status"] == "done"


def test_bundle_terminal_message_lists_every_accepted_task():
    from app.chat.runtime.nodes.executor import _pending_task_submission_message

    message = _pending_task_submission_message([
        {"task_id": "job-lesson", "workflow_type": "lesson_plan"},
        {"task_id": "job-quiz", "workflow_type": "quiz"},
        {"task_id": "job-graph", "workflow_type": "graph"},
    ])

    assert "3 个教学材料生成任务" in message
    assert "教案（job-lesson）" in message
    assert "练习题（job-quiz）" in message
    assert "思维导图（job-graph）" in message


def test_learning_terminal_message_preserves_teacher_facts():
    from app.chat.runtime.nodes.executor import _learning_status_message

    message = _learning_status_message({"last_tool_results": [{
        "tool_name": "get_course_learning_progress",
        "raw_result": {
            "ok": True,
            "payload": {"task_summaries": [{
                "task_id": "lt-1",
                "title": "循环结构学习",
                "enrolled_students": 2,
                "started_students": 1,
                "completed_students": 1,
                "completion_rate": 0.5,
                "completion_basis_counts": {"self_reported": 1},
            }]},
        },
    }]})

    assert "循环结构学习" in message
    assert "课程学生 2 人" in message
    assert "完成率 50%" in message
    assert "学生自报完成 1 人" in message
    assert "不等于测评通过" in message


def test_learning_terminal_message_preserves_student_facts_and_next_step():
    from app.chat.runtime.nodes.executor import _learning_status_message

    message = _learning_status_message({"last_tool_results": [{
        "tool_name": "get_my_learning_progress",
        "raw_result": {
            "ok": True,
            "payload": {"completed_tasks": [{
                "task_id": "lt-2",
                "title": "变量学习",
                "completion_basis": "self_reported",
            }]},
        },
    }]})

    assert "变量学习" in message
    assert "lt-2" in message
    assert "学生自报完成" in message
    assert "下一步建议" in message


def test_learning_terminal_message_survives_reflect_state_cleanup():
    from app.chat.runtime.nodes.executor import _learning_status_message

    ctx = SimpleNamespace(last_tool_results=[{
        "tool_name": "get_my_learning_progress",
        "raw_result": {
            "ok": True,
            "payload": {"pending_tasks": [{"task_id": "lt-3", "title": "待学任务"}]},
        },
    }])

    message = _learning_status_message({"last_tool_results": []}, ctx=ctx)

    assert "待学任务" in message


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
    assert "起草" in running_events[0]["payload"]["user_title"]


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


def test_vision_reflector_warns_on_unsuitable_web_search_images():
    """web_search images all rejected → pass_with_warning (not retry).
    Phase 6-A.2 made image quality non-blocking so the run never stalls."""
    r = VisionReflector(_FakeVisionGateway("不合格：图片模糊无关"))
    result = {"ok": True, "payload": {"images": ["http://img.example.com/bad.jpg"]}}
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}
    v = r.evaluate("web_search", result, state, {"require_images": True})
    assert v.verdict == "pass_with_warning"
    assert v.severity == "info"


# ─── VisionReflector × image_search (list[dict] payload, Phase 6-A) ───────────


@pytest.fixture
def vlm_review_enabled(monkeypatch):
    """Enable image_search VLM review (Phase 6-A.2: on by default, but tests
    set it explicitly for clarity)."""
    from core import Config
    monkeypatch.setattr(Config, "IMAGE_SEARCH_VLM_REVIEW", True, raising=False)


@pytest.fixture
def mock_localize(monkeypatch, tmp_path):
    """Mock localize_image so image_search VLM tests don't hit the network.
    Each call writes a real temp file and returns a LocalizedAsset pointing
    at it (so VisionReflector can read base64)."""
    import hashlib
    from app.chat.workflows.report import image_downloader

    def _fake_localize(img, **kw):
        url = str(img.get("url") or "")
        h = hashlib.sha256(url.encode()).hexdigest()[:16]
        p = tmp_path / f"{h}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        return image_downloader.LocalizedAsset(
            local_url=f"/api/images/searched/{h}.png",
            local_path=p,
            source_url=url,
            source_page=str(img.get("source_page") or ""),
            title=str(img.get("title") or ""),
            alt=str(img.get("alt") or img.get("title") or "图片"),
            content_type="image/png",
            size_bytes=p.stat().st_size,
            hash=h,
            fetched_at="2026-06-29T00:00:00Z",
        )

    monkeypatch.setattr(
        "app.chat.workflows.report.image_downloader.localize_image",
        _fake_localize,
        raising=True,
    )
    return _fake_localize


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


def test_vision_reflector_handles_image_search_dict_items(vlm_review_enabled, mock_localize):
    r = VisionReflector(_FakeVisionGateway("合格：图片相关清晰"))
    result = _image_search_payload("https://img.example.com/python.jpg")
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass"
    filtered = v.filtered_data.get("images") or []
    assert len(filtered) == 1
    assert isinstance(filtered[0], dict)
    # Phase 6-A.2: url is now the localized path; source_url preserves origin
    assert filtered[0]["url"].startswith("/api/images/searched/")
    assert filtered[0]["source_url"] == "https://img.example.com/python.jpg"
    assert filtered[0]["_localized"] is True


def test_vision_reflector_filters_image_search_dicts_partially(vlm_review_enabled, monkeypatch, tmp_path):
    """When VLM rejects some images, only the good ones remain.
    The localize mock encodes the source URL into the file bytes so the VLM
    gateway (which now only sees base64) can still tell good from bad."""
    import base64 as _b64
    import hashlib
    from app.chat.workflows.report import image_downloader

    def _url_encoding_localize(img, **kw):
        url = str(img.get("url") or "")
        h = hashlib.sha256(url.encode()).hexdigest()[:16]
        p = tmp_path / f"{h}.png"
        p.write_bytes(url.encode("utf-8"))  # file content = source url
        return image_downloader.LocalizedAsset(
            local_url=f"/api/images/searched/{h}.png", local_path=p,
            source_url=url, source_page="", title="", alt="图片",
            content_type="image/png", size_bytes=p.stat().st_size, hash=h,
            fetched_at="t",
        )

    monkeypatch.setattr(
        "app.chat.workflows.report.image_downloader.localize_image",
        _url_encoding_localize, raising=True,
    )

    class _SelectiveGateway:
        """Approve only images whose decoded base64 content contains 'good'."""
        def stream_chat_with_tools(self, messages, _tools, **_kwargs):
            data_uri = messages[0]["content"][0]["image_url"]["url"]
            content = _b64.b64decode(data_uri.split(",", 1)[1]).decode("utf-8", "ignore")
            yield {"type": "text_delta", "content": "合格" if "good" in content else "不合格"}
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
    source_urls = sorted(img["source_url"] for img in v.filtered_data.get("images") or [])
    assert source_urls == [
        "https://img.example.com/good1.jpg",
        "https://img.example.com/good2.jpg",
    ]


def test_vision_reflector_warns_when_all_image_search_dicts_rejected(vlm_review_enabled, mock_localize):
    """All images rejected by VLM → pass_with_warning (non-blocking), the run
    still proceeds to generate the report (just without these images)."""
    r = VisionReflector(_FakeVisionGateway("不合格：与主题无关"))
    result = _image_search_payload("https://img.example.com/x.jpg")
    state = {"current_plan": {"subject": "Python", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass_with_warning"
    assert v.severity == "info"


def test_vision_reflector_drops_image_on_vlm_error_event(vlm_review_enabled, mock_localize):
    """Provider-level error (e.g. DashScope) → image dropped, not approved.
    With all dropped → pass_with_warning (non-blocking)."""
    class _ErrorGateway:
        def stream_chat_with_tools(self, messages, tools, **_):
            yield {"type": "error", "message": "Failed to download multimodal content"}

    r = VisionReflector(_ErrorGateway())
    result = _image_search_payload("https://geo-blocked.example.com/x.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass_with_warning"
    assert not v.filtered_data.get("images")


def test_vision_reflector_drops_image_on_empty_vlm_text(vlm_review_enabled, mock_localize):
    """Empty / blank model response → image dropped (not approved)."""
    class _EmptyGateway:
        def stream_chat_with_tools(self, messages, tools, **_):
            yield {"type": "text_delta", "content": "   "}
            yield {"type": "done"}

    r = VisionReflector(_EmptyGateway())
    result = _image_search_payload("https://example.com/x.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass_with_warning"


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


def test_vision_reflector_runs_image_search_when_vlm_enabled(vlm_review_enabled, mock_localize):
    """When enabled, VLM review (download→base64) approves suitable images."""
    r = VisionReflector(_FakeVisionGateway("合格：清晰相关"))
    result = _image_search_payload("https://img.example.com/good.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}
    v = r.evaluate("image_search", result, state, {"require_images": True})
    assert v.verdict == "pass"
    imgs = v.filtered_data.get("images") or []
    assert imgs and imgs[0]["url"].startswith("/api/images/searched/")


def test_vision_reflector_drops_image_on_ambiguous_reply(vlm_review_enabled, mock_localize):
    """A reply that omits both '合格' and '不合格' is not approval → dropped."""
    class _AmbiguousGateway:
        def stream_chat_with_tools(self, messages, tools, **_):
            yield {"type": "text_delta", "content": "我无法评估这张图片"}
            yield {"type": "done"}

    r = VisionReflector(_AmbiguousGateway())
    result = _image_search_payload("https://example.com/x.jpg")
    state = {"current_plan": {"subject": "RAG", "resource_type": "report"}}

    v = r.evaluate("image_search", result, state, {"require_images": True})

    assert v.verdict == "pass_with_warning"
