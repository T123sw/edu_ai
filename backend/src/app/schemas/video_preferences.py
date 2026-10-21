"""Explicit video choices, distinct from shared learning-time estimates."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class VideoPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target_minutes: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    duration_mode: Literal['target', 'maximum', 'exact'] = 'target'
    narration: bool | None = None
    voice: str | None = None
    aspect: Literal['16:9', '9:16', '1:1', '4:3'] | None = None
    teaching_style: str | None = None
    scene_count: int | None = Field(default=None, ge=1)
