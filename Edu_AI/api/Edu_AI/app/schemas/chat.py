from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="Question")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    top_k: int = Field(default=5, ge=1, le=20, description="Top K")
    model_id: Optional[str] = Field(default=None, description="Model ID")
    use_rag: Optional[bool] = Field(default=True, description="Use RAG")
    selected_doc_ids: Optional[List[str]] = Field(default=None, description="Selected document ids")


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: List[Dict[str, Any]]
    title: Optional[str] = None
    model_id: Optional[str] = None

