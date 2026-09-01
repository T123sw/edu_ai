from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.chat.api.schemas_v2 import (
    KnowledgeBaseDirectBlogRequestV2,
    KnowledgeBaseDirectFlashcardRequestV2,
    KnowledgeBaseDirectGameRequestV2,
    KnowledgeBaseDirectGraphRequestV2,
    KnowledgeBaseDirectQuizRequestV2,
    KnowledgeBaseDirectReportRequestV2,
)


SOURCE_REQUESTS = [
    (
        KnowledgeBaseDirectReportRequestV2,
        {"question": "Report", "course_id": "c1"},
    ),
    (
        KnowledgeBaseDirectQuizRequestV2,
        {"course_id": "c1", "quiz_config": {"topic": "Quiz"}},
    ),
    (
        KnowledgeBaseDirectGameRequestV2,
        {"course_id": "c1", "game_type": "drag_match"},
    ),
    (
        KnowledgeBaseDirectFlashcardRequestV2,
        {
            "course_id": "c1",
            "flashcard_config": {"title": "Cards"},
            "idempotency_key": "cards-1",
        },
    ),
    (
        KnowledgeBaseDirectGraphRequestV2,
        {"course_id": "c1", "idempotency_key": "graph-1"},
    ),
    (
        KnowledgeBaseDirectBlogRequestV2,
        {"course_id": "c1", "topic": "Blog", "idempotency_key": "blog-1"},
    ),
]


@pytest.mark.parametrize(("request_model", "payload"), SOURCE_REQUESTS)
def test_direct_generation_accepts_none_without_documents(
    request_model, payload
):
    request = request_model.model_validate(
        payload
        | {
            "source_mode": "none",
            "selected_doc_ids": [],
        }
    )
    assert request.source_mode == "none"


@pytest.mark.parametrize(("request_model", "payload"), SOURCE_REQUESTS)
def test_selected_mode_requires_documents(request_model, payload):
    with pytest.raises(ValidationError):
        request_model.model_validate(
            payload
            | {
                "source_mode": "selected_documents",
                "selected_doc_ids": [],
            }
        )


@pytest.mark.parametrize(("request_model", "payload"), SOURCE_REQUESTS)
def test_non_selected_modes_reject_document_ids(request_model, payload):
    with pytest.raises(ValidationError):
        request_model.model_validate(
            payload
            | {
                "source_mode": "course_auto",
                "selected_doc_ids": ["doc-1"],
            }
        )
