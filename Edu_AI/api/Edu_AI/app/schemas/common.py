from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    message: str
    knowledge_base_ready: bool
    document_count: int


class ModelInfo(BaseModel):
    id: str
    name: str
    model_name: Optional[str] = None

