from __future__ import annotations

import re


_EDIT_KEYWORDS = (
    "\u4fee\u6539",
    "\u91cd\u5199",
    "\u6da6\u8272",
    "\u538b\u7f29",
    "\u6269\u5199",
    "\u8c03\u6574",
    "\u5220\u6389",
    "\u8865\u5145",
    "\u91cd\u6392",
    "\u6539",
)

_SLIDE_REFERENCE_PATTERN = re.compile(
    r"(\u7b2c\s*[0-9\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+\s*[\u9875\u9875\u9762\u5f20]|\b(?:slide|page)\s*\d+\b)",
    re.IGNORECASE,
)


def classify_artifact_reference_intent(question: str) -> str:
    text = str(question or "").strip()
    if not text:
        return "ask_about_artifact"

    if any(keyword in text for keyword in _EDIT_KEYWORDS):
        return "edit_artifact"

    normalized = text.lower()
    if _SLIDE_REFERENCE_PATTERN.search(normalized) and any(keyword in text for keyword in _EDIT_KEYWORDS):
        return "edit_artifact"

    return "ask_about_artifact"
