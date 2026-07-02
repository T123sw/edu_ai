"""Phase 6-A image_search handler unit tests.

All tests use a mock provider so no Bocha / network dependency is required.
"""
from types import SimpleNamespace

import pytest

from app.chat.runtime.agent_tools import ToolExecutionContext, execute_tool
from app.chat.runtime.agent_tools.handlers.image_search import handle_image_search
from app.chat.runtime.agent_tools.tool_meta import NEVER_CACHE, get_tool_meta


class _FakeProvider:
    """Configurable mock provider returning predetermined raw image dicts."""

    name = "fake"

    def __init__(self, images=None, raise_exc=None):
        self._images = list(images or [])
        self._raise_exc = raise_exc
        self.calls: list[dict] = []

    def search(self, *, query, count, style, safe, license_, owner):
        self.calls.append({
            "query": query, "count": count, "style": style,
            "safe": safe, "license_": license_, "owner": owner,
        })
        if self._raise_exc:
            raise self._raise_exc
        return list(self._images)


def _ctx(provider=None, owner="alice"):
    """Build a minimal ctx — handler reads provider + request.owner only."""
    return SimpleNamespace(
        image_search_provider=provider,
        request=SimpleNamespace(owner=owner),
    )


def _img(url, *, width=600, height=400, source_page=None, title="img"):
    """Helper to build a raw provider dict."""
    return {
        "url": url,
        "source_page": source_page if source_page is not None else url + "-page",
        "title": title,
        "width": width,
        "height": height,
        "thumbnail": url,
        "_provider": "fake",
    }


# ----------------------------------------------------------------------------
# T1: provider not configured
# ----------------------------------------------------------------------------
def test_handler_returns_provider_not_configured_when_ctx_has_no_provider():
    result = handle_image_search("image_search", {"query": "rag"}, _ctx(provider=None))

    assert result["ok"] is False
    assert result["error"] == "provider_not_configured"
    assert "BOCHA_API_KEY" in result["summary"]
    assert "SEARXNG" not in result["summary"]


def test_build_default_image_search_provider_uses_bocha(monkeypatch):
    from app.chat.runtime.agent_tools.handlers.providers.image_base import (
        build_default_image_search_provider,
    )

    monkeypatch.setenv("IMAGE_SEARCH_PROVIDER", "bocha")
    monkeypatch.setenv("BOCHA_API_KEY", "bocha-test-key")
    monkeypatch.setenv("BOCHA_BASE_URL", "https://bocha.example")
    monkeypatch.setenv("IMAGE_SEARCH_TIMEOUT_S", "3")

    provider = build_default_image_search_provider()

    assert provider is not None
    assert provider.name == "bocha"


def test_bocha_image_provider_requests_high_recall_count(monkeypatch):
    import httpx

    from app.chat.runtime.agent_tools.handlers.providers.bocha_provider import (
        BochaImageSearchProvider,
    )

    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(request.read().decode("utf-8"))
        return httpx.Response(200, json={"code": 200, "data": {"webPages": {"value": []}}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def mock_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.providers.bocha_provider.httpx.Client",
        mock_client,
    )

    provider = BochaImageSearchProvider(api_key="bocha-test", base_url="https://bocha.example")
    provider.search(query="rag", count=4, style="diagram", safe=True, license_="any", owner="alice")

    assert '"count":50' in payloads[0].replace(" ", "")


# ----------------------------------------------------------------------------
# T2: empty query
# ----------------------------------------------------------------------------
def test_handler_returns_empty_query_error_for_blank_query():
    result = handle_image_search(
        "image_search", {"query": "   "}, _ctx(provider=_FakeProvider())
    )

    assert result["ok"] is False
    assert result["error"] == "empty_query"


# ----------------------------------------------------------------------------
# T3: provider raises
# ----------------------------------------------------------------------------
def test_handler_surfaces_provider_exception_as_error_result():
    provider = _FakeProvider(raise_exc=RuntimeError("upstream timeout"))

    result = handle_image_search(
        "image_search", {"query": "rag"}, _ctx(provider=provider)
    )

    assert result["ok"] is False
    assert result["error"] == "RuntimeError"
    assert "upstream timeout" in result["summary"]


# ----------------------------------------------------------------------------
# T4: happy path — normalized payload shape + provenance
# ----------------------------------------------------------------------------
def test_handler_normalizes_payload_and_attaches_provenance():
    provider = _FakeProvider(images=[
        _img("https://ex.com/a.png", source_page="https://ex.com/page-a"),
        _img("https://ex.com/b.png", source_page="https://ex.com/page-b"),
    ])

    result = handle_image_search(
        "image_search",
        {"query": "rag architecture", "count": 5, "style": "diagram"},
        _ctx(provider=provider),
    )

    assert result["ok"] is True
    assert result["tool"] == "image_search"
    assert result["payload"]["query"] == "rag architecture"
    assert result["payload"]["trace"] == {
        "provider": "fake",
        "raw_count": 2,
        "filtered_count": 2,
    }
    images = result["payload"]["images"]
    assert len(images) == 2
    first = images[0]
    assert first["url"] == "https://ex.com/a.png"
    assert first["source_page"] == "https://ex.com/page-a"
    assert first["width"] == 600
    assert first["height"] == 400
    assert first["proxy_url"] is None    # 6-A 占位
    assert first["provenance"]["provider"] == "fake"
    assert "fetched_at" in first["provenance"]

    # provider received the style-modified query
    assert provider.calls[0]["style"] == "diagram"
    assert provider.calls[0]["owner"] == "alice"


# ----------------------------------------------------------------------------
# T5: heuristic filtering — small / wrong-ext / blocked host all dropped
# ----------------------------------------------------------------------------
def test_handler_filters_low_quality_or_blocked_candidates():
    provider = _FakeProvider(images=[
        _img("https://ex.com/ok.png", width=600, height=400),                          # keep
        _img("https://ex.com/tiny.png", width=120, height=400),                        # drop: too narrow
        _img("https://ex.com/shallow.png", width=600, height=120),                     # drop: too short
        _img("https://ex.com/document.pdf", width=600, height=400),                    # drop: bad ext
        _img("https://pinterest.com/x.png", width=600, height=400),                    # drop: blocked host
        _img("https://www.x.com/x.png", width=600, height=400),                        # drop: blocked subdomain
        _img("https://example.com/clean.jpg", width=800, height=600),                  # keep
    ])

    result = handle_image_search(
        "image_search", {"query": "test", "count": 10}, _ctx(provider=provider)
    )

    urls = [img["url"] for img in result["payload"]["images"]]
    assert urls == ["https://ex.com/ok.png", "https://example.com/clean.jpg"]
    assert result["payload"]["trace"]["raw_count"] == 7
    assert result["payload"]["trace"]["filtered_count"] == 2


def test_handler_keeps_provider_images_when_dimensions_or_extension_are_missing():
    provider = _FakeProvider(images=[
        _img("https://cdn.example.com/image?id=abc", width=0, height=0),
        _img("https://cdn.example.com/known-small.png", width=120, height=400),
        _img("https://cdn.example.com/thumbnail", width=600, height=0),
    ])

    result = handle_image_search(
        "image_search", {"query": "rag", "count": 10}, _ctx(provider=provider)
    )

    urls = [img["url"] for img in result["payload"]["images"]]
    assert urls == [
        "https://cdn.example.com/image?id=abc",
        "https://cdn.example.com/thumbnail",
    ]


def test_handler_does_not_misclassify_substring_lookalike_hosts():
    """Regression: previous bug had `\"x.com\" in \"ex.com\"` substring match."""
    provider = _FakeProvider(images=[
        _img("https://ex.com/a.png", width=600, height=400),
        _img("https://example.com/b.png", width=600, height=400),
        _img("https://xx.com/c.png", width=600, height=400),
    ])

    result = handle_image_search(
        "image_search", {"query": "test"}, _ctx(provider=provider)
    )

    assert len(result["payload"]["images"]) == 3


# ----------------------------------------------------------------------------
# T6: source_page dedup
# ----------------------------------------------------------------------------
def test_handler_dedupes_by_source_page():
    provider = _FakeProvider(images=[
        _img("https://ex.com/a1.png", source_page="https://ex.com/page-shared"),
        _img("https://ex.com/a2.png", source_page="https://ex.com/page-shared"),
        _img("https://ex.com/a3.png", source_page="https://ex.com/page-shared"),
        _img("https://ex.com/b.png", source_page="https://ex.com/page-other"),
    ])

    result = handle_image_search(
        "image_search", {"query": "test", "count": 10}, _ctx(provider=provider)
    )

    images = result["payload"]["images"]
    assert len(images) == 2
    assert images[0]["url"] == "https://ex.com/a1.png"       # first wins
    assert images[1]["url"] == "https://ex.com/b.png"


# ----------------------------------------------------------------------------
# T7: count clamping (default 6, max 12)
# ----------------------------------------------------------------------------
def test_handler_caps_count_at_max_value():
    provider = _FakeProvider(images=[
        _img(f"https://ex.com/{i}.png", source_page=f"https://ex.com/p{i}")
        for i in range(50)
    ])

    result = handle_image_search(
        "image_search", {"query": "test", "count": 100}, _ctx(provider=provider)
    )

    assert len(result["payload"]["images"]) == 12   # _MAX_COUNT


def test_handler_uses_default_count_when_arg_missing():
    provider = _FakeProvider(images=[
        _img(f"https://ex.com/{i}.png", source_page=f"https://ex.com/p{i}")
        for i in range(20)
    ])

    result = handle_image_search(
        "image_search", {"query": "test"}, _ctx(provider=provider)
    )

    assert len(result["payload"]["images"]) == 6     # _DEFAULT_COUNT


# ----------------------------------------------------------------------------
# T8: protocol-relative URL normalization
# ----------------------------------------------------------------------------
def test_handler_absolutizes_protocol_relative_urls():
    provider = _FakeProvider(images=[
        _img("//cdn.example.com/img.png"),
    ])

    result = handle_image_search(
        "image_search", {"query": "test"}, _ctx(provider=provider)
    )

    assert result["payload"]["images"][0]["url"] == "https://cdn.example.com/img.png"


# ----------------------------------------------------------------------------
# Executor integration: capability + NEVER_CACHE
# ----------------------------------------------------------------------------
def test_executor_denies_image_search_when_capability_disabled():
    cap = SimpleNamespace(allow_rag=False, allow_web=False, allow_image_search=False)
    ctx = ToolExecutionContext(capability=cap, max_steps=4)

    result = execute_tool("image_search", {"query": "rag"}, ctx)

    assert result["ok"] is False
    assert result["error"] == "permission_denied"


def test_executor_does_not_cache_image_search_results():
    cap = SimpleNamespace(allow_rag=False, allow_web=False, allow_image_search=True)
    provider = _FakeProvider(images=[_img("https://ex.com/a.png")])
    ctx = ToolExecutionContext(
        capability=cap, max_steps=4, image_search_provider=provider
    )

    first = execute_tool("image_search", {"query": "rag"}, ctx)
    second = execute_tool("image_search", {"query": "rag"}, ctx)

    # Both succeed AND provider was called twice (no cache reuse)
    assert first["ok"] is True
    assert second["ok"] is True
    assert len(provider.calls) == 2
    assert ctx.step_count == 2


def test_image_search_is_in_never_cache_whitelist():
    assert "image_search" in NEVER_CACHE


def test_image_search_tool_meta_is_parallel_safe_and_non_mutating():
    meta = get_tool_meta("image_search")
    assert meta.parallel_safe is True
    assert meta.mutates_state is False


# ============================================================================
# Planner fallback: image-related questions trigger fetch_visuals step
# ============================================================================

def test_planner_initial_plan_omits_fetch_visuals_until_user_confirms():
    """Phase 6-A.2 UX fix: initial plan does NOT include fetch_visuals.
    Image search runs in the post-confirm turn so accumulated_images survive
    to generate_resource without crossing a turn boundary."""
    from app.chat.runtime.nodes.planner import _fallback_plan
    capability = SimpleNamespace(
        allow_rag=False, allow_web=False, allow_image_search=True,
    )

    plan = _fallback_plan(
        "给我做一份 RAG 技术教学报告，要配图",
        state={},  # no active_draft_outline → initial path
        capability=capability,
    )

    assert plan["resource_type"] == "report"
    internal_actions = [s["internal_action"] for s in plan["steps"]]
    # confirm_outline present, fetch_visuals NOT present in initial plan
    assert "confirm_outline" in internal_actions
    assert "fetch_visuals" not in internal_actions
    # Order: draft_outline → confirm_outline → generate_resource
    assert internal_actions.index("draft_outline") < internal_actions.index("confirm_outline")
    assert internal_actions.index("confirm_outline") < internal_actions.index("generate_resource")


def test_planner_confirm_path_includes_fetch_visuals_when_outline_flagged():
    """After user confirms an outline that originated from a visual request,
    the next plan should be fetch_visuals → generate_resource (same turn)."""
    from app.chat.runtime.nodes.planner import _fallback_plan
    capability = SimpleNamespace(
        allow_rag=False, allow_web=False, allow_image_search=True,
    )

    plan = _fallback_plan(
        "生成",  # confirm message, no visual keywords
        state={
            "active_draft_outline": {
                "subject": "RAG 技术",
                "resource_type": "report",
                "outline_markdown": "...",
                "needs_visuals": True,   # persisted from the original request
            }
        },
        capability=capability,
    )

    actions = [s["internal_action"] for s in plan["steps"]]
    assert actions == ["fetch_visuals", "generate_resource"]
    fv = plan["steps"][0]
    assert fv["expected_tools"] == ["image_search"]
    assert fv["visual_need"]["query_candidates"]


def test_planner_fallback_skips_fetch_visuals_when_image_search_disabled():
    from app.chat.runtime.nodes.planner import _fallback_plan
    capability = SimpleNamespace(
        allow_rag=False, allow_web=False, allow_image_search=False,
    )

    plan = _fallback_plan(
        "给我做一份 RAG 技术教学报告，要配图",
        state={},
        capability=capability,
    )
    actions = [s["internal_action"] for s in plan["steps"]]
    assert "fetch_visuals" not in actions


def test_planner_fallback_skips_fetch_visuals_when_no_image_keyword():
    from app.chat.runtime.nodes.planner import _fallback_plan
    capability = SimpleNamespace(
        allow_rag=False, allow_web=False, allow_image_search=True,
    )

    plan = _fallback_plan(
        "给我做一份 RAG 技术教学报告",
        state={},
        capability=capability,
    )
    actions = [s["internal_action"] for s in plan["steps"]]
    assert "fetch_visuals" not in actions


def test_planner_fallback_adds_fetch_visuals_for_confirm_path_with_images():
    from app.chat.runtime.nodes.planner import _fallback_plan
    capability = SimpleNamespace(
        allow_rag=False, allow_web=False, allow_image_search=True,
    )

    plan = _fallback_plan(
        "好的，开始生成，记得配图",
        state={
            "active_draft_outline": {
                "subject": "量子计算",
                "resource_type": "report",
                "outline_markdown": "...",
            }
        },
        capability=capability,
    )
    actions = [s["internal_action"] for s in plan["steps"]]
    assert "fetch_visuals" in actions
    assert "generate_resource" in actions
    assert actions.index("fetch_visuals") < actions.index("generate_resource")


# ============================================================================
# Phase 6-B starting slice: visual_need + query_candidates
# ============================================================================

def test_extract_english_keywords_strips_chinese_chars():
    from app.chat.runtime.nodes.planner import _extract_english_keywords
    assert _extract_english_keywords("RAG 技术") == "RAG"
    assert _extract_english_keywords("BERT 模型架构") == "BERT"
    assert _extract_english_keywords("vector database") == "vector database"
    # All-Chinese subject falls back to the original
    assert _extract_english_keywords("量子计算") == "量子计算"
    assert _extract_english_keywords("") == ""


def test_build_visual_query_candidates_uses_english_subject_with_technical_suffixes():
    from app.chat.runtime.nodes.planner import _build_visual_query_candidates
    cands = _build_visual_query_candidates("RAG 技术")
    assert len(cands) >= 3
    assert all(c.startswith("RAG ") for c in cands)
    # Suffixes should NOT include "diagram" (provider doubles it via style="diagram")
    assert not any("diagram" in c.lower() for c in cands)
    # No duplicates
    assert len(set(cands)) == len(cands)


def test_fallback_plan_attaches_visual_need_with_candidates_for_fetch_visuals():
    """fetch_visuals appears in the post-confirm plan, not the initial one."""
    from app.chat.runtime.nodes.planner import _fallback_plan
    capability = SimpleNamespace(
        allow_rag=False, allow_web=False, allow_image_search=True,
    )
    plan = _fallback_plan(
        "继续",
        state={
            "active_draft_outline": {
                "subject": "RAG 技术",
                "resource_type": "report",
                "needs_visuals": True,
            }
        },
        capability=capability,
    )
    fv = next(s for s in plan["steps"] if s["internal_action"] == "fetch_visuals")
    vn = fv["visual_need"]
    assert vn["required"] is True
    assert vn["type"] == "diagram"
    cands = vn["query_candidates"]
    assert len(cands) >= 3
    assert all("RAG" in c for c in cands)
    assert vn["max_count"] >= 1


def test_attach_step_constraints_safety_nets_visual_need_when_missing():
    """LLM-driven plan path may forget visual_need on fetch_visuals — we must
    populate it from the subject as a safety net."""
    from app.chat.runtime.nodes.planner import _attach_step_constraints
    plan = {
        "subject": "RAG 技术",
        "resource_type": "report",
        "steps": [{
            "index": 1,
            "user_title": "搜配图",
            "internal_action": "fetch_visuals",
            "expected_tools": ["image_search"],
            # visual_need missing entirely
        }],
    }
    _attach_step_constraints(plan)
    vn = plan["steps"][0]["visual_need"]
    assert vn["required"] is True
    assert len(vn["query_candidates"]) >= 1


def test_inject_plan_step_hint_surfaces_query_candidate_for_fetch_visuals():
    from app.chat.runtime.nodes.executor import _inject_plan_step_hint

    plan = {
        "subject": "RAG", "resource_type": "report",
        "steps": [{
            "index": 1, "user_title": "搜配图",
            "internal_action": "fetch_visuals",
            "expected_tools": ["image_search"],
            "visual_need": {
                "required": True, "type": "diagram",
                "query_candidates": [
                    "RAG architecture diagram",
                    "RAG system overview",
                    "RAG workflow",
                ],
                "purpose": "支撑 RAG 教学",
                "max_count": 3,
            },
        }],
    }
    state = {
        "plan_mode": "guided",
        "current_plan": plan,
        "plan_step_index": 0,
        "retry_counts": {},
    }
    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "请搜图"},
    ]
    out = _inject_plan_step_hint(messages, state)
    injected_hint = next(m["content"] for m in out if m["role"] == "system" and "当前执行步骤" in m["content"])

    assert "image_search" in injected_hint
    # first candidate by default — use any of the candidates we explicitly pass in
    assert "RAG architecture diagram" in injected_hint
    assert "diagram" in injected_hint                      # style hint surfaces
    assert "RAG 教学" in injected_hint                     # purpose surfaces


def test_inject_plan_step_hint_advances_query_candidate_on_retry():
    from app.chat.runtime.nodes.executor import _inject_plan_step_hint

    plan = {
        "subject": "RAG", "resource_type": "report",
        "steps": [{
            "index": 1, "user_title": "搜配图",
            "internal_action": "fetch_visuals",
            "expected_tools": ["image_search"],
            "visual_need": {
                "required": True, "type": "diagram",
                "query_candidates": [
                    "RAG architecture diagram",
                    "RAG system overview",
                    "RAG workflow",
                ],
                "max_count": 3,
            },
        }],
    }
    state = {
        "plan_mode": "guided",
        "current_plan": plan,
        "plan_step_index": 0,
        "retry_counts": {"step_0:image_search": 1},  # already retried once
    }
    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "请搜图"},
    ]
    out = _inject_plan_step_hint(messages, state)
    hint = next(m["content"] for m in out if "当前执行步骤" in m["content"])

    # After 1 retry → should pick the SECOND candidate
    assert "RAG system overview" in hint
    assert "前次 query 未通过审查" in hint


def test_inject_plan_step_hint_omits_visual_block_for_non_fetch_visuals_steps():
    from app.chat.runtime.nodes.executor import _inject_plan_step_hint

    plan = {
        "subject": "RAG", "resource_type": "report",
        "steps": [{
            "index": 1, "user_title": "起草大纲",
            "internal_action": "draft_outline",
            "expected_tools": ["draft_outline"],
            "visual_need": {"required": True, "query_candidates": ["foo"]},  # should be ignored
        }],
    }
    state = {
        "plan_mode": "guided",
        "current_plan": plan,
        "plan_step_index": 0,
        "retry_counts": {},
    }
    out = _inject_plan_step_hint([{"role": "system", "content": "x"}, {"role": "user", "content": "y"}], state)
    hint = next(m["content"] for m in out if "当前执行步骤" in m["content"])
    assert "image_search" not in hint
    assert "RAG architecture diagram" not in hint


def test_planner_safety_net_does_not_inject_in_initial_turn():
    """Phase 6-A.2 UX: in the initial turn (no active_draft_outline) safety net
    must NOT add fetch_visuals — that would make image_search run BEFORE user
    confirms the outline, polluting accumulated_images and asking twice."""
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG 技术",
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "起草大纲",
             "internal_action": "draft_outline",
             "expected_tools": ["draft_outline"]},
            {"index": 2, "user_title": "等待用户确认",
             "internal_action": "confirm_outline",
             "expected_tools": []},
            {"index": 3, "user_title": "生成报告",
             "internal_action": "generate_resource",
             "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=True)
    state = {}  # no active_draft_outline → initial turn

    _ensure_fetch_visuals_when_needed(plan, "生成一份rag的报告，要配上图片", capability, state)

    actions = [s["internal_action"] for s in plan["steps"]]
    # Initial plan untouched: no fetch_visuals
    assert actions == ["draft_outline", "confirm_outline", "generate_resource"]


def test_planner_safety_net_injects_in_post_confirm_turn_when_llm_omits():
    """In the post-confirm turn (active_draft_outline.needs_visuals=True), safety
    net must inject fetch_visuals before generate_resource."""
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG 技术",
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "生成报告",
             "internal_action": "generate_resource",
             "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=True)
    state = {"active_draft_outline": {"needs_visuals": True}}

    _ensure_fetch_visuals_when_needed(plan, "继续", capability, state)

    actions = [s["internal_action"] for s in plan["steps"]]
    assert actions == ["fetch_visuals", "generate_resource"]
    fv = plan["steps"][0]
    assert fv["expected_tools"] == ["image_search"]
    assert fv["visual_need"]["required"] is True
    assert len(fv["visual_need"]["query_candidates"]) >= 1


def test_planner_safety_net_skips_when_question_has_no_visual_keyword():
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG",
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "生成", "internal_action": "generate_resource",
             "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=True)
    _ensure_fetch_visuals_when_needed(plan, "做一份报告", capability)
    assert all(s["internal_action"] != "fetch_visuals" for s in plan["steps"])


def test_planner_safety_net_skips_when_capability_disabled():
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG",
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "生成", "internal_action": "generate_resource",
             "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=False)
    _ensure_fetch_visuals_when_needed(plan, "要配图片", capability)
    assert all(s["internal_action"] != "fetch_visuals" for s in plan["steps"])


def test_planner_safety_net_no_op_when_already_present():
    """If LLM already added fetch_visuals right before generate_resource, don't move it."""
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG",
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "搜图",
             "internal_action": "fetch_visuals",
             "expected_tools": ["image_search"]},
            {"index": 2, "user_title": "生成",
             "internal_action": "generate_resource",
             "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=True)
    _ensure_fetch_visuals_when_needed(plan, "要配图片", capability)
    actions = [s["internal_action"] for s in plan["steps"]]
    assert actions == ["fetch_visuals", "generate_resource"]


def test_planner_safety_net_moves_misplaced_fetch_visuals_in_post_confirm_turn():
    """In post-confirm turn, if LLM put fetch_visuals BEFORE confirm/draft,
    safety net moves it to right before generate_resource so both run in
    the same turn (accumulated_images doesn't cross turn boundary)."""
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG",
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "搜图",
             "internal_action": "fetch_visuals", "expected_tools": ["image_search"]},
            {"index": 2, "user_title": "无关步骤",
             "internal_action": "other", "expected_tools": []},
            {"index": 3, "user_title": "生成报告",
             "internal_action": "generate_resource", "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=True)
    state = {"active_draft_outline": {"needs_visuals": True}}

    _ensure_fetch_visuals_when_needed(plan, "继续", capability, state)
    actions = [s["internal_action"] for s in plan["steps"]]
    assert actions == ["other", "fetch_visuals", "generate_resource"]
    assert [s["index"] for s in plan["steps"]] == [1, 2, 3]


def test_planner_safety_net_handles_state_with_explicit_none_outline():
    """Regression: state.active_draft_outline=None (initial turn) must not crash
    the safety net. Previously `state.get("active_draft_outline", {}).get(...)`
    returned None (not {}) when the key existed with value None, then crashed."""
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG", "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "起草", "internal_action": "draft_outline",
             "expected_tools": ["draft_outline"]},
            {"index": 2, "user_title": "确认", "internal_action": "confirm_outline",
             "expected_tools": []},
            {"index": 3, "user_title": "生成", "internal_action": "generate_resource",
             "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=True)
    # state has active_draft_outline explicitly None (the bug scenario)
    state = {"active_draft_outline": None}

    # Should not raise; should skip injection since question has no visual keyword
    _ensure_fetch_visuals_when_needed(plan, "生成一份报告", capability, state)
    actions = [s["internal_action"] for s in plan["steps"]]
    assert "fetch_visuals" not in actions  # no visual keyword + no persisted intent


def test_planner_safety_net_reads_persisted_intent_when_question_lacks_keyword():
    """On confirm turn the user typically says '生成' without visual keywords.
    Safety net must read active_draft_outline.needs_visuals to know intent."""
    from app.chat.runtime.nodes.planner import _ensure_fetch_visuals_when_needed

    plan = {
        "subject": "RAG",
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "生成报告",
             "internal_action": "generate_resource",
             "expected_tools": ["generate_report"]},
        ],
    }
    capability = SimpleNamespace(allow_image_search=True)
    state = {"active_draft_outline": {"needs_visuals": True}}
    _ensure_fetch_visuals_when_needed(plan, "生成", capability, state)
    actions = [s["internal_action"] for s in plan["steps"]]
    assert actions == ["fetch_visuals", "generate_resource"]


def test_request_normalizer_defaults_image_search_to_true_regardless_of_allow_web():
    """Phase 6-A.2 fix: image_search must NOT be silently disabled when
    allow_web=False. Previously coupled → caused users' '要配图' requests to
    fail silently."""
    from app.chat.application.request_normalizer import normalize_chat_request

    # No allow_web, no explicit allow_image_search → should still be True
    payload = SimpleNamespace(
        question="测试",
        allow_web=False,
        allow_rag=False,
        selected_doc_ids=[],
    )
    result = normalize_chat_request(payload)
    assert result.capability.allow_image_search is True
    assert result.capability.allow_web is False  # unchanged


def test_request_normalizer_honors_explicit_image_search_false():
    """Explicit override from frontend should still be respected."""
    from app.chat.application.request_normalizer import normalize_chat_request
    payload = SimpleNamespace(
        question="测试",
        allow_web=False,
        allow_rag=False,
        allow_image_search=False,
        selected_doc_ids=[],
    )
    result = normalize_chat_request(payload)
    assert result.capability.allow_image_search is False


def test_plan_step_serialization_roundtrips_visual_need():
    from app.chat.runtime.planning.schema import PlanStep, VisualNeed
    step = PlanStep(
        index=1, user_title="搜图", internal_action="fetch_visuals",
        expected_tools=["image_search"],
        visual_need=VisualNeed(
            required=True, type="diagram",
            query_candidates=["RAG diagram", "RAG architecture"],
            purpose="教学支撑", max_count=3,
        ),
    )
    d = step.to_dict()
    assert d["visual_need"]["query_candidates"] == ["RAG diagram", "RAG architecture"]

    restored = PlanStep.from_dict(d)
    assert restored.visual_need is not None
    assert restored.visual_need.query_candidates == ["RAG diagram", "RAG architecture"]
    assert restored.visual_need.required is True


# ============================================================================
# Day 3 — Integration: image_search through the full ReActAgent graph
# ============================================================================
# This exercises the actual graph wiring (tools_node → reflect_node → executor)
# with a mock LLM that calls image_search, a mock vision gateway that approves
# all candidates, and a fake provider feeding deterministic raw images.

from app.chat.runtime.react_agent import ReActAgent


class _FakeImageSearchLLM:
    """Fake LLM gateway: turn 1 calls image_search; turn 2 returns plain text."""

    def __init__(self):
        self.calls = 0

    def stream_chat_with_tools(self, messages, tools, tool_choice="auto",
                                temperature=0.1, max_tokens=1024):
        self.calls += 1
        if self.calls == 1:
            yield {
                "type": "tool_calls",
                "calls": [{
                    "id": "call-img-1",
                    "name": "image_search",
                    "args": {"query": "rag architecture diagram", "count": 4, "style": "diagram"},
                }],
            }
            yield {"type": "done"}
            return
        yield {"type": "text_delta", "content": "已获取相关配图。"}
        yield {"type": "done"}


class _ApproveAllVisionGateway:
    """Vision gateway that approves every image."""
    def stream_chat_with_tools(self, messages, tools, **_):
        yield {"type": "text_delta", "content": "合格"}
        yield {"type": "done"}


class _FakeFastRuntime:
    def run_stream(self, *, request, snapshot, decision):
        yield {"type": "result", "payload": {
            "message": {"role": "assistant", "content": "fallback"},
            "conversation": {"conversation_id": request.conversation_id},
            "action": {"name": "chat.reply"}, "workflow": None,
            "artifacts": [], "sources": [], "trace": {"path": "fast"},
        }}


def _e2e_request_snapshot():
    capability = SimpleNamespace(
        allow_rag=False, allow_web=False, allow_image_search=True,
    )
    request = SimpleNamespace(question="给我搜张 RAG 架构图", conversation_id="conv-img-e2e", owner="alice")
    snapshot = SimpleNamespace(capability=capability, recent_messages=[], workflow_state=None)
    return request, snapshot


def test_react_agent_invokes_image_search_and_emits_full_sse_chain():
    request, snapshot = _e2e_request_snapshot()
    provider = _FakeProvider(images=[
        _img(f"https://ex.com/{i}.png", source_page=f"https://ex.com/page-{i}")
        for i in range(6)
    ])

    agent = ReActAgent(
        agent_gateway=_FakeImageSearchLLM(),
        fast_runtime=_FakeFastRuntime(),
        vision_gateway=_ApproveAllVisionGateway(),
        image_search_provider=provider,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))
    event_types = [e["type"] for e in events]

    # SSE chain must include the key Phase 6-A signals
    assert "tool_call" in event_types
    assert "tool_result" in event_types

    tool_call_evt = next(e for e in events if e["type"] == "tool_call")
    assert tool_call_evt["payload"]["tool"] == "image_search"

    tool_result_evt = next(e for e in events if e["type"] == "tool_result")
    assert tool_result_evt["payload"]["tool"] == "image_search"
    assert tool_result_evt["payload"]["ok"] is True

    # Provider was actually called with the right query
    assert provider.calls[0]["query"] == "rag architecture diagram"
    assert provider.calls[0]["style"] == "diagram"

    # Final result event present
    assert events[-1]["type"] == "result"
    trace = events[-1]["payload"]["trace"]
    assert any(s["tool"] == "image_search" for s in trace["agent_steps"])


def test_reflect_node_accumulates_image_search_results_across_turns():
    """Day 4: reflect_node should harvest image_search payload images into
    state.accumulated_images, dedup by URL."""
    from app.chat.runtime.nodes.reflect import reflect_node
    from unittest.mock import patch

    state = {
        "messages": [],
        "tool_exchange": [],
        "current_plan": None,
        "plan_step_index": 0,
        "plan_mode": "",
        "retry_counts": {},
        "accumulated_images": [
            {"url": "https://ex.com/old.png", "title": "old"},  # pre-existing
        ],
        "last_tool_results": [
            {
                "tool_name": "image_search",
                "raw_result": {
                    "ok": True,
                    "payload": {
                        "images": [
                            {"url": "https://ex.com/new1.png", "title": "new1"},
                            {"url": "https://ex.com/old.png", "title": "dup"},  # should dedup
                            {"url": "https://ex.com/new2.png", "title": "new2"},
                        ],
                    },
                },
            }
        ],
    }

    # Run reflect_node without real LangGraph runtime — patch helpers it touches.
    with patch("app.chat.runtime.nodes.reflect.get_stream_writer", return_value=lambda _payload: None), \
         patch("app.chat.runtime.nodes.reflect._build_pipeline") as mock_pipeline:
        from app.chat.runtime.reflection.rules import ReflectorPipeline
        mock_pipeline.return_value = ReflectorPipeline.default()
        updates = reflect_node(state)

    images = updates["accumulated_images"]
    urls = [img["url"] for img in images]
    assert urls == [
        "https://ex.com/old.png",
        "https://ex.com/new1.png",
        "https://ex.com/new2.png",
    ]


def test_image_injector_handles_image_search_dict_shape():
    """Day 4: inject_images_into_report accepts the image_search payload shape
    (dict with url/title), not just MediaAsset objects."""
    from app.chat.workflows.report.image_injector import inject_images_into_report

    markdown = (
        "# 报告\n"
        "## 一、背景\n"
        "RAG 是一种...\n"
        "## 二、原理\n"
        "检索 + 生成...\n"
        "## 三、应用\n"
        "教育场景...\n"
    )
    image_search_dicts = [
        {
            "url": "https://example.com/diagram1.png",
            "title": "RAG 架构示意",
            "source_page": "https://example.com/page1",
        },
        {
            "url": "https://example.com/diagram2.png",
            "title": "向量检索流程",
            "source_page": "https://example.com/page2",
        },
    ]

    result = inject_images_into_report(markdown, image_search_dicts, max_images=2)

    assert "![RAG 架构示意](https://example.com/diagram1.png)" in result
    assert "![向量检索流程](https://example.com/diagram2.png)" in result
    # Images come AFTER the heading line they target
    rag_heading_pos = result.index("## 一、背景")
    diagram1_pos = result.index("diagram1.png")
    assert diagram1_pos > rag_heading_pos


def test_full_pipeline_image_search_to_report_artifact_contains_images():
    """End-to-end (offline): mock LLM → image_search → reflect accumulates →
    generate_report handler → captured fn produces artifact whose markdown
    embeds the searched images.

    Mocks: LLM, vision_gateway, build_report_markdown, submit_callable_task.
    Real: image_search handler, reflect_node accumulator, image_injector.
    """
    from unittest.mock import patch

    from app.chat.runtime.agent_tools.handlers import report as report_handler

    # 1. Fake provider returning deterministic candidate images
    accumulated_provider = _FakeProvider(images=[
        _img("https://example.com/rag-architecture.png", source_page="https://example.com/rag", title="RAG 架构"),
        _img("https://example.com/vector-db.png", source_page="https://example.com/db", title="向量数据库"),
    ])

    # 2. LLM that runs 3 turns: image_search, generate_report, then final text
    class _TwoToolLLM:
        def __init__(self):
            self.calls = 0
        def stream_chat_with_tools(self, messages, tools, **_):
            self.calls += 1
            if self.calls == 1:
                yield {"type": "tool_calls", "calls": [{
                    "id": "c-img", "name": "image_search",
                    "args": {"query": "RAG architecture", "count": 4, "style": "diagram"},
                }]}
            elif self.calls == 2:
                yield {"type": "tool_calls", "calls": [{
                    "id": "c-rep", "name": "generate_report",
                    "args": {
                        "subject": "RAG 技术",
                        "confirmed_outline": "## 一、原理\n## 二、流程\n## 三、应用",
                    },
                }]}
            else:
                yield {"type": "text_delta", "content": "已提交。"}
            yield {"type": "done"}

    captured_fn: dict = {}

    def _fake_submit(fn, workflow_type="", on_complete=None):
        captured_fn["fn"] = fn
        captured_fn["workflow_type"] = workflow_type
        return "task-img-test-1"

    # Stub out build_report_markdown so we don't need RAG/LLM stack
    def _fake_build_report_markdown(*, skill_manager, slots, outline=None, mode="fast"):
        body = (
            f"# {slots['core_topic']} 教学报告\n"
            "## 一、原理\n"
            "RAG 检索后生成。\n"
            "## 二、流程\n"
            "查询 → 检索 → 重排 → 生成。\n"
            "## 三、应用\n"
            "教育辅助与企业知识库。\n"
        )
        return body, {"status": "stub"}

    request, snapshot = _e2e_request_snapshot()
    agent = ReActAgent(
        agent_gateway=_TwoToolLLM(),
        fast_runtime=_FakeFastRuntime(),
        vision_gateway=_ApproveAllVisionGateway(),
        image_search_provider=accumulated_provider,
        max_steps=6, timeout_seconds=10,
    )

    with patch("app.chat.tasks.background_runner.submit_callable_task", side_effect=_fake_submit), \
         patch("app.chat.agents.report_generation.build_report_markdown",
               side_effect=_fake_build_report_markdown), \
         patch("app.chat.agents.report_generation.get_fallback_llm", return_value=None), \
         patch("app.chat.skill_manager.SkillManager"):
        events = list(agent.run_stream(request=request, snapshot=snapshot))

    # The submit_callable_task should have received the report runner fn
    assert "fn" in captured_fn, "generate_report handler did not submit a callable"
    assert captured_fn["workflow_type"] == "report"

    # Execute the captured fn synchronously and inspect the artifact
    result = captured_fn["fn"]()
    artifact = result["artifacts"][0]

    # Real image injector should have placed at least one searched image into the body
    assert artifact["artifact_type"] == "report"
    assert "https://example.com/rag-architecture.png" in artifact["content"] or \
           "https://example.com/vector-db.png" in artifact["content"]
    assert artifact["visual_assets_count"] >= 1

    # Sanity-check SSE chain
    event_types = [e["type"] for e in events]
    assert event_types.count("tool_call") == 2     # image_search + generate_report
    assert "task_submitted" in event_types         # generate_report submission


def test_react_agent_records_image_search_in_tool_exchange_and_trace():
    """tool_exchange stores human-readable formatted text for persistence;
    raw images flow to LLM next turn via reflect_filtered (Day 4 wiring)."""
    request, snapshot = _e2e_request_snapshot()
    provider = _FakeProvider(images=[
        _img("https://ex.com/diagram.png", source_page="https://ex.com/page"),
    ])

    agent = ReActAgent(
        agent_gateway=_FakeImageSearchLLM(),
        fast_runtime=_FakeFastRuntime(),
        vision_gateway=_ApproveAllVisionGateway(),
        image_search_provider=provider,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))
    result = events[-1]["payload"]

    # tool_exchange should contain the assistant tool_call + the tool result
    tool_msgs = [m for m in result["tool_exchange"] if m.get("role") == "tool"]
    assert len(tool_msgs) >= 1
    # Content is human-readable summary, not raw JSON
    assert "图片检索完成" in tool_msgs[0]["content"]

    # Trace records the step with proper summary
    img_step = next(
        s for s in result["trace"]["agent_steps"] if s["tool"] == "image_search"
    )
    assert img_step["ok"] is True
    assert "候选" in img_step["result_summary"]
