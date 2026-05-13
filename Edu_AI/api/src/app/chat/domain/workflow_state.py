from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowState(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str
    stage: str
    required_slots: list[str] = Field(default_factory=list)
    filled_slots: dict[str, str] = Field(default_factory=dict)
    artifacts: list[dict] = Field(default_factory=list)
    resume_token: str = ""

