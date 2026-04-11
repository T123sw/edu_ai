from __future__ import annotations

from pydantic import BaseModel, Field


class PptSlidePlanCard(BaseModel):
    title: str
    text: str


class PptSlidePlanProcessStep(BaseModel):
    title: str
    text: str


class PptSlidePlanComparisonColumn(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)


class PptSlidePlanComparison(BaseModel):
    left: PptSlidePlanComparisonColumn
    right: PptSlidePlanComparisonColumn


class PptSlidePlanSlide(BaseModel):
    slide_index: int
    role: str
    title: str
    layout_intent: str = "bullets"
    lead: str | None = None
    bullets: list[str] = Field(default_factory=list)
    cards: list[PptSlidePlanCard] = Field(default_factory=list)
    process_steps: list[PptSlidePlanProcessStep] = Field(default_factory=list)
    comparison: PptSlidePlanComparison | None = None
    presenter_notes: str | None = None


class PptSlidePlanChapter(BaseModel):
    chapter_index: int
    chapter_title: str
    chapter_goal: str
    slides: list[PptSlidePlanSlide] = Field(default_factory=list)


class PptSlidePlan(BaseModel):
    deck_title: str
    deck_subtitle: str | None = None
    theme_id: str = "heu_academic_elegant"
    chapters: list[PptSlidePlanChapter] = Field(default_factory=list)
    slides: list[PptSlidePlanSlide] = Field(default_factory=list)
