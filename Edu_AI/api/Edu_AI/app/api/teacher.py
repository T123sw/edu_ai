"""Teacher API routes — HTTP layer only.

Delegates all business logic to app.services.teacher_service.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.dependencies import get_rag_system
from app.schemas.lesson_plan import (
    LessonPlanListResponse,
    LessonPlanMeta,
    LessonPlanRequest,
    LessonPlanResponse,
)
from app.schemas.question import (
    KnowledgePointsRequest,
    KnowledgePointsResponse,
    QuestionGenerateRequest,
    QuestionGenerateResponse,
)
from app.schemas.quiz import QuizRequest, QuizResponse
from app.schemas.report import ReportRequest, ReportResponse
from app.services.teacher_service import (
    delete_lesson_plan as _svc_delete_lesson_plan,
    delete_quiz as _svc_delete_quiz,
    delete_report as _svc_delete_report,
    generate_lesson_plan,
    generate_quiz,
    generate_report,
    generate_questions,
    get_course_materials,
    get_lesson_plan_detail,
    list_lesson_plans,
    suggest_knowledge_points,
)
from app.integrations.rag_client import load_selected_rag_documents
from core import Config

router = APIRouter(tags=["teacher"])


def _get_rag():
    return get_rag_system()


def _get_deep_model():
    return Config.get_deep_model()


# ---------------------------------------------------------------------------
# lesson plan
# ---------------------------------------------------------------------------

@router.post("/teacher/lesson_plan", response_model=LessonPlanResponse)
async def generate_lesson_plan_endpoint(
    payload: LessonPlanRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        if not payload.selected_doc_ids or len(payload.selected_doc_ids) == 0:
            raise HTTPException(status_code=400, detail="必须至少选择一个文档才能生成教案")

        username = current_user.get("username", "teacher")
        rag = _get_rag()

        documents_content = load_selected_rag_documents(
            rag, payload.selected_doc_ids, owner=username, log_prefix="LessonPlan",
        )
        if not documents_content:
            raise HTTPException(status_code=400, detail="无法获取选中文档的内容，请检查文档是否存在且可访问")

        return generate_lesson_plan(payload, documents_content, username, rag, _get_deep_model())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成教案失败: {exc}") from exc


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@router.post("/teacher/report", response_model=ReportResponse)
async def generate_report_endpoint(
    payload: ReportRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        if not payload.selected_doc_ids or len(payload.selected_doc_ids) == 0:
            raise HTTPException(status_code=400, detail="必须至少选择一个文档才能生成报告")

        username = current_user.get("username", "teacher")
        rag = _get_rag()

        documents_content = load_selected_rag_documents(
            rag, payload.selected_doc_ids, owner=username, log_prefix="Report",
        )
        if not documents_content:
            raise HTTPException(status_code=400, detail="无法获取选中文档的内容，请检查文档是否存在且可访问")

        return generate_report(payload, documents_content, username, rag, _get_deep_model())
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {exc}") from exc


# ---------------------------------------------------------------------------
# quiz
# ---------------------------------------------------------------------------

@router.post("/teacher/quiz", response_model=QuizResponse)
async def generate_quiz_endpoint(
    payload: QuizRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        if not payload.selected_doc_ids or len(payload.selected_doc_ids) == 0:
            raise HTTPException(status_code=400, detail="必须至少选择一个文档才能生成测验")

        question_type_map = {"choice": ["choice"], "blank": ["blank"], "mixed": ["choice", "blank"]}
        if payload.question_type not in question_type_map:
            raise HTTPException(status_code=400, detail="question_type 仅支持 choice/blank/mixed")

        difficulty_map = {"easy": "low", "medium": "medium", "hard": "high"}
        if payload.difficulty not in difficulty_map:
            raise HTTPException(status_code=400, detail="difficulty 仅支持 easy/medium/hard")

        username = current_user.get("username", "teacher")
        rag = _get_rag()

        documents_content = load_selected_rag_documents(
            rag, payload.selected_doc_ids, owner=username, log_prefix="Quiz",
        )
        if not documents_content:
            raise HTTPException(status_code=400, detail="无法获取选中文档内容，请检查文档状态")

        return generate_quiz(payload, documents_content, username, rag, _get_deep_model())
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成测验失败: {exc}") from exc


# ---------------------------------------------------------------------------
# knowledge points
# ---------------------------------------------------------------------------

@router.post("/teacher/knowledge_points", response_model=KnowledgePointsResponse)
async def suggest_knowledge_points_endpoint(payload: KnowledgePointsRequest):
    try:
        return suggest_knowledge_points(payload.course_name, _get_rag(), _get_deep_model())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成知识点失败: {exc}") from exc


# ---------------------------------------------------------------------------
# lesson plan CRUD
# ---------------------------------------------------------------------------

@router.get("/teacher/lesson_plans", response_model=LessonPlanListResponse)
async def list_lesson_plans_endpoint():
    try:
        data = list_lesson_plans()
        plans = [
            LessonPlanMeta(
                id=item["id"], title=item.get("title") or "",
                topic=item.get("topic") or "", difficulty=item.get("difficulty") or "",
                knowledge_points=item.get("knowledge_points") or [],
                created_at=item.get("created_at") or "", updated_at=item.get("updated_at") or "",
            )
            for item in data.get("plans", [])
        ]
        return LessonPlanListResponse(plans=plans, count=len(plans))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取教案列表失败: {exc}") from exc


@router.get("/teacher/lesson_plans/{plan_id}", response_model=LessonPlanResponse)
async def get_lesson_plan_detail_endpoint(plan_id: str):
    try:
        record = get_lesson_plan_detail(plan_id)
        plan_data = record.get("plan") or {}
        return LessonPlanResponse(**plan_data)
    except KeyError:
        raise HTTPException(status_code=404, detail="教案不存在")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取教案详情失败: {exc}") from exc


@router.delete("/teacher/lesson_plans/{plan_id}")
async def delete_lesson_plan_endpoint(
    plan_id: str,
    course_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    try:
        _svc_delete_lesson_plan(plan_id, course_id)
        return {"message": "教案已删除"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除教案失败: {exc}") from exc


@router.delete("/teacher/reports/{report_id}")
async def delete_report_endpoint(
    report_id: str,
    course_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    try:
        if not course_id:
            raise HTTPException(status_code=400, detail="必须提供course_id")
        _svc_delete_report(report_id, course_id)
        return {"message": "报告已删除"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除报告失败: {exc}") from exc


@router.delete("/teacher/quizzes/{quiz_id}")
async def delete_quiz_endpoint(
    quiz_id: str,
    course_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    try:
        if not course_id:
            raise HTTPException(status_code=400, detail="必须提供course_id")
        _svc_delete_quiz(quiz_id, course_id)
        return {"message": "测验已删除"}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除测验失败: {exc}") from exc


# ---------------------------------------------------------------------------
# questions
# ---------------------------------------------------------------------------

@router.post("/teacher/questions", response_model=QuestionGenerateResponse)
async def generate_questions_endpoint(payload: QuestionGenerateRequest):
    try:
        return generate_questions(payload, _get_rag(), _get_deep_model())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成题目失败: {exc}") from exc


# ---------------------------------------------------------------------------
# course materials
# ---------------------------------------------------------------------------

@router.get("/api/courses/{course_id}/materials")
async def get_course_materials_endpoint(
    course_id: str,
    material_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    try:
        return get_course_materials(course_id, material_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取课程资源失败: {exc}") from exc
