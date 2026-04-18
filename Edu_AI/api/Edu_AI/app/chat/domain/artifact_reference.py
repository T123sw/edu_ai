from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ArtifactReferencePayload(BaseModel):
    artifact_id: str
    artifact_type: Literal[
        "report",
        "report_outline",
        "ppt_outline",
        "ppt_content_markdown",
        "ppt_deck",
        "lesson_plan",
        "lesson_plan_outline",
    ]
    version_id: str | None = None
    title: str | None = None
    source_conversation_id: str | None = None
    source_course_id: str | None = None

