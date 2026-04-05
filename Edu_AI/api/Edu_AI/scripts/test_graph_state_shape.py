from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH_STATE_FILE = PROJECT_ROOT / "app" / "chat" / "graph_state.py"


def run() -> None:
    text = GRAPH_STATE_FILE.read_text(encoding="utf-8")

    required_new_fields = {
        "resource_type",
        "slots",
        "slot_meta",
        "missing_slots",
        "slot_collection_phase",
        "outline",
        "outline_confirmed",
        "generated_content",
        "generation_checkpoint",
        "search_context_hint",
        "memory_context",
    }

    for field in required_new_fields:
        assert re.search(rf"^\s*{field}:", text, re.MULTILINE), f"missing field: {field}"

    # 去重检查：关键重复字段只出现一次
    assert len(re.findall(r"^\s*need_type:", text, re.MULTILINE)) == 1
    assert len(re.findall(r"^\s*user_role_mode:", text, re.MULTILINE)) == 1

    # response_type 应包含新增值
    assert "text_generate" in text
    assert "multimodal_generate" in text

    print("graph_state shape tests passed")


if __name__ == "__main__":
    run()
