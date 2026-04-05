from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.chat.agents.supervisor_agent import route_after_supervisor
    from app.chat.graph_state import GraphState
    from app.chat.resource_type_router import ResourceTypeRouter

    # 1) 资源类型覆盖与路由映射
    text_types = {"report", "lesson_plan", "quiz", "flashcard", "blog"}
    multimodal_types = {"ppt", "video", "podcast"}

    for resource_type in sorted(text_types):
        state = {"response_type": "text_generate", "resource_type": resource_type}
        assert route_after_supervisor(state) == "text_generate", resource_type

    for resource_type in sorted(multimodal_types):
        state = {"response_type": "multimodal_generate", "resource_type": resource_type}
        expected = resource_type
        assert route_after_supervisor(state) == expected, resource_type

    # 2) fallback 行为
    assert route_after_supervisor({}) == "chat"
    assert route_after_supervisor({"response_type": "generate", "resource_type": "unknown"}) == "text_generate"

    # 3) resource_type_router 异常/空输入兜底
    router = ResourceTypeRouter(None)
    rt, source = router.classify("随便帮我生成点东西")
    assert rt == "report", (rt, source)
    assert source.startswith("fallback:"), source

    # 4) GraphState 关键字段存在
    annotations = GraphState.__annotations__
    required_fields = {
        "resource_type",
        "response_type",
        "slots",
        "slot_meta",
        "missing_slots",
        "slot_collection_phase",
    }
    missing = [f for f in required_fields if f not in annotations]
    assert not missing, f"missing fields: {missing}"

    print("phase1 integration tests passed")


if __name__ == "__main__":
    run()
