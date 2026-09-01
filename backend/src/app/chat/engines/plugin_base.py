from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type

from pydantic import BaseModel


class GenPlugin(ABC):
    """文本生成插件基类。"""

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """资源类型标识，如 report/lesson_plan。"""

    @property
    @abstractmethod
    def slot_class(self) -> Type[BaseModel]:
        """对应的槽位模型类。"""

    @abstractmethod
    def needs_outline_review(self) -> bool:
        """是否需要大纲确认。"""

    @abstractmethod
    def build_outline(self, slots: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据槽位和上下文生成结构化大纲。"""

    @abstractmethod
    def generate_content(
        self,
        slots: Dict[str, Any],
        outline: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """根据槽位与大纲生成最终内容。"""

    def post_process(self, content: str) -> str:
        """可选后处理，默认透传。"""
        return content
