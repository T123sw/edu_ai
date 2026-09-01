from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


VisualKind = Literal["diagram", "chart", "photo", "illustration", "any"]
VisualSource = Literal["knowledge_base", "web"]


@dataclass(frozen=True)
class OutlineSection:
    section_id: str
    title: str


@dataclass(frozen=True)
class VisualSlot:
    slot_id: str
    section_id: str
    purpose: str
    query: str
    preferred_kind: VisualKind = "any"
    required: bool = False
    caption_hint: str = ""
    source_preference: tuple[VisualSource, ...] = (
        "knowledge_base",
        "web",
    )


@dataclass(frozen=True)
class VisualBrief:
    resource_type: str
    topic: str
    outline: tuple[OutlineSection, ...]
    slots: tuple[VisualSlot, ...]

    def to_snapshot(self) -> dict:
        return {
            "resource_type": self.resource_type,
            "topic": self.topic,
            "outline": [asdict(section) for section in self.outline],
            "slots": [
                {
                    **asdict(slot),
                    "source_preference": list(slot.source_preference),
                }
                for slot in self.slots
            ],
        }


@dataclass(frozen=True)
class SelectedVisual:
    slot_id: str
    local_url: str
    title: str
    caption: str
    source_page: str
    source_type: VisualSource
    score: float


@dataclass(frozen=True)
class VisualPipelineResult:
    brief: VisualBrief
    selected: tuple[SelectedVisual, ...]
    candidate_count: int
    rejected_counts: dict[str, int]

    def to_snapshot(self) -> dict:
        return {
            "brief": self.brief.to_snapshot(),
            "selected": [asdict(item) for item in self.selected],
            "candidate_count": self.candidate_count,
            "rejected_counts": dict(self.rejected_counts),
        }
