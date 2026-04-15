from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Tuple

from langchain_core.tools import tool

from core.config import Config
from rag_v2.api import get_rag_system
from rag_v2.document_resolver import resolve_rag_document_ids


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
            result = rag_system.query(
                query,
                top_k=top_k,
                use_rag=True,
                selected_doc_ids=rag_context.get("selected_doc_ids") or [],
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
            from app.deepsearch_pipeline import run_deepsearch_pipeline

            rag_context = rag_context_var.get()
            owner = rag_context.get("owner")
            question = str(rag_context.get("question") or query or "").strip()

            result = run_deepsearch_pipeline(
                query=query,
                owner=owner,
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

            imported_docs = result.get("imported") or []
            selected_paths = [doc.get("file_path") for doc in imported_docs if doc.get("file_path")]
            if selected_paths:
                rag_system = get_rag_system()
                selected_doc_ids = resolve_rag_document_ids(rag_system, selected_paths, owner=owner)

                rag_context["selected_doc_ids"] = selected_doc_ids
                rag_result = rag_system.query(
                    question or query,
                    top_k=5,
                    use_rag=True,
                    selected_doc_ids=selected_doc_ids,
                    owner=owner,
                )
                rag_answer = str(rag_result.get("answer") or "").strip()
                rag_sources = rag_result.get("sources") or []
                result["sources"] = rag_sources
                result["rag"] = {
                    "answer": rag_answer,
                    "sources": rag_sources,
                    "selected_doc_ids": selected_doc_ids,
                }

                course_id = rag_context.get("course_id")
                if course_id:
                    try:
                        from core.course_storage import storage_manager

                        index = storage_manager.get_knowledge_base_index(course_id)
                        for doc in imported_docs:
                            file_path = doc.get("file_path")
                            if not file_path:
                                continue
                            url = doc.get("url") or doc.get("source_url")
                            file_name = doc.get("file_name") or Path(file_path).name
                            if any(
                                item.get("url") == url
                                or item.get("source_url") == url
                                or item.get("filename") == file_name
                                for item in index
                            ):
                                continue

                            try:
                                file_data = Path(file_path).read_bytes()
                            except Exception:
                                continue

                            relative_path = storage_manager.save_knowledge_base_file(
                                course_id,
                                file_data,
                                file_name,
                            )
                            if not relative_path:
                                continue

                            index = storage_manager.get_knowledge_base_index(course_id)
                            for item in index:
                                if item.get("filename") == file_name:
                                    if url:
                                        item["url"] = url
                                    item["source_url"] = url
                                    item["doc_kind"] = "web"
                                    break
                        storage_manager.save_knowledge_base_index(course_id, index)
                    except Exception:
                        pass

                rag_context["deepsearch_done"] = True

                if rag_answer:
                    summarizer = rag_context.get("gateway")
                    summary_prompt = (
                        "你是教育助理，请基于下列资料回答用户问题。"
                        "如果用户的问题是明确提问，请直接回答；"
                        "如果问题不明确或只是请求查找资料，请对资料做简洁总结。\n\n"
                        f"用户问题：{question or '（无）'}\n\n"
                        f"资料：{rag_answer}\n"
                    )
                    final_text = summarizer.chat(
                        [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": summary_prompt},
                        ]
                    )
                    rag_context["final_answer"] = final_text
                    rag_context["final_answer_source"] = "deepsearch"
                    rag_context["skip_chat_llm"] = True
                    rag_context["deepsearch_done"] = True

            return json.dumps(result or {}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    return rag_search_tool, deep_research_tool
