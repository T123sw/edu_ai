"""Pydantic models for deepsearch; no HTTP or business dependencies."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class DeepSearchAndCrawlRequest(BaseModel):
    """Request body for web search and optional crawl/import."""

    query: str = Field(..., description="Search query")
    depth: Literal["basic", "full"] = Field("basic", description="basic=Bocha summaries, full=Bocha+Tavily extract")
    max_urls: Optional[int] = Field(10, description="Maximum URL count")
    crawl_timeout: Optional[int] = Field(60, description="Per-URL extract timeout in seconds")
    save_to_kb: Optional[bool] = Field(True, description="Whether to save results into RAG")
    course_id: Optional[str] = Field(None, description="Course id")
    scope_type: Optional[str] = Field(None, description="Scope type")
    scope_id: Optional[str] = Field(None, description="Scope id")
