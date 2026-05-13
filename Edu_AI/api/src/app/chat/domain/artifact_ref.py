from __future__ import annotations

from pydantic import BaseModel


class ArtifactRef(BaseModel):
    artifact_id: str
    artifact_type: str
    title: str | None = None

