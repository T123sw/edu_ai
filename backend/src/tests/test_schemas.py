import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserInfoResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import HealthResponse, ModelInfo
from app.schemas.lesson_plan import LessonPlanListResponse, LessonPlanRequest, LessonPlanResponse
from app.schemas.question import (
    KnowledgePointsRequest,
    KnowledgePointsResponse,
    QuestionGenerateRequest,
    QuestionGenerateResponse,
)
from app.schemas.quiz import QuizQuestion, QuizRequest, QuizResponse
from app.schemas.report import ReportRequest, ReportResponse, ReportSection


def test_auth_schema_fields_are_available():
    assert set(LoginRequest.model_fields) == {"username", "password"}
    assert set(RegisterRequest.model_fields) == {"username", "password", "role"}
    assert set(LoginResponse.model_fields) == {"token", "user"}
    assert {"username", "role", "display_name", "email", "phone", "department", "bio", "avatar_url"} <= set(
        UserInfoResponse.model_fields
    )


def test_chat_and_common_schema_fields_are_available():
    assert set(ChatRequest.model_fields) >= {"question", "conversation_id", "top_k", "model_id", "use_rag"}
    assert set(ChatResponse.model_fields) == {"answer", "conversation_id", "sources", "title", "model_id"}
    assert set(HealthResponse.model_fields) == {"status", "message", "knowledge_base_ready", "document_count"}
    assert set(ModelInfo.model_fields) == {"id", "name", "model_name"}


def test_lesson_plan_schema_fields_are_available():
    assert set(LessonPlanRequest.model_fields) >= {"topic", "course_id", "selected_doc_ids", "duration", "difficulty"}
    assert set(LessonPlanResponse.model_fields) == {"id", "title", "objectives", "keyPoints", "hardPoints", "process", "homework"}
    assert set(LessonPlanListResponse.model_fields) == {"plans", "count"}


def test_report_schema_fields_are_available():
    assert set(ReportRequest.model_fields) >= {"title", "course_id", "selected_doc_ids", "focus_areas"}
    assert set(ReportResponse.model_fields) == {
        "id",
        "title",
        "summary",
        "introduction",
        "mainContent",
        "keyFindings",
        "conclusions",
        "recommendations",
    }
    assert set(ReportSection.model_fields) == {"title", "content", "subsections"}


def test_quiz_schema_fields_are_available():
    assert set(QuizRequest.model_fields) >= {"title", "course_id", "selected_doc_ids", "question_type", "count", "difficulty"}
    assert set(QuizQuestion.model_fields) == {"id", "type", "stem", "options", "answer", "explanation"}
    assert set(QuizResponse.model_fields) == {"id", "title", "difficulty", "question_type", "questions"}


def test_question_schema_fields_are_available():
    assert set(KnowledgePointsRequest.model_fields) == {"course_name"}
    assert set(KnowledgePointsResponse.model_fields) == {"knowledge_points"}
    assert set(QuestionGenerateRequest.model_fields) == {"knowledge_points", "types", "difficulty", "count"}
    assert set(QuestionGenerateResponse.model_fields) == {"questions"}

