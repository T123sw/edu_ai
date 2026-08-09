from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

from langchain_openai import ChatOpenAI

from core.config import Config
from modules.rag_v2.api import get_rag_system
from modules.rag_v2.rag_main.api import _get_server_url, _scrub_response_sources
from modules.rag_v2.document_resolver import resolve_rag_document_ids

from app.integrations.rag_client import resolve_selected_doc_ids_for_query

from ..agents.report_generation import build_report_markdown
from ..skill_manager import SkillManager

try:
    from app.services.deepsearch_service import run_deepsearch_and_crawl
except Exception:  # pragma: no cover
    run_deepsearch_and_crawl = None


ToolResult = Dict[str, Any]
ToolCallable = Callable[..., ToolResult]
ToolRegistry = Dict[str, Dict[str, Any]]


def _ok(tool: str, summary: str, payload: Optional[Dict[str, Any]] = None, *, need_human: bool = False) -> ToolResult:
    return {
        "ok": True,
        "tool": tool,
        "summary": summary,
        "payload": payload or {},
        "need_human": need_human,
        "error": "",
    }



def _err(tool: str, message: str, payload: Optional[Dict[str, Any]] = None) -> ToolResult:
    return {
        "ok": False,
        "tool": tool,
        "summary": "",
        "payload": payload or {},
        "need_human": False,
        "error": str(message or "unknown_error"),
    }


def _normalize_rag_sources_for_chat(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    safe_sources = _scrub_response_sources(sources, _get_server_url())
    normalized: List[Dict[str, Any]] = []
    for raw_source in safe_sources:
        source = dict(raw_source or {})
        metadata = dict(source.get("metadata") or {})
        modality = str(source.get("modality") or metadata.get("modality") or "").strip().lower()
        if modality:
            source["modality"] = modality
        if modality == "image":
            image_url = str(source.get("image_url") or metadata.get("image_url") or "").strip()
            if image_url:
                source["image_url"] = image_url
        if modality == "video":
            video_url = str(source.get("video_url") or metadata.get("video_url") or "").strip()
            if video_url:
                source["video_url"] = video_url
        for key in list(source.keys()):
            if key.endswith("_path"):
                source.pop(key, None)
        source["metadata"] = metadata
        normalized.append(source)
    return normalized



def ask_human_for_clarification(*, question: str, reason: str = "") -> ToolResult:
    q = str(question or "").strip() or "请补充更多信息以继续生成。"
    return _ok(
        "ask_human_for_clarification",
        f"已向用户发起追问：{q}",
        {"question": q, "reason": str(reason or "")},
        need_human=True,
    )



def submit_outline_for_review(*, outline_json_str: str) -> ToolResult:
    raw = str(outline_json_str or "").strip()
    outline_payload: Any = raw
    if raw:
        try:
            outline_payload = json.loads(raw)
        except Exception:
            outline_payload = raw
    return _ok(
        "submit_outline_for_review",
        "大纲已提交，等待用户确认或修改。",
        {"outline": outline_payload},
        need_human=True,
    )



def rag_search_tool(
    *,
    query: str,
    top_k: int = 5,
    selected_doc_ids: Optional[List[str]] = None,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
) -> ToolResult:
    try:
        rag_system = get_rag_system()
        resolved_doc_ids = resolve_selected_doc_ids_for_query(
            rag_system,
            list(selected_doc_ids or []),
            owner=str(owner or ""),
            course_id=course_id,
        )
        result = rag_system.query(
            str(query or ""),
            top_k=max(1, int(top_k or 5)),
            use_rag=True,
            selected_doc_ids=resolved_doc_ids or list(selected_doc_ids or []),
            owner=owner,
        )
        answer = str(result.get("answer") or "").strip()
        sources = _normalize_rag_sources_for_chat(list(result.get("sources") or []))
        return _ok(
            "rag_search_tool",
            "RAG 检索完成" if answer or sources else "RAG 检索完成但结果较少",
            {"answer": answer, "sources": sources},
        )
    except Exception as exc:
        return _err("rag_search_tool", str(exc))



def _build_selected_doc_ids(*, imported_docs: List[Dict[str, Any]], owner: Optional[str], rag_system: Any) -> List[str]:
    document_ids: List[str] = []
    for doc in imported_docs:
        for key in ("index_key", "file_path", "source_key"):
            value = str(doc.get(key) or "").strip()
            if value:
                document_ids.append(value)
    return resolve_rag_document_ids(rag_system, document_ids, owner=owner)


def _source_from_result(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": str(item.get("title") or item.get("url") or ""),
        "url": str(item.get("url") or ""),
        "content": str(item.get("content") or "")[:500],
    }


def _summary_from_results(results: List[Dict[str, Any]]) -> str:
    parts = [
        str(item.get("content") or "").strip()
        for item in results
        if str(item.get("status") or "success") == "success" and str(item.get("content") or "").strip()
    ]
    return "\n\n".join(parts[:3])



def web_search_tool(*, query: str, owner: Optional[str] = None) -> ToolResult:
    if run_deepsearch_and_crawl is None:
        return _err("web_search_tool", "web_search_service_unavailable")

    try:
        result = run_deepsearch_and_crawl(
            query=str(query or "").strip(),
            owner=owner,
            depth="basic",
            save_to_kb=False,
        )
        if result.get("ok") is False:
            return _err("web_search_tool", str(result.get("message") or "deepsearch_failed"), payload=result)

        results = list(result.get("results") or [])
        sources = list(result.get("sources") or [])
        if not sources:
            sources = [_source_from_result(item) for item in results if item.get("url")]
        summary = str(result.get("summary") or result.get("answer") or "").strip()
        if not summary:
            summary = _summary_from_results(results)
        payload: Dict[str, Any] = {
            "links": list(result.get("links") or []),
            "summary": summary,
            "answer": summary,
            "sources": sources,
            "trace": {
                "web_links_count": len(list(result.get("links") or [])),
                "web_sources_count": len(sources),
            },
        }

        return _ok("web_search_tool", "Web 检索完成", payload)
    except Exception as exc:
        return _err("web_search_tool", str(exc))



def revise_outline_with_feedback(*, outline: List[Dict[str, Any]], feedback: str) -> ToolResult:
    try:
        model_cfg = Config.get_deep_model()
        api_key = str(model_cfg.get("api_key") or "").strip()
        if not api_key:
            return _err("revise_outline_with_feedback", "missing_answer_llm_api_key")

        llm = ChatOpenAI(
            model=str(model_cfg.get("model_name") or Config.LLM_MODEL_DEEP),
            openai_api_key=api_key,
            openai_api_base=str(model_cfg.get("api_base") or Config.DEEP_MODEL_API_BASE),
            temperature=0,
        )
        prompt = (
            "你是报告大纲编辑器。请根据用户修改意见，直接修改给定大纲。\n"
            "仅输出 JSON 数组，不要解释。\n\n"
            f"【当前大纲】\n{json.dumps(outline, ensure_ascii=False)}\n\n"
            f"【修改意见】\n{str(feedback or '').strip()}"
        )
        raw = llm.invoke(prompt)
        text = str(getattr(raw, "content", raw) or "").strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("[") and candidate.endswith("]"):
                    text = candidate
                    break
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        revised = json.loads(text)
        if not isinstance(revised, list):
            return _err("revise_outline_with_feedback", "invalid_outline_json")
        return _ok(
            "revise_outline_with_feedback",
            "已根据用户意见完成大纲修改，请确认是否继续调整。",
            {"outline": revised},
            need_human=True,
        )
    except Exception as exc:
        return _err("revise_outline_with_feedback", str(exc))



def generate_long_report_content(*, slots: Dict[str, str], outline: List[Dict[str, Any]]) -> ToolResult:
    try:
        content, checkpoint = build_report_markdown(
            skill_manager=SkillManager(),
            slots=dict(slots or {}),
            outline=list(outline or []),
        )
        return _ok(
            "generate_long_report_content",
            "报告正文生成完成" if content else "报告正文生成完成但内容为空",
            {"content": content, "checkpoint": checkpoint},
        )
    except Exception as exc:
        return _err("generate_long_report_content", str(exc))



def get_default_tool_registry() -> ToolRegistry:
    return {
        "ask_human_for_clarification": {
            "callable": ask_human_for_clarification,
            "signature": "(question: str, reason: str = '')",
            "requires_human": True,
        },
        "submit_outline_for_review": {
            "callable": submit_outline_for_review,
            "signature": "(outline_json_str: str)",
            "requires_human": True,
        },
        "rag_search_tool": {
            "callable": rag_search_tool,
            "signature": "(query: str, top_k: int = 5, selected_doc_ids: list[str] | None = None, owner: str | None = None, course_id: str | None = None)",
            "requires_human": False,
        },
        "web_search_tool": {
            "callable": web_search_tool,
            "signature": "(query: str, owner: str | None = None)",
            "requires_human": False,
        },
        "revise_outline_with_feedback": {
            "callable": revise_outline_with_feedback,
            "signature": "(outline: list[dict], feedback: str)",
            "requires_human": True,
        },
        "generate_long_report_content": {
            "callable": generate_long_report_content,
            "signature": "(slots: dict[str, str], outline: list[dict])",
            "requires_human": False,
        },
    }



def get_tool_registry_for_capability(*, allow_rag: bool, allow_web: bool) -> ToolRegistry:
    registry = dict(get_default_tool_registry())
    if not allow_rag:
        registry.pop("rag_search_tool", None)
    if not allow_web:
        registry.pop("web_search_tool", None)
    return registry
