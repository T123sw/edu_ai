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

from app.integrations.openmaic import OpenMaicClient, get_openmaic_client
from app.services.classroom_job_service import (
    ClassroomSourceIntent,
    create_classroom_job,
    run_generate_classroom_job,
    start_generate_classroom_job,
)
from app.services.classroom_media import (
    migrate_classroom_speech_audio,
    synthesize_classroom_speech_audio,
)
from app.services.classroom_persistence import ClassroomValidationError, persist_classroom_result
from app.services.openmaic_tts_service import OpenMaicTtsService
from app.services.job_store import EduJob, JobKind, list_job_page
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


async def _build_research_context(
    *,
    course_storage_manager: CourseStorageManager,
    course_id: str,
    requirement: str,
    web_research_context: Optional[str],
    rag_top_k: int,
    rag_system: Optional[Any],
    resolved_source: Optional[Any] = None,
) -> Optional[str]:
    if resolved_source is None:
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
    else:
        rag_context = str(resolved_source.context_text or "").strip() or None
    # 知识图谱是本地小 JSON 树的一次内存遍历，不是网络/向量库调用，
    # 不需要像 RAG 那样丢线程池（不会有明显阻塞）。
    kg_context = (
        None
        if resolved_source is not None and resolved_source.mode == "none"
        else fetch_knowledge_graph_context(
            course_storage_manager=course_storage_manager,
            course_id=course_id,
            query=requirement,
        )
    )
    return merge_research_context(web_research_context, rag_context, kg_context)


def _make_on_sidecar_succeeded(
    *,
    active_client: OpenMaicClient,
    course_storage_manager: CourseStorageManager,
    course_id: str,
    owner: Optional[str],
    scope_type: Optional[str],
    scope_id: Optional[str],
    source_snapshot: Optional[dict[str, Any]] = None,
    source_job_id: Optional[str] = None,
):
    async def _on_sidecar_succeeded(result: dict[str, Any]) -> dict[str, Any]:
        # `result` here is the job envelope's slim {classroomId, url,
        # scenesCount} — NOT the full GenerateClassroomResult (SPEC-04 §1.2
        # 订正 / OpenMaicClient.get_classroom 的 docstring). Must fetch the
        # full {id, stage, scenes, createdAt} separately before validating
        # and persisting.
        classroom_id = result.get("classroomId")
        if not classroom_id:
            raise ClassroomValidationError([f"job succeeded but result has no classroomId: {result!r}"])
        full_classroom = await active_client.get_classroom(classroom_id)
        # D1（SPEC-04 §5）：开了 TTS 时 sidecar 回填的 audioUrl 指向它自己的
        # 临时地址，必须先搬到 edu_ai 自己的存储、改写 url，校验/落库才能通过
        # 不变量 5。没开 TTS（没有 audioUrl）时这一步是空操作。
        await migrate_classroom_speech_audio(
            scenes=full_classroom.get("scenes") or [],
            course_id=course_id,
            classroom_id=classroom_id,
            active_client=active_client,
            course_storage_manager=course_storage_manager,
        )
        await synthesize_classroom_speech_audio(
            scenes=full_classroom.get("scenes") or [],
            course_id=course_id,
            classroom_id=classroom_id,
            course_storage_manager=course_storage_manager,
            tts_service=OpenMaicTtsService(client=active_client),
        )
        return persist_classroom_result(
            course_storage_manager=course_storage_manager,
            course_id=course_id,
            owner=owner,
            result=full_classroom,
            scope_type=scope_type,
            scope_id=scope_id,
            sidecar_base_url=active_client.config.base_url,
            source_snapshot=source_snapshot,
            source_job_id=source_job_id,
        )

    return _on_sidecar_succeeded


async def generate_classroom_for_course(
    *,
    course_id: str,
    requirement: str,
    owner: Optional[str],
    course_storage_manager: CourseStorageManager,
    web_research_context: Optional[str] = None,
    pdf_content: Optional[dict[str, Any]] = None,
    enable_web_search: bool = False,
    enable_tts: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    client: Optional[OpenMaicClient] = None,
    rag_system: Optional[Any] = None,
) -> EduJob:
    """顶层入口（同步等待版）：拼 researchContext（web+RAG+知识图谱 合并
    叠加）→ 提交 sidecar job → 阻塞至完成 → 校验+落库 → 返回最终 edu_job。

    生成通常要几分钟到几十分钟（真实实测一次 9-scene 课件约 20 分钟），HTTP
    路由不应该直接 await 这个函数——用 `submit_classroom_generation_job`
    立即拿到 queued 状态的 job 再让前端轮询。这个函数留给测试/脚本等愿意
    等的调用方。

    `enable_tts` 默认开启（D1，SPEC-04 §5）：sidecar 侧需要配置至少一个
    server-managed TTS provider（如 `TTS_QWEN_API_KEY`），否则 sidecar 会
    静默跳过配音生成（不报错，只是 audioUrl 不会出现），前端自动退回浏览器
    TTS/静音等待兜底，不影响功能完整性，只是没有真人配音。
    """
    active_client = client or get_openmaic_client(owner_user_id=owner)
    research_context = await _build_research_context(
        course_storage_manager=course_storage_manager,
        course_id=course_id,
        requirement=requirement,
        web_research_context=web_research_context,
        rag_top_k=rag_top_k,
        rag_system=rag_system,
    )
    on_sidecar_succeeded = _make_on_sidecar_succeeded(
        active_client=active_client,
        course_storage_manager=course_storage_manager,
        course_id=course_id,
        owner=owner,
        scope_type=scope_type,
        scope_id=scope_id,
    )

    return await start_generate_classroom_job(
        requirement=requirement,
        research_context=research_context,
        pdf_content=pdf_content,
        enable_web_search=enable_web_search,
        enable_tts=enable_tts,
        owner=owner,
        client=active_client,
        on_sidecar_succeeded=on_sidecar_succeeded,
    )


async def submit_classroom_generation_job(
    *,
    course_id: str,
    requirement: str,
    owner: Optional[str],
    course_storage_manager: CourseStorageManager,
    web_research_context: Optional[str] = None,
    pdf_content: Optional[dict[str, Any]] = None,
    enable_web_search: bool = False,
    enable_tts: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    client: Optional[OpenMaicClient] = None,
    rag_system: Optional[Any] = None,
    existing_job: Optional[EduJob] = None,
    source_mode: str = "course_auto",
    selected_doc_ids: Optional[list[str]] = None,
    topic: Optional[str] = None,
    audience: str = "",
    scene_count: int = 6,
    objectives: Optional[list[str]] = None,
    duration_minutes: int = 25,
    teaching_style: str = "guided",
    voice: str = "alloy",
    include_visuals: bool = True,
    research_bundle_id: str | None = None,
    idempotency_key: str | None = None,
) -> EduJob:
    """异步提交版：立即返回一个 `queued` 状态的 edu_job，真正的生成/校验/
    落库在后台 `asyncio.create_task` 里跑。调用方（HTTP 路由）应把返回的
    job 原样给前端，前端轮询 `GET /api/jobs/{edu_job_id}` 直到 `done`。

    researchContext 的拼装（RAG/知识图谱检索）仍然同步跑完才返回——这样
    "课程不存在""RAG 系统炸了"这类问题在提交阶段就能快速失败，不会让调用方
    以为提交成功了，实际后台任务立刻挂掉却无人知晓。

    `enable_tts` 见 `generate_classroom_for_course` 的说明。
    """
    source_intent = ClassroomSourceIntent.create(
        source_mode,
        list(selected_doc_ids or []),
    )
    normalized_key = str(idempotency_key or "").strip()
    if existing_job is None and normalized_key:
        # Classroom jobs predate GenerationCommand, so apply the same durable,
        # owner/course-scoped deduplication at this boundary.  A duplicate must
        # return the original job and must not enqueue a second sidecar task.
        existing = list_job_page(
            owner_user_id=str(owner or ""),
            kinds=[JobKind.GENERATE_CLASSROOM],
            course_id=course_id,
            limit=200,
        )
        for candidate in existing.items:
            if str((candidate.input_summary or {}).get("idempotency_key") or "") == normalized_key:
                return candidate
    job = existing_job or create_classroom_job(
            owner=owner,
            course_id=course_id,
            scope_type=scope_type or "course",
            scope_id=scope_id,
            input_summary={
                "title": requirement[:120],
                "requirement": requirement,
                "resource_type": "classroom",
                "enable_web_search": enable_web_search,
                "enable_tts": enable_tts,
                "source_mode": source_intent.mode,
                "selected_doc_ids": list(source_intent.selected_document_ids),
                "objectives": list(objectives or []),
                "duration_minutes": duration_minutes,
                "teaching_style": teaching_style,
                "voice": voice if enable_tts else "",
                "include_visuals": include_visuals,
                "research_bundle_id": str(research_bundle_id or ""),
                "idempotency_key": normalized_key,
                "source": "classroom-studio",
            },
        )

    from app.services.platform_task_handlers import enqueue_platform_task
    from app.services.runtime_config_resolver import runtime_config_resolver

    runtime_snapshot = runtime_config_resolver.capture_snapshot(str(owner or ""))
    if enable_tts and voice:
        runtime_snapshot["voice"] = voice

    return enqueue_platform_task(
        job=job,
        workflow_type="classroom_generate",
        command={
            "course_id": course_id,
            "requirement": requirement,
            "scope_type": scope_type or "course",
            "scope_id": scope_id,
            "web_research_context": web_research_context,
            "pdf_content": pdf_content,
            "enable_web_search": enable_web_search,
            "enable_tts": enable_tts,
            "rag_top_k": rag_top_k,
            "source_mode": source_intent.mode,
            "selected_doc_ids": list(source_intent.selected_document_ids),
            "topic": topic,
            "audience": audience,
            "scene_count": scene_count,
            "objectives": list(objectives or []),
            "duration_minutes": duration_minutes,
            "teaching_style": teaching_style,
            "voice": voice if enable_tts else "",
            "include_visuals": include_visuals,
            "research_bundle_id": str(research_bundle_id or ""),
            "idempotency_key": normalized_key,
        },
        runtime_config_snapshot=runtime_snapshot,
    )
