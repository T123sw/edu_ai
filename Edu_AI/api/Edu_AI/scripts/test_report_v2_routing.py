from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.chat.agents.universal_report_engine import focus_router, outliner_router

    # 1) focus 评估通过后，必须先进入 confirmer
    s_focus_ok = {"focus_sufficient": True}
    assert focus_router(s_focus_ok) == "confirmer"

    s_focus_bad = {"focus_sufficient": False}
    assert focus_router(s_focus_bad) == "asker"

    # 2) 用户确认大纲后，本轮应直达 generator
    s_outline_confirmed = {
        "outline_confirmed": True,
        "phase": "generating",
        "status": "executing",
    }
    assert outliner_router(s_outline_confirmed) == "generator"

    # 3) 其他情况应结束本轮等待用户
    s_outline_wait = {
        "outline_confirmed": False,
        "phase": "outlining",
        "status": "awaiting_human",
    }
    assert outliner_router(s_outline_wait) == "__end__"

    print("report v2 routing tests passed")


if __name__ == "__main__":
    run()
