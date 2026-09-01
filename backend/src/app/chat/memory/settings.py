from __future__ import annotations

import os

from pydantic import BaseModel


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AgentMemorySettings(BaseModel):
    enabled: bool = True
    langmem_enabled: bool = True
    shadow_mode: bool = False
    langmem_background: bool = True
    embedding_enabled: bool = False
    langmem_timeout_ms: int = 12_000
    langmem_max_candidates: int = 4
    retrieval_limit: int = 8
    min_confidence: float = 0.72
    token_budget: int = 1_500

    @classmethod
    def from_environment(cls) -> "AgentMemorySettings":
        return cls(
            enabled=_bool("AGENT_MEMORY_ENABLED", True),
            langmem_enabled=_bool("AGENT_MEMORY_LANGMEM_ENABLED", True),
            shadow_mode=_bool("AGENT_MEMORY_LANGMEM_SHADOW_MODE", False),
            langmem_background=_bool("AGENT_MEMORY_LANGMEM_BACKGROUND", True),
            embedding_enabled=_bool("AGENT_MEMORY_EMBEDDING_ENABLED", False),
            langmem_timeout_ms=int(
                os.getenv("AGENT_MEMORY_LANGMEM_TIMEOUT_MS", "12000")
            ),
            langmem_max_candidates=int(
                os.getenv("AGENT_MEMORY_LANGMEM_MAX_CANDIDATES", "4")
            ),
            retrieval_limit=int(os.getenv("AGENT_MEMORY_RETRIEVAL_LIMIT", "8")),
            min_confidence=float(os.getenv("AGENT_MEMORY_MIN_CONFIDENCE", "0.72")),
            token_budget=int(os.getenv("AGENT_MEMORY_TOKEN_BUDGET", "1500")),
        )
