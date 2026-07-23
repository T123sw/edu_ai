"""P2-5 编排入口：串联 P2-2~P2-4 的全部产出。

researchContext 合并注入（web + 本课程 RAG Top-K + 知识图谱节点/课时，
SPEC-04 §4.3；后者是 Phase 2.5/D4 补的第三路）→ 提交 `generate_classroom`
job（P2-4 `classroom_job_service`）→ sidecar 完成后校验 + 落库
（`classroom_validation`/`classroom_persistence`，SPEC-02 §6/SPEC-04 §6）→
返回最终 `EduJob`（succeeded/failed 由真实的落库结果决定，不是 sidecar 说了
算，见 SPEC-05 §2.2）。
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any, Optional

import anyio

from app.integrations.openmaic import OpenMaicClient
from app.services.classroom_job_service import start_generate_classroom_job
from app.services.classroom_persistence import persist_classroom_result
from app.services.job_store import EduJob
from app.services.knowledge_graph_context import fetch_knowledge_graph_context
from core.course_storage import CourseStorageManager

log = logging.getLogger("classroom_service")

DEFAULT_RAG_TOP_K = 5


def fetch_course_rag_snippets(
    *,
    course_storage_manager: CourseStorageManager,
    course_id: str,
    query: str,
    top_k: int = DEFAULT_RAG_TOP_K,
    rag_system: Optional[Any] = None,
) -> Optional[str]:
    """检索"本课程知识库"的 Top-K 片段，带出处格式化为一段文本（同步/阻塞）。

    刻意只信任课程自己知识库里已登记的文档——`allowed_sources` 收窄到这些
    文档解析出的 source_key；课程没有配套知识库文档时直接返回 None，**绝不
    退化成不限范围的全库检索**（那会把其它课程/其它用户的资料混进本课件的
    生成上下文，是相关性也是隐私问题）。

    **已知简化（待确认，非阻塞）**：课程知识库文档在上传时以上传者的
    username 作为 owner 导入 rag_v2（`app/api/courses.py` 的
    `upload_knowledge_base_document`），但课程知识库索引条目里
    `owner_user_id` 对"course"库类型固定存 None（只有 personal 库类型才存实际
    上传者）。这里解析时故意传 `owner=None`（宽松匹配，不按上传者身份过滤），
    因为课程共享知识库的定位就是"同课程可见"而非"个人私有"——如果以后要收紧
    到"仅同课程教师可读"，需要在这里补权限校验。

    任何异常（embedding/向量库未配置、RAG 系统未就绪等）都吞掉返回
    None：RAG 只是补充，不是必需（SPEC-04 §4.3 原则：缺它 LLM+web 也该能生成）。
    """
    try:
        if rag_system is None:
            from modules.rag_v2.api import get_rag_system

            rag_system = get_rag_system()

        from modules.rag_v2.document_resolver import resolve_rag_document

        index = course_storage_manager.get_knowledge_base_index(course_id)
        source_keys: list[str] = []
        for item in index or []:
            candidate = item.get("path") or item.get("id")
            if not candidate:
                continue
            resolved = resolve_rag_document(rag_system, candidate, owner=None)
            if resolved and resolved.source_key not in source_keys:
                source_keys.append(resolved.source_key)

        if not source_keys:
            return None

        query_embedding = rag_system.embedding_client.embed_query(query)
        chunks = rag_system.vector_store.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=top_k,
            allowed_sources=source_keys,
        )
        if not chunks:
            return None

        blocks: list[str] = []
        for chunk in chunks:
            metadata = chunk.get("metadata") or {}
            source = metadata.get("source") or metadata.get("file_name") or "本课程知识库"
            text = str(chunk.get("document") or chunk.get("content") or "").strip()
            if text:
                blocks.append(f"[来源: {source}]\n{text}")

        return "\n\n---\n\n".join(blocks) if blocks else None
    except Exception:  # noqa: BLE001 — RAG 是补充，任何失败都不能拖垮生成主链路
        log.exception(
            "RAG retrieval failed for course=%s; continuing without RAG supplement", course_id
        )
        return None


def merge_research_context(*parts: Optional[str]) -> Optional[str]:
    """web/RAG/知识图谱各路结果合并叠加（不互相短路），空片段自动跳过。"""
    non_empty = [p.strip() for p in parts if p and p.strip()]
    return "\n\n".join(non_empty) if non_empty else None


async def generate_classroom_for_course(
    *,
    course_id: str,
    requirement: str,
    owner: Optional[str],
    course_storage_manager: CourseStorageManager,
    web_research_context: Optional[str] = None,
    pdf_content: Optional[dict[str, Any]] = None,
    enable_web_search: bool = False,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    client: Optional[OpenMaicClient] = None,
    rag_system: Optional[Any] = None,
) -> EduJob:
    """顶层入口：拼 researchContext（web+RAG+知识图谱 合并叠加）→ 提交
    sidecar job → sidecar 完成后校验+落库 → 返回最终 edu_job。"""
    rag_context = await anyio.to_thread.run_sync(
        partial(
            fetch_course_rag_snippets,
            course_storage_manager=course_storage_manager,
            course_id=course_id,
            query=requirement,
            top_k=rag_top_k,
            rag_system=rag_system,
        )
    )
    # 知识图谱是本地小 JSON 树的一次内存遍历，不是网络/向量库调用，
    # 不需要像 RAG 那样丢线程池（不会有明显阻塞）。
    kg_context = fetch_knowledge_graph_context(
        course_storage_manager=course_storage_manager,
        course_id=course_id,
        query=requirement,
    )
    research_context = merge_research_context(web_research_context, rag_context, kg_context)

    async def _on_sidecar_succeeded(result: dict[str, Any]) -> dict[str, Any]:
        return persist_classroom_result(
            course_storage_manager=course_storage_manager,
            course_id=course_id,
            owner=owner,
            result=result,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    return await start_generate_classroom_job(
        requirement=requirement,
        research_context=research_context,
        pdf_content=pdf_content,
        enable_web_search=enable_web_search,
        owner=owner,
        client=client,
        on_sidecar_succeeded=_on_sidecar_succeeded,
    )
