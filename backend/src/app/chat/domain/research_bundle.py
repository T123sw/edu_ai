from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field


class ResearchEvidence(BaseModel):
    source_kind: Literal["rag", "web", "image"]
    summary: str = ""
    source: dict = Field(default_factory=dict)
    query: str = ""
    trust_tier: Literal["course", "authoritative_web", "external_web", "visual"] = "external_web"


class ResearchQuestion(BaseModel):
    question_id: str
    aspect: Literal["concept", "pedagogy", "misconception", "assessment"]
    query: str
    keywords: list[str] = Field(default_factory=list)
    required: bool = True


class ResearchPlan(BaseModel):
    schema_version: Literal["2026-08-09.research.v1"] = "2026-08-09.research.v1"
    topic: str
    primary_query: str
    questions: list[ResearchQuestion] = Field(default_factory=list)
    minimum_coverage: float = Field(default=0.5, ge=0.0, le=1.0)
    max_supplemental_queries: int = Field(default=1, ge=0, le=2)


class EvidenceCoverage(BaseModel):
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    covered_aspects: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)
    next_query: str = ""
    sufficient: bool = False


class ResearchBundle(BaseModel):
    schema_version: Literal["2026-08-09", "2026-08-09.research.v2"] = "2026-08-09.research.v2"
    bundle_id: str = ""
    topic: str
    source_mode: Literal["selected_documents", "course_auto", "none"] = "none"
    course_evidence: list[ResearchEvidence] = Field(default_factory=list)
    web_evidence: list[ResearchEvidence] = Field(default_factory=list)
    visual_assets: list[dict] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    quality_summary: str = ""
    missing_evidence: list[str] = Field(default_factory=list)
    research_plan: ResearchPlan | None = None
    coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)

    @property
    def context_text(self) -> str:
        blocks = [item.summary for item in [*self.course_evidence, *self.web_evidence] if item.summary]
        return "\n\n".join(blocks)[:16000]

    def with_id(self) -> "ResearchBundle":
        payload = self.model_dump(mode="json", exclude={"bundle_id"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.bundle_id = f"research-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:20]}"
        return self
