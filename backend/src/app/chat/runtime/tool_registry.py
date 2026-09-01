from __future__ import annotations


def build_tool_registry(policy, *, rag_factory=None, web_factory=None):
    tools = {}
    if getattr(policy, "allow_rag", False):
        tools["rag_search"] = rag_factory() if rag_factory else object()
    if getattr(policy, "allow_web", False):
        tools["deep_research"] = web_factory() if web_factory else object()
    return tools
