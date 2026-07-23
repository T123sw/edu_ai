"""OpenMAIC sidecar 客户端包。

对外统一入口：

    from app.integrations.openmaic import get_openmaic_client

    client = get_openmaic_client()
    envelope = await client.generate_classroom(requirement="...", research_context=ctx)
    result = await client.wait_job(envelope["pollUrl"], on_progress=...)

见 docs/spec/SPEC-07（客户端）与 docs/acceptance/ACC-07。
"""

from __future__ import annotations

from typing import Optional

from .client import OpenMaicClient, OpenMaicConfig
from .errors import (
    OpenMaicBadRequest,
    OpenMaicError,
    OpenMaicJobNotFound,
    OpenMaicPollTimeout,
    OpenMaicServerError,
    OpenMaicSSRFRejected,
    OpenMaicUnavailable,
)
from .types import JobEnvelope

__all__ = [
    "OpenMaicClient",
    "OpenMaicConfig",
    "JobEnvelope",
    "OpenMaicError",
    "OpenMaicBadRequest",
    "OpenMaicSSRFRejected",
    "OpenMaicJobNotFound",
    "OpenMaicServerError",
    "OpenMaicUnavailable",
    "OpenMaicPollTimeout",
    "get_openmaic_client",
]

_singleton: Optional[OpenMaicClient] = None


def get_openmaic_client() -> OpenMaicClient:
    """返回进程内单例（复用一个 httpx.AsyncClient 连接池，SPEC-07 §1）。"""
    global _singleton
    if _singleton is None:
        _singleton = OpenMaicClient()
    return _singleton
