from __future__ import annotations

from typing import Any, Dict, Optional

from .plugin_base import GenPlugin


class TextGenEngine:
    """文本统一生成引擎（Phase 2 骨架版）。"""

    def __init__(self, plugins: Optional[Dict[str, GenPlugin]] = None):
        self._plugins: Dict[str, GenPlugin] = dict(plugins or {})

    def register_plugin(self, plugin: GenPlugin) -> None:
        self._plugins[plugin.resource_type] = plugin

    def get_plugin(self, resource_type: str) -> Optional[GenPlugin]:
        return self._plugins.get(str(resource_type or "").strip())

    def slot_collector_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        phase = str(state.get("slot_collection_phase") or "collecting")
        if phase == "done":
            state["engine_stage"] = "planning"
        else:
            state["engine_stage"] = "collecting"
        return state

    def planner_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plugin = self.get_plugin(str(state.get("resource_type") or ""))
        if not plugin:
            state["engine_stage"] = "awaiting_human"
            state["final_answer"] = "未找到对应资源类型的生成插件，请稍后重试。"
            return state

        slots = state.get("slots") if isinstance(state.get("slots"), dict) else {}
        context = {"state": state}

        try:
            outline = plugin.build_outline(slots, context)
            state["outline"] = outline if isinstance(outline, list) else []
            state["engine_stage"] = "executing"
        except Exception as exc:
            state["engine_stage"] = "awaiting_human"
            state["final_answer"] = f"规划阶段失败：{exc}"
        return state

    def validator_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plugin = self.get_plugin(str(state.get("resource_type") or ""))
        if not plugin:
            state["engine_stage"] = "awaiting_human"
            return state

        outline = state.get("outline") if isinstance(state.get("outline"), list) else []
        if plugin.needs_outline_review() and not outline:
            state["engine_stage"] = "awaiting_human"
            state["final_answer"] = "大纲为空，请补充需求后重试。"
            return state

        state["engine_stage"] = "executing"
        return state

    def executor_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plugin = self.get_plugin(str(state.get("resource_type") or ""))
        if not plugin:
            state["engine_stage"] = "awaiting_human"
            return state

        slots = state.get("slots") if isinstance(state.get("slots"), dict) else {}
        outline = state.get("outline") if isinstance(state.get("outline"), list) else []
        context = {"state": state}

        try:
            content = plugin.generate_content(slots, outline, context)
            final_content = plugin.post_process(str(content or ""))
            state["generated_content"] = final_content
            state["generation_checkpoint"] = {
                "plugin": plugin.resource_type,
                "outline_size": len(outline),
                "generated": bool(final_content.strip()),
            }
            state["engine_stage"] = "reviewing"
        except Exception as exc:
            state["engine_stage"] = "replanning"
            state["final_answer"] = f"执行阶段失败：{exc}"
        return state

    def analyzer_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        content = str(state.get("generated_content") or "").strip()
        if content:
            state["engine_stage"] = "finished"
            state["final_answer"] = content
        else:
            state["engine_stage"] = "replanning"
        return state
