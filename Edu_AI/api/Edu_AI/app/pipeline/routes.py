"""FastAPI 路由：启动任务 / 查询状态 / 概览"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .models import CrawlConfig, ParseConfig, ChunkConfig, TaskType
from .storage import store
from . import tasks as _tasks

router = APIRouter()


# ------------------------------ 启动任务 ------------------------------
@router.post("/crawl")
async def start_crawl(cfg: CrawlConfig, bg: BackgroundTasks):
    task_id = f"crawl_{uuid.uuid4().hex[:8]}"
    from .models import CrawlTask

    t = CrawlTask(task_id=task_id, config=cfg)
    store.save(t)
    bg.add_task(_tasks.crawl_worker, task_id, cfg.model_dump())
    return {"task_id": task_id}


@router.post("/parse")
async def start_parse(cfg: ParseConfig, bg: BackgroundTasks):
    task_id = f"parse_{uuid.uuid4().hex[:8]}"
    from .models import ParseTask

    t = ParseTask(task_id=task_id, config=cfg)
    store.save(t)
    bg.add_task(_tasks.parse_worker, task_id, cfg.model_dump())
    return {"task_id": task_id}


@router.post("/chunk")
async def start_chunk(cfg: ChunkConfig, bg: BackgroundTasks):
    task_id = f"chunk_{uuid.uuid4().hex[:8]}"
    from .models import ChunkTask

    t = ChunkTask(task_id=task_id, config=cfg)
    store.save(t)
    bg.add_task(_tasks.chunk_worker, task_id, cfg.model_dump())
    return {"task_id": task_id}


# ------------------------------ 查询 ------------------------------
@router.get("/status/{task_id}")
async def get_status(task_id: str):
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.get("/overview")
async def overview(limit: int = 20):
    items = store.list(limit)
    return {
        "crawl": [t for t in items if t.task_type == TaskType.CRAWL],
        "parse": [t for t in items if t.task_type == TaskType.PARSE],
        "chunk": [t for t in items if t.task_type == TaskType.CHUNK],
    }

