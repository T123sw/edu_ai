"""Resolve durable generation review requirements before adapting payloads."""

from collections.abc import Mapping
from typing import Any, Literal


def resolve_review_policy(value: Any) -> Literal["standard", "required"]:
    """Accept a durable command mapping or an already flattened payload.

    Required signals always win. Old persisted Harness commands without a
    policy retain their outline-based requirement; explicit standard keeps
    ordinary workbench behavior. Callers must pass the server-owned command,
    so a client preference cannot replace its required flag.
    """
    fields = value if isinstance(value, Mapping) else vars(value)
    config = fields.get("config") or {}
    if not isinstance(config, Mapping):
        config = {}
    policies = (fields.get("review_policy"), config.get("review_policy"))
    if "required" in policies or any(
        bool(source.get("harness_review_required")) for source in (fields, config)
    ):
        return "required"
    if "standard" in policies:
        return "standard"
    if any(source.get("harness_outline_id") for source in (fields, config)):
        return "required"
    return "standard"
