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

from app.services.runtime_config_resolver import runtime_config_resolver

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

_singletons: dict[str, OpenMaicClient] = {}


def get_openmaic_client(
    owner_user_id: str | None = None,
    snapshot: dict[str, str] | None = None,
) -> OpenMaicClient:
    """Return a connection pool bound to the resolved classroom config revision."""
    resolved = runtime_config_resolver.resolve(
        "classroom", owner_user_id=owner_user_id, snapshot=snapshot
    )
    base_url = str(resolved.get("base_url") or _default_openmaic_url())
    api_key = str(resolved.get("api_key") or "")
    cache_key = f"{resolved.get('_revision_id') or 'environment'}:{base_url}:{bool(api_key)}"
    if cache_key not in _singletons:
        _singletons[cache_key] = OpenMaicClient(
            OpenMaicConfig(base_url=base_url, api_key=api_key)
        )
    return _singletons[cache_key]


def _default_openmaic_url() -> str:
    import os

    return os.getenv("OPENMAIC_BASE_URL", "http://localhost:3000")
