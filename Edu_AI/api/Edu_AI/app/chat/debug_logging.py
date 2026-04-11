from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR = _PROJECT_ROOT / "storage" / "logs"


def _compact_for_console(value: Any, *, max_length: int = 240, max_items: int = 6) -> Any:
    if isinstance(value, str):
        compact = " ".join(value.split())
        if len(compact) > max_length:
            return f"{compact[:max_length]}...(+{len(compact) - max_length} chars)"
        return compact
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                compact["__truncated__"] = f"{len(value) - max_items} more keys"
                break
            compact[key] = _compact_for_console(item, max_length=max_length, max_items=max_items)
        return compact
    if isinstance(value, list):
        compact_items = [
            _compact_for_console(item, max_length=max_length, max_items=max_items)
            for item in value[:max_items]
        ]
        if len(value) > max_items:
            compact_items.append(f"...(+{len(value) - max_items} items)")
        return compact_items
    return value


def append_debug_log(log_name: str, *, event: str, echo: bool = False, **payload: Any) -> None:
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = _LOG_DIR / f"{log_name}.log"
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        if echo:
            console_record = {
                "event": event,
                **{key: _compact_for_console(value) for key, value in payload.items()},
            }
            print(f"[debug:{log_name}] {json.dumps(console_record, ensure_ascii=False)}")
    except Exception:
        # Debug logging must never break the main workflow.
        return
