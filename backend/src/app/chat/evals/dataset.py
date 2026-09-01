"""Schema and loader for the versioned teacher-Agent evaluation dataset."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class CapabilityFixture(BaseModel):
    source_mode: Literal["none", "course_auto", "selected_documents"] = "none"
    selected_doc_ids: list[str] = Field(default_factory=list)
    allow_rag: bool = False
    allow_web: bool = False
    allow_image_search: bool = False

    @model_validator(mode="after")
    def validate_source_authority(self):
        if self.source_mode == "selected_documents" and not self.selected_doc_ids:
            raise ValueError("selected_documents requires selected_doc_ids")
        if self.source_mode != "selected_documents":
            self.selected_doc_ids = []
        return self


class ExpectedOutcome(BaseModel):
    intent: str
    resource_types: list[str] = Field(default_factory=list)
    source_mode: Literal["none", "course_auto", "selected_documents"] = "none"
    plan_actions: list[str]
    required_tools: list[str] = Field(default_factory=list)
    tool_order: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    confirmation_policy: str | None = None
    needs_clarification: bool = False
    expected_topic_contains: list[str] = Field(default_factory=list)


class AgentEvalCase(BaseModel):
    case_id: str
    question: str
    dimensions: list[str]
    capability: CapabilityFixture = Field(default_factory=CapabilityFixture)
    state: dict[str, Any] = Field(default_factory=dict)
    expected: ExpectedOutcome
    tags: list[str] = Field(default_factory=list)


class CaseVariant(BaseModel):
    id_suffix: str
    question: str
    capability: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CaseFamily(BaseModel):
    id_prefix: str
    dimensions: list[str]
    capability: CapabilityFixture = Field(default_factory=CapabilityFixture)
    state: dict[str, Any] = Field(default_factory=dict)
    expected: ExpectedOutcome
    tags: list[str] = Field(default_factory=list)
    variants: list[CaseVariant]


class EvalDataset(BaseModel):
    schema_version: str
    dataset_id: str
    description: str = ""
    families: list[CaseFamily]

    def expand_cases(self) -> list[AgentEvalCase]:
        cases: list[AgentEvalCase] = []
        for family in self.families:
            for variant in family.variants:
                capability = _merged(
                    family.capability.model_dump(mode="python"),
                    variant.capability,
                )
                state = _merged(family.state, variant.state)
                expected = _merged(
                    family.expected.model_dump(mode="python"),
                    variant.expected,
                )
                cases.append(AgentEvalCase(
                    case_id=f"{family.id_prefix}-{variant.id_suffix}",
                    question=variant.question,
                    dimensions=list(dict.fromkeys(
                        [*family.dimensions, *variant.dimensions]
                    )),
                    capability=CapabilityFixture(**capability),
                    state=state,
                    expected=ExpectedOutcome(**expected),
                    tags=list(dict.fromkeys([*family.tags, *variant.tags])),
                ))
        return cases


def load_eval_dataset(path: str | Path) -> EvalDataset:
    dataset_path = Path(path)
    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"evaluation dataset must be an object: {dataset_path}")
    return EvalDataset.model_validate(raw)


def _merged(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merged(result[key], value)
        else:
            result[key] = value
    return result
