"""Course-scoped standard learning resource routes."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.course_dependencies import require_course_generate, require_course_read
from app.persistence.dependencies import (
    get_postgres_material_repository,
    get_standard_resource_repository,
)
from app.schemas.standard_resources import (
    StandardResourceBatchCreateRequest,
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

    async def submitter(item: dict, context: dict):
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
        if item["standard_kind"] == "classroom":
            return await submit_classroom_generation_job(
                course_id=context["course_id"],
                requirement=f'围绕知识点“{item["leaf_title"]}”生成精炼、可学习的 AI 课堂',
                owner=context["owner_user_id"],
                course_storage_manager=manager,
                enable_web_search=False,
                enable_tts=False,
                scope_type=context["scope_type"],
                scope_id=context["scope_id"],
                source_mode="course_auto",
                topic=item["leaf_title"],
                audience="课程学生",
                scene_count=5,
                duration_minutes=15,
                objectives=[f'理解并能应用“{item["leaf_title"]}”'],
                idempotency_key=context["idempotency_key"],
                material_id=item["material_id"],
                material_metadata={"title": context["title"], **metadata},
                deadline_seconds=context["deadline_seconds"],
                execution_timeout_seconds=context["execution_timeout_seconds"],
            )
        config = {
            "entrypoint": "agent",
            "title": context["title"],
            "subject": item["leaf_title"],
            "allow_rag": True,
            "standard_resource": {"title": context["title"], **metadata},
        }
        if item["standard_kind"] == "study_guide":
            config.update(
                {
                    "focus": "核心概念、常见误区、例题与复习清单",
                    "length_hint": "约 1200 字",
                    "confirmed_outline": (
                        f"# {item['leaf_title']}\n"
                        "## 核心概念\n## 示例解析\n## 常见误区\n## 复习清单"
                    ),
                }
            )
        else:
            config.update(
                {
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
            )
        )

    return StandardResourceBatchService(
        repository=get_standard_resource_repository(),
        graph_lookup=manager.get_knowledge_graph,
        submitter=submitter,
        job_lookup=get_job,
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
        )
        return StandardResourceBatchResponse.model_validate(result)
    except StandardResourceRuleError as error:
        raise _rule_http_error(error) from error


@router.get(
    "/standard-resource-batches/{batch_id}",
    response_model=StandardResourceBatchResponse,
)
def get_standard_resource_batch(
    course_id: str,
    batch_id: str,
    _principal: CoursePrincipal = Depends(require_course_read),
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
