"""Deepsearch API routes — HTTP layer only.

Delegates business logic to app.services.deepsearch_service.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.auth import get_current_user
from app.schemas.deepsearch import DeepSearchAndCrawlRequest
from app.services import deepsearch_service as _svc

router = APIRouter(prefix="/agent", tags=["深度搜索"])


@router.post("/deepsearch-and-crawl")
async def deepsearch_and_crawl(
    request: DeepSearchAndCrawlRequest,
    current_user: dict = Depends(get_current_user),
):
    username = current_user.get("username", "unknown")

    try:
        result = _svc.run_deepsearch_and_crawl(
            query=request.query,
            owner=username,
            depth=request.depth,
            max_urls=request.max_urls,
            crawl_timeout=request.crawl_timeout,
            save_to_kb=request.save_to_kb,
            course_id=request.course_id,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
        )

        if not result.get("ok"):
            return JSONResponse(status_code=200, content=result)
        return result

    except NotImplementedError as e:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": f"深度搜索功能未配置: {str(e)}",
                "query": request.query,
            },
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": f"处理失败: {str(e)}",
                "query": request.query,
            },
        )


@router.get("/crawl-results/{batch_id}")
async def get_crawl_results(
    batch_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = _svc.get_crawl_results(batch_id=batch_id)
        if not result.get("ok"):
            return JSONResponse(status_code=404, content=result)
        return result

    except NotImplementedError as e:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": f"深度搜索功能未配置: {str(e)}",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": f"获取结果失败: {str(e)}",
            },
        )


@router.get("/crawl-history")
async def get_crawl_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    try:
        return _svc.get_crawl_history(limit=limit)

    except NotImplementedError as e:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": f"深度搜索功能未配置: {str(e)}",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": f"获取历史失败: {str(e)}",
            },
        )
