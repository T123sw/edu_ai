from __future__ import annotations

import json
from typing import Any


class ToolExecutionContext:
    def __init__(
        self,
        *,
        capability,
        max_steps: int,
        rag_retriever=None,
        web_retriever=None,
        workflow_registry=None,
        background_runner=None,
        agent_gateway=None,
        request=None,
        snapshot=None,
    ):
        self.capability = capability
        self.max_steps = max_steps
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever
        self.workflow_registry = workflow_registry or {}
        self.background_runner = background_runner
        self.agent_gateway = agent_gateway
        self.request = request
        self.snapshot = snapshot
        self.step_count = 0
        self.trace: dict[str, Any] = {"agent_steps": []}
        self._call_cache: dict[str, Any] = {}

    def cache_key(self, name: str, args: dict) -> str:
        return f"{name}:{json.dumps(args, ensure_ascii=False, sort_keys=True)}"

    def already_called(self, name: str, args: dict) -> bool:
        return self.cache_key(name, args) in self._call_cache

    def cache_result(self, name: str, args: dict, result: Any) -> None:
        self._call_cache[self.cache_key(name, args)] = result

    def get_cached_result(self, name: str, args: dict) -> Any:
        return self._call_cache[self.cache_key(name, args)]
