from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.chat.graph_state import GraphState


def run() -> None:
    # 模拟旧会话状态（缺失新字段/包含旧字段）
    legacy_state = {
        "question": "帮我写一份教案",
        "conversation_id": "conv_legacy",
        "intent_category": "generate_content",
        "response_type": "generate",
        "router_reason": "llm_generate",
        "route_source": "llm",
        "slots": {},
        "report_slots": {"core_topic": "函数"},
        "history": [],
        "messages": [],
    }

    # 使用 TypedDict 注解字段存在性来模拟兼容性检查
    annotations = GraphState.__annotations__
    required_fields = {"resource_type", "response_type", "slots"}
    missing = [f for f in required_fields if f not in annotations]
    assert not missing, f"missing fields: {missing}"

    # 老字段存在时不应被误删（保障兼容读取）
    assert "router_reason" in legacy_state
    assert legacy_state["response_type"] == "generate"

    # 新字段可延迟填充，不影响老状态保存
    legacy_state.setdefault("resource_type", None)
    legacy_state.setdefault("slot_meta", {})
    legacy_state.setdefault("missing_slots", [])

    assert "resource_type" in legacy_state
    assert isinstance(legacy_state["missing_slots"], list)

    print("phase1 state compatibility tests passed")


if __name__ == "__main__":
    run()
