from __future__ import annotations

import re
from typing import Any


_EDIT_KEYWORDS = (
    "修改",
    "重写",
    "润色",
    "压缩",
    "扩写",
    "调整",
    "删掉",
    "补充",
    "重排",
    "改成",
    "改写",
    "优化",
    "强化",
    "精简",
    "缩短",
    "删除",
    "改",
)

_QUESTION_KEYWORDS = (
    "什么",
    "怎么",
    "为何",
    "为什么",
    "是否",
    "哪些",
    "几页",
    "多少",
    "讲了",
    "内容",
    "观点",
    "？",
    "?",
)

_GENERIC_ARTIFACT_WORDS = (
    "这个报告",
    "这份报告",
    "报告",
    "这个大纲",
    "这份大纲",
    "大纲",
    "这个ppt",
    "这份ppt",
    "ppt",
    "课件",
    "文档",
    "文件",
)

_AMBIGUOUS_TARGET_MARKERS = (
    "这里",
    "这一段",
    "这一节",
    "这一部分",
    "这部分",
    "这个部分",
    "这个地方",
    "那部分",
    "那一段",
)

_REPORT_EXACT_ANCHOR_PATTERN = re.compile(
    r"[\"'\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f].+?[\"'\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f]"
    r"|摘要|结论|总结|第\s*[0-9\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+\s*部分"
)
_PPT_PAGE_PATTERN = re.compile(
    r"第\s*[0-9\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+\s*(?:页|页面|张)|\b(?:slide|page)\s*\d+\b",
    re.IGNORECASE,
)


def _contains_edit_keyword(text: str) -> bool:
    return any(keyword in text for keyword in _EDIT_KEYWORDS)


def _looks_like_question(text: str) -> bool:
    return any(keyword in text for keyword in _QUESTION_KEYWORDS)


def _extract_freeform_anchor(text: str) -> str:
    cleaned = str(text or "").strip().lower()
    for token in _EDIT_KEYWORDS + _AMBIGUOUS_TARGET_MARKERS:
        cleaned = cleaned.replace(token, " ")
    filler_tokens = (
        "帮我",
        "一下",
        "一点",
        "一下子",
        "再",
        "更",
        "一下吧",
        "一下子",
        "成",
        "为",
        "把",
        "将",
        "请",
        "给我",
        "保留结构",
        "保持结构",
    )
    for token in filler_tokens + _GENERIC_ARTIFACT_WORDS:
        cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"[，。！？、,.!?:：\s]+", "", cleaned)
    return cleaned


def _classify_report_intent(text: str) -> dict[str, Any]:
    if not _contains_edit_keyword(text):
        return {
            "intent_class": "ask" if _looks_like_question(text) else "ask",
            "reason": "no_explicit_edit_verb",
            "requires_confirmation": False,
        }

    if _REPORT_EXACT_ANCHOR_PATTERN.search(text):
        return {
            "intent_class": "edit",
            "reason": "explicit_edit_with_structural_anchor",
            "requires_confirmation": False,
        }

    if any(marker in text for marker in _AMBIGUOUS_TARGET_MARKERS):
        return {
            "intent_class": "unclear",
            "reason": "ambiguous_target_marker",
            "requires_confirmation": True,
        }

    anchor = _extract_freeform_anchor(text)
    if anchor and anchor not in _GENERIC_ARTIFACT_WORDS:
        return {
            "intent_class": "edit",
            "reason": "explicit_edit_with_freeform_anchor",
            "requires_confirmation": False,
        }

    return {
        "intent_class": "unclear",
        "reason": "edit_without_safe_target",
        "requires_confirmation": True,
    }


def _classify_ppt_intent(text: str) -> dict[str, Any]:
    if not _contains_edit_keyword(text):
        return {
            "intent_class": "ask",
            "reason": "no_explicit_edit_verb",
            "requires_confirmation": False,
        }

    if _PPT_PAGE_PATTERN.search(text):
        return {
            "intent_class": "edit",
            "reason": "explicit_edit_with_page_anchor",
            "requires_confirmation": False,
        }

    return {
        "intent_class": "unclear",
        "reason": "ppt_edit_requires_explicit_page",
        "requires_confirmation": True,
    }


def classify_artifact_reference_intent(question: str, *, artifact_type: str = "") -> dict[str, Any]:
    text = str(question or "").strip()
    kind = str(artifact_type or "").strip()
    if not text:
        return {
            "intent_class": "ask",
            "reason": "empty_question_defaults_to_ask",
            "requires_confirmation": False,
        }

    if kind in {"ppt_deck", "ppt_outline", "ppt_content_markdown"}:
        return _classify_ppt_intent(text)
    return _classify_report_intent(text)
