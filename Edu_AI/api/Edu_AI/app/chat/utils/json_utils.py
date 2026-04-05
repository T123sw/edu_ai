from __future__ import annotations

import json
import re
from typing import Any, Dict


def coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value).strip()


def extract_json_block(text: str) -> Any:
    raw = str(text or "").strip()
    if not raw:
        return {}

    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        pass

    arr_start = raw.find("[")
    arr_end = raw.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        try:
            return json.loads(raw[arr_start:arr_end + 1])
        except Exception:
            pass

    obj_start = raw.find("{")
    obj_end = raw.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        try:
            return json.loads(raw[obj_start:obj_end + 1])
        except Exception:
            return {}
    return {}


def read_report_schema(report_slot_schema: str) -> Dict[str, Any]:
    try:
        parsed = extract_json_block(report_slot_schema)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
