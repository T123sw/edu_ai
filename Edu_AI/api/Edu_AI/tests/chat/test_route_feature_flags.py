from app.chat.application.route_feature_flags import load_route_feature_flags


def test_load_route_feature_flags_reads_all_chat_route_switches(monkeypatch):
    monkeypatch.setenv("CHAT_USE_NEW_ORCHESTRATOR", "1")
    monkeypatch.setenv("CHAT_USE_FAST_RUNTIME", "true")
    monkeypatch.setenv("CHAT_USE_REPORT_WORKFLOW_V2", "yes")
    monkeypatch.setenv("CHAT_CAPABILITY_POLICY_ENFORCED", "1")
    monkeypatch.setenv("CHAT_SSE_V2_EVENTS", "true")
    monkeypatch.setenv("CHAT_USE_LLM_ENHANCEMENT", "true")
    monkeypatch.setenv("CHAT_TRACE_LLM_ENHANCEMENT", "true")

    flags = load_route_feature_flags()

    assert flags.enable_new_chat is True
    assert flags.enable_fast_runtime is True
    assert flags.enable_report_workflow is True
    assert flags.enforce_capability_policy is True
    assert flags.enable_sse_v2_events is True
    assert flags.enable_llm_enhancement is True
    assert flags.trace_llm_enhancement is True
