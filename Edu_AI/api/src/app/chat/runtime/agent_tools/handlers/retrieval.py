from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result


def handle_rag_search(name: str, args: dict, ctx) -> dict:
    if ctx.rag_retriever is None:
        return error_result("rag_search", "rag_not_available", "RAG 检索器未配置")
    result = ctx.rag_retriever(
        query=str(args.get("query", "")),
        top_k=int(args.get("top_k", 5)),
        selected_doc_ids=list(getattr(ctx.capability, "selected_doc_ids", []) or []),
        owner=getattr(ctx.request, "owner", None),
    )
    payload = dict((result or {}).get("payload") or {}) if isinstance(result, dict) else {}
    answer = str(payload.get("answer") or "").strip()
    sources = list(payload.get("sources") or [])
    return ok_result("rag_search", f"检索到 {len(sources)} 条结果", {"answer": answer, "sources": sources})


def handle_web_search(name: str, args: dict, ctx) -> dict:
    if ctx.web_retriever is None:
        return error_result("web_search", "web_not_available", "Web 检索器未配置")
    result = ctx.web_retriever(query=str(args.get("query", "")), owner=getattr(ctx.request, "owner", None))
    payload = dict((result or {}).get("payload") or {}) if isinstance(result, dict) else {}
    summary = str(payload.get("summary") or payload.get("answer") or "").strip()
    sources = list(payload.get("sources") or [])
    return ok_result("web_search", f"联网检索完成，获取 {len(sources)} 个来源", {"summary": summary, "sources": sources})
