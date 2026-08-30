from __future__ import annotations

import time
import threading
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.chat.memory.domain import CandidateExtractionResult, MemoryCandidate
from app.chat.memory.settings import AgentMemorySettings


LANGMEM_CANDIDATE_INSTRUCTIONS = """
Extract only durable user preferences, stable identity/profile facts, reusable
conversation episodes, corrections, or response strategy hints. Every memory
must be supported by an exact source span from the user message. Never extract
task completion, assessment results, grades, knowledge mastery, course
membership, answer keys, permissions, or private teacher notes. Return at most
the configured number of concise standalone memories. Use profile_axis for
preferences and profile facts (for example display_name, language,
response_detail, learning_style, resource_preference).
""".strip()


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if normalized.lower() in {"", "none", "null", "n/a"}:
        return None
    return normalized


class LangMemCandidateSchema(BaseModel):
    """A proposed memory that still requires application policy approval."""

    model_config = ConfigDict(extra="forbid")

    memory_type: str = Field(
        description="preference, profile_fact, episode, correction, or strategy_hint"
    )
    content: str = Field(
        description="Concise standalone memory in the conversation language"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    source_span: str = Field(description="Exact supporting span from the user message")
    reason: str
    profile_axis: str | None = None
    expires_at: str | None = None


class LangMemAdapter:
    def __init__(
        self,
        *,
        settings: AgentMemorySettings | None = None,
        manager_factory: Callable[[], Any] | None = None,
    ):
        self.settings = settings or AgentMemorySettings.from_environment()
        self._manager_factory = manager_factory or self._build_manager
        self._manager = None
        self._invoke_lock = threading.Lock()

    def _build_manager(self):
        from langchain_openai import ChatOpenAI
        from langmem import create_memory_manager

        from core.config import Config

        model = ChatOpenAI(
            model=Config.LLM_MODEL_DEEP,
            api_key=Config.DEEP_MODEL_API_KEY,
            base_url=Config.DEEP_MODEL_API_BASE,
            timeout=max(1.0, self.settings.langmem_timeout_ms / 1000),
            max_retries=0,
            temperature=0,
        )
        return create_memory_manager(
            model,
            schemas=[LangMemCandidateSchema],
            instructions=(
                LANGMEM_CANDIDATE_INSTRUCTIONS
                + f"\nReturn no more than {self.settings.langmem_max_candidates} memories."
            ),
            enable_inserts=True,
            enable_updates=False,
            enable_deletes=False,
        )

    def extract_candidates(
        self,
        *,
        messages: list[dict],
        existing_memories: list,
        policy_hint: dict,
    ) -> CandidateExtractionResult:
        if not self.settings.langmem_enabled:
            return CandidateExtractionResult(provider="langmem", status="disabled")
        started = time.perf_counter()
        try:
            if self._manager is None:
                self._manager = self._manager_factory()
            payload: dict[str, Any] = {"messages": messages, "max_steps": 1}
            if existing_memories:
                payload["existing"] = existing_memories
            with self._invoke_lock:
                extracted = self._manager.invoke(payload)
            candidates: list[MemoryCandidate] = []
            for item in list(extracted or [])[: self.settings.langmem_max_candidates]:
                value = getattr(item, "content", item)
                raw = (
                    value.model_dump(mode="json")
                    if hasattr(value, "model_dump")
                    else {
                        key: getattr(value, key, None)
                        for key in (
                            "memory_type",
                            "content",
                            "confidence",
                            "source_span",
                            "reason",
                            "profile_axis",
                            "expires_at",
                        )
                    }
                )
                raw["provider_memory_id"] = str(getattr(item, "id", "") or "")
                raw["provider"] = "langmem"
                candidates.append(
                    MemoryCandidate(
                        memory_type=str(raw.get("memory_type") or ""),
                        content=str(raw.get("content") or ""),
                        confidence=float(raw.get("confidence") or 0.0),
                        source_span=str(raw.get("source_span") or ""),
                        reason=str(raw.get("reason") or ""),
                        profile_axis=_optional_text(raw.get("profile_axis")),
                        expires_at=_optional_text(raw.get("expires_at")),
                        supersedes_axis=(
                            str(raw.get("memory_type") or "") == "correction"
                            or any(
                                word in str(raw.get("source_span") or "")
                                for word in ("以后", "改为", "不要")
                            )
                        ),
                        raw_provider_payload=raw,
                    )
                )
            return CandidateExtractionResult(
                provider="langmem",
                status="ok",
                candidates=candidates,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
        except ValidationError as exc:
            errors = exc.errors()
            if errors and all(error.get("input") == {} for error in errors):
                return CandidateExtractionResult(
                    provider="langmem",
                    status="empty",
                    candidates=[],
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
            return CandidateExtractionResult(
                provider="langmem",
                status="error",
                candidates=[],
                latency_ms=round((time.perf_counter() - started) * 1000),
                error=str(exc),
            )
        except Exception as exc:
            return CandidateExtractionResult(
                provider="langmem",
                status="error",
                candidates=[],
                latency_ms=round((time.perf_counter() - started) * 1000),
                error=str(exc),
            )
