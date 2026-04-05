from __future__ import annotations

import re
from typing import Any, Dict


def render_prompt_template(template: str, values: Dict[str, Any]) -> str:
    text = str(template or "")
    for k, v in (values or {}).items():
        text = text.replace("{" + str(k) + "}", str(v if v is not None else ""))
    return text


def strip_trailing_questions(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    lines = [ln.rstrip() for ln in t.splitlines()]
    while lines and (not lines[-1].strip() or lines[-1].strip().endswith(("?", "？"))):
        lines.pop()
    return "\n".join(lines).strip() or t


def smooth_followup_transition(prefix: str, followup: str) -> str:
    p = str(prefix or "").strip()
    f = str(followup or "").strip()
    if not p:
        return f
    if not f:
        return p
    if re.search(r"[。！？!?]$", p):
        return f"{p}\n{f}"
    return f"{p}。\n{f}"
