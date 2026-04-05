"""教学博客 Agent（MVP）模块。

提供：
- 启动任务（生成大纲→分章生成→组装）
- 查询任务状态

后续可扩展：人工审查（HITL）、SSE/WebSocket 流式输出、分层RAG等。
"""

from fastapi import APIRouter

from .routes import router as _routes_router

router = APIRouter()
router.include_router(_routes_router)

__all__ = ["router"]

