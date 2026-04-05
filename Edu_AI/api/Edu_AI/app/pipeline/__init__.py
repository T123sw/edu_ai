"""数据采集管道模块：
负责爬虫、PDF 解析、文本切块三阶段任务的创建与状态查询。

为了保证最小侵入式接入，本模块仅依赖标准库与 FastAPI，
并使用内存字典作为任务缓存。如需持久化或分布式运行，
可后续替换为 Redis / 数据库。
"""

from fastapi import APIRouter

from .routes import router as _routes_router

router = APIRouter()
router.include_router(_routes_router)

__all__ = ["router"]
