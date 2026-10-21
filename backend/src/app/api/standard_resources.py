"""Course-scoped standard learning resource routes."""

from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.course_dependencies import require_course_generate, require_course_read
from app.persistence.dependencies import (
    get_postgres_material_repository,
    get_standard_resource_repository,
)
from app.schemas.standard_resources import (
    StandardResourceBatchCreateRequest,
    StandardResourceBatchPreviewRequest,
    StandardResourceBatchPreviewResponse,
    StandardResourceBatchResponse,
    StandardResourceCatalogResponse,
    StandardResourceReviewRequest,
    StandardResourceReviewResponse,
)
from app.services.classroom_service import submit_classroom_generation_job
from app.services.course_access import CoursePrincipal
from app.services.generation_command import GenerationCommand, generation_command_service
from app.services.job_store import get_job
from app.standard_resources.batch_service import StandardResourceBatchService
from app.standard_resources.repository import (
    StandardResourceRepository,
    StandardResourceRuleError,
)
from app.standard_resources.review_service import StandardResourceReviewService
from app.standard_resources.service import StandardResourceService
from core.course_storage import CourseStorageManager


router = APIRouter(prefix="/api/courses/{course_id}", tags=["standard-resources"])


def _rule_http_error(error: StandardResourceRuleError) -> HTTPException:
    code_map = {
        "BATCH_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "BATCH_ITEM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "STANDARD_RESOURCE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "MATERIAL_VERSION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "VERSION_NOT_PENDING": status.HTTP_409_CONFLICT,
        "COURSE_HAS_NO_LEAVES": status.HTTP_409_CONFLICT,
        "NO_LEAF_SELECTED": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "LEAF_NOT_FOUND": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "INVALID_REVIEW_DECISION": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "REJECTION_REASON_REQUIRED": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "LEARNING_MANIFEST_INVALID": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "LEARNING_MANIFEST_MISMATCH": status.HTTP_409_CONFLICT,
        "LEARNING_MANIFEST_IMMUTABLE": status.HTTP_409_CONFLICT,
        "VERSION_CHANGED": status.HTTP_409_CONFLICT,
        "GRAPH_VERSION_CHANGED": status.HTTP_409_CONFLICT,
        "SLOT_GENERATION_ACTIVE": status.HTTP_409_CONFLICT,
        "NO_ACTIONABLE_RESOURCES": status.HTTP_409_CONFLICT,
        "INVALID_GENERATION_MODE": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "INVALID_STANDARD_KIND": status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
    return HTTPException(
        status_code=code_map.get(error.code, status.HTTP_400_BAD_REQUEST),
        detail={"code": error.code, "message": error.message},
    )


def _manager() -> CourseStorageManager:
    return CourseStorageManager()


def get_standard_resource_catalog_service() -> StandardResourceService:
    manager = _manager()
    materials = get_postgres_material_repository()
    return StandardResourceService(
        graph_lookup=manager.get_knowledge_graph,
        material_list=materials.list,
        version_lookup=materials.get_version,
    )


def get_standard_resource_batch_service() -> StandardResourceBatchService:
    manager = _manager()
    materials = get_postgres_material_repository()

    async def submitter(item: dict, context: dict):
        from app.chat.harness.bundle_profiles import standard_resource_bundle_contract
        from app.chat.harness.resource_profiles import resource_contract

        generation_context = dict(context.get("generation_context") or {})
        bundle_spec = dict(generation_context.get("bundle_spec") or {})
        bundle_contract = standard_resource_bundle_contract()
        metadata = {
            key: context[key]
            for key in (
                "origin_type",
                "standard_kind",
                "generation_batch_id",
                "current_review_status",
                "review_status",
            )
        }
        standard_metadata = {
            "title": context["title"],
            **metadata,
            "standard_action": context.get("action"),
            "bundle_spec": bundle_spec,
        }
        if item["standard_kind"] == "classroom":
            classroom_config = {
                "resource_type": "classroom",
                "title": item["leaf_title"],
                "subject": item["leaf_title"],
                "audience": "课程学生",
                "focus": json.dumps(bundle_spec, ensure_ascii=False),
                "confirmed_outline": "按共享教学目标整理需求，内部创作由 HyperFrames 原生工作流决定",
                "harness_chapters": [],
                "harness_organization": {"objectives": bundle_spec.get("objectives", [])},
                "classroom_options": {},
                "standard_bundle_spec": bundle_spec,
                "standard_bundle_contract": bundle_contract,
                "standard_action": context.get("action"),
                "baseline_version": generation_context.get("baseline_version"),
                "baseline_summary": generation_context.get("baseline_summary"),
                "approved_version": generation_context.get("approved_version"),
                "rejection_reason": generation_context.get("rejection_reason"),
            }
            return await submit_classroom_generation_job(
                course_id=context["course_id"],
                requirement=(
                    f'围绕知识点“{item["leaf_title"]}”生成精炼、可学习的 AI 课堂。\n'
                    f'共享教学蓝图：{json.dumps(bundle_spec, ensure_ascii=False)}\n'
                    f'资源包 Skill：{bundle_contract}\n'
                    f'旧版本摘要：{generation_context.get("baseline_summary") or "无"}\n'
                    f'退回意见：{generation_context.get("rejection_reason") or "无"}\n'
                    f'课堂契约：{resource_contract("classroom")}'
                ),
                owner=context["owner_user_id"],
                course_storage_manager=manager,
                enable_web_search=False,
                enable_tts=False,
                scope_type=context["scope_type"],
                scope_id=context["scope_id"],
                source_mode="course_auto",
                topic=item["leaf_title"],
                audience="课程学生",
                objectives=list(bundle_spec.get("objectives") or [f'理解并能应用“{item["leaf_title"]}”']),
                idempotency_key=context["idempotency_key"],
                material_id=item["material_id"],
                material_metadata={
                    **standard_metadata,
                    "review_policy": "required",
                    "harness_config": classroom_config,
                },
                deadline_seconds=context["deadline_seconds"],
                execution_timeout_seconds=context["execution_timeout_seconds"],
            )
        config = {
            "entrypoint": "agent",
            "title": context["title"],
            "subject": item["leaf_title"],
            "allow_rag": True,
            "standard_resource": standard_metadata,
            "standard_bundle_spec": bundle_spec,
            "standard_bundle_contract": bundle_contract,
            "standard_action": context.get("action"),
            "baseline_version": generation_context.get("baseline_version"),
            "baseline_summary": generation_context.get("baseline_summary"),
            "approved_version": generation_context.get("approved_version"),
            "rejection_reason": generation_context.get("rejection_reason"),
            "audience": "课程学生",
        }
        if item["standard_kind"] == "study_guide":
            chapters = [
                {"title": "核心概念", "points": ["定义", "必要前提", "适用边界"]},
                {"title": "示例解析", "points": ["典型任务", "逐步推理"]},
                {"title": "常见误区", "points": ["错误表现", "校正方法"]},
                {"title": "复习清单", "points": ["目标自检", "迁移提示"]},
            ]
            config.update(
                {
                    "focus": (
                        "核心概念、常见误区、例题与复习清单。"
                        f"共享教学蓝图：{json.dumps(bundle_spec, ensure_ascii=False)}\n"
                        f"资源包 Skill：{bundle_contract}\n"
                        f"旧版本摘要：{generation_context.get('baseline_summary') or '无'}\n"
                        f"退回意见：{generation_context.get('rejection_reason') or '无'}"
                    ),
                    "length_hint": "约 1200 字",
                    "confirmed_outline": (
                        f"# {item['leaf_title']}\n"
                        "## 核心概念\n## 示例解析\n## 常见误区\n## 复习清单"
                    ),
                    "harness_chapters": chapters,
                    "harness_organization": {
                        "objectives": bundle_spec.get("objectives", []),
                        "chapters": chapters,
                    },
                    "harness_execution_context": {
                        "stage": "write_and_review_standard_study_guide",
                        "action": context.get("action"),
                    },
                }
            )
        else:
            config.update(
                {
                    "focus": (
                        f"共享教学蓝图：{json.dumps(bundle_spec, ensure_ascii=False)}\n"
                        f"资源包 Skill：{bundle_contract}\n"
                        f"旧版本摘要：{generation_context.get('baseline_summary') or '无'}\n"
                        f"退回意见：{generation_context.get('rejection_reason') or '无'}"
                    ),
                    "question_count": 6,
                    "difficulty": "medium",
                    "question_types": ["choice", "blank", "short"],
                }
            )
        return generation_command_service.submit(
            GenerationCommand(
                resource_type=item["material_type"],
                owner_user_id=context["owner_user_id"],
                course_id=context["course_id"],
                scope_type=context["scope_type"],
                scope_id=context["scope_id"],
                source_mode="course_auto",
                config=config,
                idempotency_key=context["idempotency_key"],
                material_id=item["material_id"],
                deadline_seconds=context["deadline_seconds"],
                execution_timeout_seconds=context["execution_timeout_seconds"],
                review_policy="required",
            )
        )

    return StandardResourceBatchService(
        repository=get_standard_resource_repository(),
        graph_lookup=manager.get_knowledge_graph,
        submitter=submitter,
        job_lookup=get_job,
        material_list=materials.list,
        material_get=materials.get,
        version_lookup=materials.get_version,
    )


def get_standard_resource_review_service() -> StandardResourceReviewService:
    return StandardResourceReviewService(
        repository=get_standard_resource_repository(),
        material_repository=get_postgres_material_repository(),
    )


@router.get("/standard-resources", response_model=StandardResourceCatalogResponse)
def list_standard_resources(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: StandardResourceService = Depends(get_standard_resource_catalog_service),
) -> StandardResourceCatalogResponse:
    result = service.list_course_resources(
        course_id=course_id,
        can_manage=principal.course_role in {"owner", "editor"},
    )
    return StandardResourceCatalogResponse.model_validate(asdict(result))


@router.post(
    "/standard-resource-batches",
    response_model=StandardResourceBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_standard_resource_batch(
    course_id: str,
    payload: StandardResourceBatchCreateRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
    service: StandardResourceBatchService = Depends(get_standard_resource_batch_service),
) -> StandardResourceBatchResponse:
    try:
        result = await service.create_batch(
            course_id=course_id,
            created_by=principal.user_id,
            leaf_ids=payload.leaf_ids,
            standard_kinds=payload.standard_kinds,
            mode=payload.mode,
            idempotency_key=payload.idempotency_key,
            expected_graph_version=payload.graph_version,
        )
        return StandardResourceBatchResponse.model_validate(result)
    except StandardResourceRuleError as error:
        raise _rule_http_error(error) from error


@router.post(
    "/standard-resource-batches/preview",
    response_model=StandardResourceBatchPreviewResponse,
)
def preview_standard_resource_batch(
    course_id: str,
    payload: StandardResourceBatchPreviewRequest,
    _principal: CoursePrincipal = Depends(require_course_generate),
    service: StandardResourceBatchService = Depends(get_standard_resource_batch_service),
) -> StandardResourceBatchPreviewResponse:
    try:
        return StandardResourceBatchPreviewResponse.model_validate(
            service.preview_batch(
                course_id=course_id,
                leaf_ids=payload.leaf_ids,
                standard_kinds=payload.standard_kinds,
                mode=payload.mode,
            )
        )
    except StandardResourceRuleError as error:
        raise _rule_http_error(error) from error


@router.get(
    "/standard-resource-batches",
    response_model=list[StandardResourceBatchResponse],
)
def list_standard_resource_batches(
    course_id: str,
    limit: int = 10,
    _principal: CoursePrincipal = Depends(require_course_generate),
    repository: StandardResourceRepository = Depends(get_standard_resource_repository),
) -> list[StandardResourceBatchResponse]:
    return [
        StandardResourceBatchResponse.model_validate(item)
        for item in repository.list_batches(course_id=course_id, limit=limit)
    ]


@router.get(
    "/standard-resource-batches/{batch_id}",
    response_model=StandardResourceBatchResponse,
)
def get_standard_resource_batch(
    course_id: str,
    batch_id: str,
    _principal: CoursePrincipal = Depends(require_course_generate),
    service: StandardResourceBatchService = Depends(get_standard_resource_batch_service),
) -> StandardResourceBatchResponse:
    try:
        return StandardResourceBatchResponse.model_validate(
            service.get_batch(course_id=course_id, batch_id=batch_id)
        )
    except StandardResourceRuleError as error:
        raise _rule_http_error(error) from error


@router.post(
    "/standard-resource-batches/{batch_id}/retry",
    response_model=StandardResourceBatchResponse,
)
async def retry_standard_resource_batch(
    course_id: str,
    batch_id: str,
    principal: CoursePrincipal = Depends(require_course_generate),
    service: StandardResourceBatchService = Depends(get_standard_resource_batch_service),
) -> StandardResourceBatchResponse:
    try:
        result = await service.retry_failed(
            course_id=course_id,
            batch_id=batch_id,
            requested_by=principal.user_id,
        )
        return StandardResourceBatchResponse.model_validate(result)
    except StandardResourceRuleError as error:
        raise _rule_http_error(error) from error


@router.post(
    "/standard-resources/{material_id}/review",
    response_model=StandardResourceReviewResponse,
)
def review_standard_resource(
    course_id: str,
    material_id: str,
    payload: StandardResourceReviewRequest,
    principal: CoursePrincipal = Depends(require_course_generate),
    service: StandardResourceReviewService = Depends(get_standard_resource_review_service),
) -> StandardResourceReviewResponse:
    try:
        return StandardResourceReviewResponse.model_validate(
            service.review(
                course_id=course_id,
                material_id=material_id,
                reviewer_id=principal.user_id,
                decision=payload.decision,
                reason=payload.reason,
                expected_version=payload.expected_version,
                expected_content_hash=payload.expected_content_hash,
            )
        )
    except StandardResourceRuleError as error:
        raise _rule_http_error(error) from error


@router.post(
    "/standard-resource-batches/{batch_id}/approve-pending",
    response_model=list[StandardResourceReviewResponse],
)
def approve_pending_standard_resources(
    course_id: str,
    batch_id: str,
    principal: CoursePrincipal = Depends(require_course_generate),
    service: StandardResourceReviewService = Depends(get_standard_resource_review_service),
) -> list[StandardResourceReviewResponse]:
    try:
        return [
            StandardResourceReviewResponse.model_validate(item)
            for item in service.approve_pending_in_batch(
                course_id=course_id,
                batch_id=batch_id,
                reviewer_id=principal.user_id,
            )
        ]
    except StandardResourceRuleError as error:
        raise _rule_http_error(error) from error
