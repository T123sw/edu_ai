"""Pydantic models for deepsearch — no HTTP or business dependencies."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DeepSearchAndCrawlRequest(BaseModel):
    """深度搜索并爬取请求"""

    query: str = Field(..., description="搜索关键词")
    max_urls: Optional[int] = Field(10, description="最多爬取的URL数量")
    crawl_timeout: Optional[int] = Field(30, description="单个URL爬取超时（秒）")
    save_to_kb: Optional[bool] = Field(True, description="是否将爬取结果永久保存到知识库并加入RAG索引")
    course_id: Optional[str] = Field(None, description="当前课程ID")
    scope_type: Optional[str] = Field(None, description="当前工作域类型")
    scope_id: Optional[str] = Field(None, description="当前工作域ID")
