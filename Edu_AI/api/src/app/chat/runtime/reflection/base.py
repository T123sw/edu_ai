from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ReflectVerdict:
    verdict: Literal["pass", "pass_with_warning", "retry", "replan", "abort"]
    hint: str = ""
    severity: Literal["info", "warning", "blocking"] = "info"
    filtered_data: dict = field(default_factory=dict)


class BaseReflector(ABC):
    priority: int = 0  # lower runs first

    @abstractmethod
    def applies_to(self, tool_name: str) -> bool: ...

    @abstractmethod
    def evaluate(
        self,
        tool_name: str,
        result: dict,
        state: dict,
        step_constraints: dict,
    ) -> ReflectVerdict: ...
