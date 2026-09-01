from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Tuple

from langchain_core.tools import tool

from core.config import Config
from modules.rag_v2.api import get_rag_system
from app.integrations.rag_client import resolve_selected_doc_ids_for_query


def create_search_tools(
    *,
    rag_context_var: ContextVar[Dict[str, Any]],
    rag_tool_description: str,
    deep_research_tool_description: str,
    system_prompt: str,
) -> Tuple[Any, Any]:
    @tool(description=rag_tool_description)
    def rag_search_tool(query: str, top_k: int = 5) -> str:
        """本地知识库检索。"""
        try:
            rag_system = get_rag_system()
            rag_context = rag_context_var.get()
            resolved_doc_ids = resolve_selected_doc_ids_for_query(
                rag_system,
                list(rag_context.get("selected_doc_ids") or []),
                owner=rag_context.get("owner"),
                course_id=rag_context.get("course_id"),
            )
            result = rag_system.query(
                query,
                top_k=top_k,
                use_rag=True,
                selected_doc_ids=resolved_doc_ids or list(rag_context.get("selected_doc_ids") or []),
                owner=rag_context.get("owner"),
            )
            answer = str(result.get("answer") or "").strip()
            sources = result.get("sources") or []
            return json.dumps({"answer": answer, "sources": sources}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"answer": "", "sources": [], "error": str(exc)}, ensure_ascii=False)

    @tool(description=deep_research_tool_description)
    def deep_research_tool(query: str) -> str:
        """深度研究工具。"""
        try:
            from app.services.deepsearch_service import run_deepsearch_and_crawl

            rag_context = rag_context_var.get()
            owner = rag_context.get("owner")
            question = str(rag_context.get("question") or query or "").strip()

            result = run_deepsearch_and_crawl(
                query=query,
                owner=owner,
                depth="basic",
                save_to_kb=False,
            )

            if result.get("ok") is False:
                error_message = str(result.get("message") or "深度搜索失败").strip()
                rag_context["deepsearch_error"] = error_message
                rag_context["deepsearch_done"] = True
                state_ref = rag_context.get("state")
                if isinstance(state_ref, dict):
                    state_ref["deepsearch_done"] = True
                return json.dumps(result or {}, ensure_ascii=False)

            rag_context["deepsearch_done"] = True
            state_ref = rag_context.get("state")
            if isinstance(state_ref, dict):
                state_ref["deepsearch_done"] = True

            summary = str(result.get("summary") or "").strip()
            if summary:
                rag_context["final_answer"] = summary
                rag_context["final_answer_source"] = "deepsearch"
                rag_context["skip_chat_llm"] = True
                rag_context["deepsearch_done"] = True

            return json.dumps(result or {}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    return rag_search_tool, deep_research_tool
