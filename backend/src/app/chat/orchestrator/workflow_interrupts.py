from __future__ import annotations


INTERRUPT_KEYWORDS = ("算了", "别继续", "重新开始", "先帮我", "顺便查一下")
REWRITE_COMMANDS = {"再正式一点", "缩短一点", "换个说法", "加上案例"}


def should_interrupt_workflow(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(keyword in normalized for keyword in INTERRUPT_KEYWORDS)


def is_rewrite_command(text: str) -> bool:
    return str(text or "").strip() in REWRITE_COMMANDS


def interrupt_reason(text: str) -> str | None:
    normalized = str(text or "").strip()
    for keyword in INTERRUPT_KEYWORDS:
        if keyword in normalized:
            return keyword
    return None
