from __future__ import annotations

import re

LEAD_MAX_CHARS = 48
BULLET_MAX_ITEMS = 4
BULLET_MAX_CHARS = 36
CARD_MAX_ITEMS = 4
CARD_TITLE_MAX_CHARS = 12
CARD_TEXT_MAX_CHARS = 32
PROCESS_MAX_STEPS = 4
PROCESS_TITLE_MAX_CHARS = 10
PROCESS_TEXT_MAX_CHARS = 30
COMPARISON_ITEM_MAX_CHARS = 30
COMPARISON_TITLE_MAX_CHARS = 12


def text_length(value: str) -> int:
    text = re.sub(r"\s+", "", str(value or ""))
    return len(text)


def comparison_item_limit(*, has_lead: bool) -> int:
    return 2 if has_lead else 3

