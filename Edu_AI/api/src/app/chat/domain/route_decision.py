from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class RouteDecision(BaseModel):
    path: Literal["fast", "workflow", "agent"]
    action: str
    workflow_name: Optional[str] = None
    reason: str

    @classmethod
    def fast(cls, *, action: str, reason: str) -> "RouteDecision":
        return cls(path="fast", action=action, reason=reason)

    @classmethod
    def agent(cls, *, reason: str) -> "RouteDecision":
        return cls(path="agent", action="agent.plan", reason=reason)

