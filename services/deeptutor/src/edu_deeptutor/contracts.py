from __future__ import annotations

import base64
import binascii
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Attachment(StrictModel):
    # Only bytes from the authenticated Edu_AI backend, never a local path/URL.
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str
    type: Literal["pdf", "image", "document"]
    base64: str = Field(min_length=1, repr=False)

    @field_validator("filename")
    @classmethod
    def basename_only(cls, value: str) -> str:
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("Attachment filename must be a basename")
        return value

    @field_validator("base64")
    @classmethod
    def valid_bytes(cls, value: str) -> str:
        try:
            data = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid attachment encoding") from exc
        if not data or len(data) > 30 * 1024 * 1024:
            raise ValueError("Attachment exceeds the 30 MiB transport limit")
        return value


class ModelSelection(StrictModel):
    profile_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)


class RuntimeModel(StrictModel):
    # Internal transport only. Never copied into upstream persisted payloads.
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: SecretStr
    supports_vision: bool = False
    api_format: Literal["openai_chat"] = "openai_chat"
    binding: Literal["openai", "deepseek"] = "openai"
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None

    @field_validator("base_url")
    @classmethod
    def configured_origin(cls, value):
        from urllib.parse import urlsplit
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Invalid configured model origin")
        return value.rstrip("/")


class ParsedSource(StrictModel):
    document_id: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=255)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser: str = Field(min_length=1)
    role: Literal["context", "template"] = "context"
    content: str = Field(min_length=1)
    content_list: list[dict] = Field(default_factory=list)
    images: dict[str, str] = Field(default_factory=dict, repr=False)

    @field_validator("images")
    @classmethod
    def safe_images(cls, value):
        total = 0
        for name, encoded in value.items():
            if "/" in name or "\\" in name or name in {".", ".."} or "\x00" in name:
                raise ValueError("Invalid asset basename")
            raw = base64.b64decode(encoded, validate=True)
            total += len(raw)
        if total > 30 * 1024 * 1024:
            raise ValueError("Parsed assets exceed transport limit")
        return value


class GenerateRequest(StrictModel):
    request_id: UUID
    checkpoint_id: UUID | None = None  # Trusted backend retry lineage; never accepted by public API.
    requirement: str = Field(min_length=1)
    mode: Literal["custom", "mimic"] = "custom"
    num_questions: int = Field(default=5, ge=1)
    question_types: list[Literal["choice", "concept", "fill_in_blank", "short_answer", "written", "coding"]] = Field(default_factory=list)
    per_type_counts: dict[str, int] = Field(default_factory=dict)
    attachments: list[Attachment] = Field(default_factory=list)
    knowledge_bases: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    model_selection: ModelSelection | None = None
    runtime_model: RuntimeModel | None = Field(default=None, repr=False)
    runtime_text_model: RuntimeModel | None = Field(default=None, repr=False)
    parsed_sources: list[ParsedSource] = Field(default_factory=list)
    language: Literal["zh", "en"] = "zh"

    @field_validator("requirement")
    @classmethod
    def meaningful_requirement(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Requirement must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def consistency(self):
        if self.per_type_counts and (
            any(k not in self.question_types or v <= 0 for k, v in self.per_type_counts.items())
            or sum(self.per_type_counts.values()) != self.num_questions
        ):
            raise ValueError("Per-type counts must match allowed types and total")
        if self.runtime_text_model and not self.runtime_model:
            raise ValueError("Text model requires an explicit runtime model")
        if self.runtime_model and self.model_selection:
            raise ValueError("Select one model configuration mechanism")
        templates = [s for s in self.parsed_sources if s.role == "template"]
        if self.mode != "mimic" and templates:
            raise ValueError("Template sources require mimic mode")
        if self.mode == "mimic":
            papers = [a for a in self.attachments if a.type == "pdf"]
            if len(papers) + len(templates) != 1:
                raise ValueError("The foundation bridge requires one explicit PDF template")
        return self

    def upstream_payload(self, allowed_tools: frozenset[str]) -> dict:
        if set(self.tools) - allowed_tools:
            raise ValueError("Requested tool is not enabled by this service")
        config = {"mode": self.mode, "num_questions": self.num_questions,
                  "question_types": self.question_types, "per_type_counts": self.per_type_counts}
        if self.mode == "mimic":
            config["max_questions"] = 0  # Patched upstream: retain all extracted questions.
        payload = {"content": self.requirement, "client_submission_id": str(self.request_id),
                   "capability": "deep_question", "language": self.language, "auto_route": False,
                   "workspace_id": "", "tools": self.tools, "knowledge_bases": self.knowledge_bases,
                   "attachments": [a.model_dump() for a in self.attachments], "config": config}
        if self.model_selection is not None:
            payload["llm_selection"] = self.model_selection.model_dump()
        if self.runtime_model:
            payload["_edu_model"] = {**self.runtime_model.model_dump(exclude={"api_key"}),
                                     "api_key": self.runtime_model.api_key.get_secret_value()}
        if self.runtime_text_model:
            payload["_edu_text_model"] = {**self.runtime_text_model.model_dump(exclude={"api_key"}),
                                            "api_key": self.runtime_text_model.api_key.get_secret_value()}
        if self.checkpoint_id:
            payload["_edu_checkpoint_id"] = str(self.checkpoint_id)
        if self.parsed_sources:
            payload["_edu_sources"] = [s.model_dump() for s in self.parsed_sources]
        return payload


def public_progress(event: dict) -> dict:
    """Allowlist projection. Text, qa_pair, results and tool payloads stay internal."""
    metadata = event.get("metadata") or {}
    stage = event.get("stage")
    labels = {"exploring": "正在整理资料", "planning": "正在规划题目", "quizzing": "正在生成题目"}
    result = {"seq": event.get("seq", 0), "type": "progress",
              "stage": stage if stage in labels else "generating",
              "message": labels.get(stage, "正在生成试卷")}
    if event.get("type") == "done":
        state = metadata.get("status")
        result.update(type="done", status=state if state in {"completed", "failed", "cancelled"} else "unknown",
                      message="生成任务已结束")
    for source, target in (("question_index", "question_index"), ("total_questions", "total_questions")):
        value = metadata.get(source)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[target] = value
    return result
