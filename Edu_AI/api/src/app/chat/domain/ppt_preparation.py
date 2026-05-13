from __future__ import annotations

from pydantic import BaseModel, Field


class PptPreparationResult(BaseModel):
    intent: str = "generate_outline"
    topic: str | None = None
    audience: str | None = None
    objective: str | None = None
    key_points: list[str] = Field(default_factory=list)
    source_basis: list[str] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)
    style: str | None = None
    theme: str | None = None
    page_count: int | None = None
    missing_core_fields: list[str] = Field(default_factory=list)
    followup_question: str = ""
    assumptions: list[str] = Field(default_factory=list)
    preparation_source: str = ""
    preparation_model: str = ""

    @property
    def deck_topic(self) -> str | None:
        return self.topic

    @property
    def theme_id(self) -> str | None:
        return self.theme

    @property
    def slide_count(self) -> int | None:
        return self.page_count
