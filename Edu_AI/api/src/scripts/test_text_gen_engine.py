from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.chat.engines.plugin_base import GenPlugin
from app.chat.engines.text_gen_engine import TextGenEngine


class _DummySlots(BaseModel):
    topic: str | None = None


class _DummyPlugin(GenPlugin):
    @property
    def resource_type(self) -> str:
        return "report"

    @property
    def slot_class(self):
        return _DummySlots

    def needs_outline_review(self) -> bool:
        return True

    def build_outline(self, slots, context):
        return [{"title": "第1章", "points": ["要点1"]}]

    def generate_content(self, slots, outline, context) -> str:
        return "# 内容\n\n测试正文"


def run() -> None:
    engine = TextGenEngine(plugins={"report": _DummyPlugin()})

    # 1) 插件可被发现
    plugin = engine.get_plugin("report")
    assert plugin is not None
    assert plugin.resource_type == "report"

    # 2) 缺失插件应返回 None
    assert engine.get_plugin("quiz") is None

    # 3) 骨架状态流转（最小 happy path）
    state = {
        "resource_type": "report",
        "slots": {"topic": "函数"},
        "slot_collection_phase": "done",
        "outline": [],
        "outline_confirmed": False,
        "generated_content": "",
        "generation_checkpoint": {},
        "final_answer": "",
        "response_type": "text_generate",
        "messages": [],
        "meta": {},
    }

    s1 = engine.slot_collector_node(dict(state))
    assert s1["engine_stage"] in {"planning", "collecting"}

    s2 = engine.planner_node(dict(s1))
    assert isinstance(s2.get("outline", []), list)
    assert s2.get("engine_stage") == "executing"

    s3 = engine.validator_node(dict(s2))
    assert s3.get("engine_stage") in {"executing", "awaiting_human"}

    s4 = engine.executor_node(dict(s3))
    assert isinstance(s4.get("generated_content", ""), str)

    s5 = engine.analyzer_node(dict(s4))
    assert s5.get("engine_stage") in {"finished", "replanning", "awaiting_human"}

    print("text_gen_engine tests passed")


if __name__ == "__main__":
    run()
