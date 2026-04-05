from __future__ import annotations

import importlib.util
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_BASE_PATH = PROJECT_ROOT / "app" / "chat" / "engines" / "plugin_base.py"

spec = importlib.util.spec_from_file_location("plugin_base", PLUGIN_BASE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
GenPlugin = module.GenPlugin


class _DummySlots(BaseModel):
    topic: str | None = None


class _GoodPlugin(GenPlugin):
    @property
    def resource_type(self) -> str:
        return "report"

    @property
    def slot_class(self):
        return _DummySlots

    def needs_outline_review(self) -> bool:
        return True

    def build_outline(self, slots, context):
        return [{"title": "章节1", "points": ["要点1"]}]

    def generate_content(self, slots, outline, context) -> str:
        return "# 报告\n\n内容"


class _BadPlugin(GenPlugin):
    @property
    def resource_type(self) -> str:
        return "report"


def run() -> None:
    plugin = _GoodPlugin()
    assert plugin.resource_type == "report"
    assert plugin.slot_class is _DummySlots
    assert plugin.needs_outline_review() is True
    assert isinstance(plugin.build_outline({}, {}), list)
    assert isinstance(plugin.generate_content({}, [], {}), str)
    assert plugin.post_process("abc") == "abc"

    failed = False
    try:
        _BadPlugin()
    except TypeError:
        failed = True
    assert failed, "abstract plugin should not be instantiable"

    print("plugin_base tests passed")


if __name__ == "__main__":
    run()
