from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR_FILE = PROJECT_ROOT / "app" / "chat" / "agents" / "supervisor_agent.py"

spec = importlib.util.spec_from_file_location("supervisor_agent", SUPERVISOR_FILE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

route_after_supervisor = module.route_after_supervisor


def run() -> None:
    assert route_after_supervisor({"response_type": "chat"}) == "chat"
    assert route_after_supervisor({"response_type": "research"}) == "research"

    assert (
        route_after_supervisor({"response_type": "text_generate", "resource_type": "report"})
        == "text_generate"
    )
    assert (
        route_after_supervisor({"response_type": "multimodal_generate", "resource_type": "ppt"})
        == "ppt"
    )
    assert (
        route_after_supervisor({"response_type": "multimodal_generate", "resource_type": "video"})
        == "video"
    )
    assert (
        route_after_supervisor({"response_type": "multimodal_generate", "resource_type": "podcast"})
        == "podcast"
    )
    assert (
        route_after_supervisor({"response_type": "generate", "resource_type": "lesson_plan"})
        == "text_generate"
    )

    # 兜底行为
    assert route_after_supervisor({"response_type": "unknown"}) == "chat"

    print("supervisor routing tests passed")


if __name__ == "__main__":
    run()
