from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class WebSearchError(RuntimeError):
    def __init__(self, code: str, message: str, log_id: str | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.log_id = log_id


@dataclass
class WebSearchHit:
    url: str
    title: str
    content: str
    date: str | None = None
    site: str | None = None
    images: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractResult:
    url: str
    content: str
    status: str = "success"
    error: str | None = None
    images: list[str] = field(default_factory=list)
    favicon: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
