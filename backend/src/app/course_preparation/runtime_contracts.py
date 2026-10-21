"""Runtime authority and accounting, never supplied by model arguments."""
from dataclasses import dataclass
from typing import Callable
from pydantic import Field
from .schemas import Contract, Identifier, Operation


class BudgetCost(Contract):
    calls: int = Field(default=0, ge=0, strict=True)
    tokens: int = Field(default=0, ge=0, strict=True)
    cost_micro_usd: int = Field(default=0, ge=0, strict=True)


class BudgetLimits(BudgetCost):
    retry_only: bool = False
    calls: int = Field(default=200, ge=1, strict=True)
    tokens: int = Field(default=2_000_000, ge=1, strict=True)
    cost_micro_usd: int = Field(default=10_000_000, ge=0, strict=True)
    seconds: int = Field(default=3600, ge=1, le=86400, strict=True)


def budget_deadline(budget):
    """The non-null legacy DB timestamp is inactive under retry-only policy."""
    from .repository import aware
    return None if budget.limits.get('retry_only') else aware(budget.deadline)


def remaining_seconds(deadline):
    from datetime import datetime, timezone
    return float('inf') if deadline is None else (datetime.fromisoformat(deadline) - datetime.now(timezone.utc)).total_seconds()


class ExecutionContext(Contract):
    preparation_id: Identifier
    attempt_no: int
    owner_user_id: Identifier
    lease_token: Identifier
    revision: int
    stage: str
    operation: Operation
    source_policy: str
    checkpoint: dict = Field(default_factory=dict)
    capabilities: tuple[str, ...] = ()
    deadline: str | None = None


class ToolCall(Contract):
    call_id: Identifier
    name: Identifier
    arguments: dict


@dataclass(frozen=True)
class ToolSpec:
    name: str
    arguments: type[Contract]
    handler: Callable
    stages: tuple[str, ...] = ()
    operations: tuple[str, ...] = ('create_course', 'supplement_node', 'revise_resource', 'adjust_course')
    readonly: bool = True
    network: bool = False
    capability: str | None = None
    cost: BudgetCost = BudgetCost(calls=1)
    reconcile: Callable | None = None


@dataclass(frozen=True)
class MountedTools:
    tools: tuple[ToolSpec, ...]
    digest: str
    schemas: tuple[dict, ...]
