from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class VisualNeed:
    """Visual asset requirements attached to a fetch_visuals plan step (Phase 6-B).

    query_candidates carry pre-thought-out search queries so the executor LLM
    doesn't have to invent them; on reflect retry the executor picks the next
    unused candidate.
    """
    required: bool = False
    type: Literal["real", "diagram", "chart", "any"] = "any"
    query_candidates: list[str] = field(default_factory=list)
    purpose: str = ""
    max_count: int = 3

    def to_dict(self) -> dict:
        return {
            "required": self.required,
            "type": self.type,
            "query_candidates": list(self.query_candidates),
            "purpose": self.purpose,
            "max_count": self.max_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VisualNeed":
        return cls(
            required=bool(d.get("required", False)),
            type=d.get("type", "any"),
            query_candidates=list(d.get("query_candidates") or []),
            purpose=str(d.get("purpose", "")),
            max_count=int(d.get("max_count", 3)),
        )


@dataclass
class PlanStep:
    index: int
    user_title: str           # shown to user: "检索课程资料与案例"
    internal_action: str      # executor/router uses: "retrieve_context"
    expected_tools: list[str]
    constraints: dict = field(default_factory=dict)
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"
    visual_need: Optional[VisualNeed] = None

    def to_dict(self) -> dict:
        out = {
            "index": self.index,
            "user_title": self.user_title,
            "internal_action": self.internal_action,
            "expected_tools": self.expected_tools,
            "constraints": self.constraints,
            "status": self.status,
        }
        if self.visual_need is not None:
            out["visual_need"] = self.visual_need.to_dict()
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        vn = d.get("visual_need")
        return cls(
            index=d["index"],
            user_title=d["user_title"],
            internal_action=d["internal_action"],
            expected_tools=d.get("expected_tools", []),
            constraints=d.get("constraints", {}),
            status=d.get("status", "pending"),
            visual_need=VisualNeed.from_dict(vn) if vn else None,
        )


@dataclass
class Plan:
    steps: list[PlanStep]
    resource_type: str  # "report" | "ppt" | "lesson_plan" | "quiz" | "unknown"
    subject: str
    global_constraints: dict = field(default_factory=lambda: {
        "max_retries_per_step": 2,
        "max_total_reflect_retries": 4,
    })
    can_replan: bool = True

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "resource_type": self.resource_type,
            "subject": self.subject,
            "global_constraints": self.global_constraints,
            "can_replan": self.can_replan,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(
            steps=[PlanStep.from_dict(s) for s in d.get("steps", [])],
            resource_type=d.get("resource_type", "unknown"),
            subject=d.get("subject", ""),
            global_constraints=d.get("global_constraints", {
                "max_retries_per_step": 2,
                "max_total_reflect_retries": 4,
            }),
            can_replan=d.get("can_replan", True),
        )
