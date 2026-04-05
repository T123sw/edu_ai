"""pydantic 数据模型：Task 结构定义"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    CRAWL = "crawl"
    PARSE = "parse"
    CHUNK = "chunk"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class CrawlConfig(BaseModel):
    mode: str = Field(..., description="keyword/url")
    keywords: List[str] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    pages: int = 1  # 页面数（CNKI 爬虫用）
    max_sites: int = 10
    depth: int = 2
    time_range: str = "1y"
    whitelist: List[str] = Field(default_factory=list)
    auto_expand: bool = True


class ParseConfig(BaseModel):
    pdf_paths: List[str]
    output_format: str = "md"


class ChunkConfig(BaseModel):
    text_paths: List[str]
    min_heading_level: int = 3
    output_dir: str = "storage/chunks/"


class TaskBase(BaseModel):
    task_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class CrawlTask(TaskBase):
    task_type: TaskType = TaskType.CRAWL
    config: CrawlConfig


class ParseTask(TaskBase):
    task_type: TaskType = TaskType.PARSE
    config: ParseConfig


class ChunkTask(TaskBase):
    task_type: TaskType = TaskType.CHUNK
    config: ChunkConfig


Task = CrawlTask | ParseTask | ChunkTask
