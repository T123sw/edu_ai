from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ExtractionCandidate(BaseModel):
    field: str
    value: Any
    source: Literal["rule", "llm"] = "llm"
    confidence: Literal["low", "medium", "high"] = "medium"
    operation: Literal["replace", "append", "merge"] = "merge"
    reason: str | None = None
