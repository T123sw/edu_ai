"""Preparation facts and the mandatory server-side authorization port."""
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field

from .schemas import Contract, Identifier, OriginRef, PositiveVersion, PreparationRequest

PreparationStatus = Literal['accepted', 'running', 'checking', 'succeeded', 'failed', 'canceled']
PreparationStage = Literal['normalize', 'ingest', 'research_scope', 'plan', 'research_nodes',
                           'produce', 'review', 'repair', 'commit']
EventType = Literal['accepted', 'stage_changed', 'child_updated', 'check_finished',
                    'cancel_requested', 'succeeded', 'failed', 'canceled']


class PreparationSnapshot(Contract):
    schema_version: Literal[1] = 1
    preparation_id: Identifier
    status: PreparationStatus
    stage: PreparationStage
    attempt_no: PositiveVersion
    revision: PositiveVersion
    created_at: AwareDatetime
    request: PreparationRequest


class PreparationEvent(Contract):
    schema_version: Literal[1] = 1
    event_id: Identifier
    preparation_id: Identifier
    attempt_no: PositiveVersion
    sequence: PositiveVersion
    type: EventType
    revision: PositiveVersion
    occurred_at: AwareDatetime
    origin_ref: OriginRef | None = None
    payload: dict = Field(default_factory=dict)


class PreparationAuthorizer(Protocol):
    def authorize(self, owner_user_id: str, request: PreparationRequest) -> None:
        """Raise PermissionError unless all current source/target/origin refs are accessible.

        owner_user_id must come from the authenticated service, never the model.
        Implementations must enforce scope and operation, not just course visibility.
        """
        ...


class PreparationNotFound(LookupError):
    pass


class IdempotencyConflict(ValueError):
    pass
