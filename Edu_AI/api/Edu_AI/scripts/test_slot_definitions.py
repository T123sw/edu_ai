from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SLOT_FILE = PROJECT_ROOT / "app" / "chat" / "slot_definitions.py"

spec = importlib.util.spec_from_file_location("slot_definitions", SLOT_FILE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

SLOT_REGISTRY = module.SLOT_REGISTRY


def run() -> None:
    expected_types = {
        "report",
        "lesson_plan",
        "quiz",
        "flashcard",
        "blog",
        "ppt",
        "video",
        "podcast",
    }

    assert set(SLOT_REGISTRY.keys()) == expected_types, SLOT_REGISTRY.keys()

    for resource_type, model_cls in SLOT_REGISTRY.items():
        slot_obj = model_cls()
        assert hasattr(model_cls, "SlotMeta"), resource_type

        core_slots = getattr(model_cls.SlotMeta, "core_slots", None)
        secondary_slots = getattr(model_cls.SlotMeta, "secondary_slots", None)
        defaults = getattr(model_cls.SlotMeta, "defaults", None)

        assert isinstance(core_slots, list), f"{resource_type}: core_slots missing"
        assert isinstance(secondary_slots, list), f"{resource_type}: secondary_slots missing"
        assert isinstance(defaults, dict), f"{resource_type}: defaults missing"

        data = slot_obj.model_dump()
        for key in core_slots + secondary_slots:
            assert key in data, f"{resource_type}: {key} not in model fields"

    print("slot_definitions tests passed")


if __name__ == "__main__":
    run()
