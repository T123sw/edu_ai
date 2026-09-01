"""FastAPI 主入口 — 所有路由已迁移到 app/api/* 和 app/bootstrap.py。

保留 test-compat 重导出，后续待测试迁移后移除。
"""

from __future__ import annotations

from app.api import app
from app.integrations.rag_client import (
    load_selected_rag_documents as _load_selected_rag_documents,
    resolve_selected_doc_ids_for_query as _resolve_selected_doc_ids_for_query,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
