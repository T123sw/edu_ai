from __future__ import annotations

from pydantic import BaseModel, Field


class PptOutlineSlide(BaseModel):
    slide_index: int
    role: str
    title: str
    goal: str
    key_points: list[str] = Field(default_factory=list)
    presenter_notes: str | None = None


class PptOutlineChapter(BaseModel):
    chapter_index: int
    chapter_title: str
    chapter_goal: str
    slides: list[PptOutlineSlide] = Field(default_factory=list)


class PptOutline(BaseModel):
    deck_title: str
    deck_subtitle: str | None = None
    theme_id: str = "heu_academic_elegant"
    confirmation_status: str = "pending"
    chapters: list[PptOutlineChapter] = Field(default_factory=list)
    slides: list[PptOutlineSlide] = Field(default_factory=list)

