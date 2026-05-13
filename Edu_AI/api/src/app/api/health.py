"""Health check endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencies import get_rag_system
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    rag_system = get_rag_system()
    stats: dict[str, Any] = rag_system.get_stats()
    document_count = int(stats.get("document_count", 0) or 0)
    return HealthResponse(
        status="ok",
        message="service ready",
        knowledge_base_ready=document_count > 0,
        document_count=document_count,
    )
