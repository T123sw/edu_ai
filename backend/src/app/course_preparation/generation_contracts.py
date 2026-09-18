"""Server-constructed automatic policy, distinct from workbench confirmation."""
from pydantic import Field
from .schemas import Contract, Identifier, ShortText, ResourceType


class ResourceSpec(Contract):
    node_id: Identifier
    title: ShortText
    resource_type: ResourceType
    required: bool=True
    revision: int=Field(default=1,ge=1)
    objectives: tuple[ShortText,...]=Field(min_length=1,max_length=10)
    objective_ids: tuple[Identifier,...]=Field(min_length=1,max_length=10)
    evidence: tuple[dict,...]=Field(min_length=1,max_length=40)
    language: Identifier
    audience: ShortText
    minutes: int=Field(ge=1)
    learning_check: ShortText
    memory_subject: Identifier
    memory_refs: dict=Field(default_factory=dict)
    memory_epoch: int=Field(ge=0)
    config_snapshot: dict=Field(default_factory=dict)
    revision_feedback: tuple[ShortText,...]=Field(default=(),max_length=10)
    delivery_resource_id: Identifier | None = None
    delivery_resource_version: int = Field(default=1, ge=1)
    source_resource_ref: dict | None = None
    original_content: dict | str | None = None
    preparation_policy: str='automatic_personal_draft_v1'
