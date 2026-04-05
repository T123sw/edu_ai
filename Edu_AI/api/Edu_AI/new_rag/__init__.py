"""
新RAG模块包
将所有与requests版RAG相关的实现集中在此目录，和旧的core/rag_qa完全隔离
"""

from .system import RAGSystem  # noqa: F401
from .api import router as rag_router  # noqa: F401

__all__ = ["RAGSystem", "rag_router"]


