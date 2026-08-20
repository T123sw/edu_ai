"""Deterministic query decomposition and evidence-coverage assessment."""
from __future__ import annotations

import re
from typing import Any

from app.chat.domain.research_bundle import (
    EvidenceCoverage,
    ResearchPlan,
    ResearchQuestion,
)


def build_research_plan(contract: Any) -> ResearchPlan:
    topic = str(_value(contract, "topic", "") or "教学主题").strip()
    intent = str(_value(contract, "intent", "qa") or "qa")
    resources = list(_value(contract, "resource_types", []) or [])
    questions = [ResearchQuestion(
        question_id="concept",
        aspect="concept",
        query=topic,
        keywords=_concept_keywords(topic),
    )]
    if intent != "qa" or resources:
        questions.extend([
            ResearchQuestion(
                question_id="pedagogy",
                aspect="pedagogy",
                query=f"{topic} 教学活动 课堂案例",
                keywords=["教学", "课堂", "活动", "案例"],
            ),
            ResearchQuestion(
                question_id="misconception",
                aspect="misconception",
                query=f"{topic} 常见错误 易错点 误区",
                keywords=["常见错误", "易错", "误区", "错误"],
            ),
            ResearchQuestion(
                question_id="assessment",
                aspect="assessment",
                query=f"{topic} 学习目标 评价 练习",
                keywords=["学习目标", "教学目标", "评价", "练习"],
            ),
        ])
    return ResearchPlan(
        topic=topic,
        primary_query=topic,
        questions=questions[:4],
        minimum_coverage=1.0 if intent == "qa" else 0.5,
        max_supplemental_queries=1,
    )


def assess_evidence_coverage(plan: ResearchPlan, evidence_text: str) -> EvidenceCoverage:
    normalized = str(evidence_text or "").lower()
    covered: list[str] = []
    missing: list[str] = []
    next_query = ""
    for question in plan.questions:
        keywords = [keyword.lower() for keyword in question.keywords if keyword]
        matched = any(keyword in normalized for keyword in keywords)
        target = covered if matched else missing
        target.append(question.aspect)
        if not matched and not next_query:
            next_query = question.query
    required_count = max(1, sum(1 for item in plan.questions if item.required))
    covered_required = sum(
        1 for item in plan.questions if item.required and item.aspect in covered
    )
    ratio = covered_required / required_count
    return EvidenceCoverage(
        coverage_ratio=round(ratio, 4),
        covered_aspects=covered,
        missing_aspects=missing,
        next_query=next_query,
        sufficient=ratio >= plan.minimum_coverage,
    )


def _value(obj: Any, name: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _concept_keywords(topic: str) -> list[str]:
    """Extract the subject from common Chinese QA wrappers.

    Coverage checks should look for the subject in evidence, not require a
    source to repeat the user's complete conversational question verbatim.
    """
    subject = re.sub(r"[？?！!。,.，：:]", " ", str(topic or "")).strip()
    leading_patterns = (
        r"^(?:请问|请|麻烦)?(?:介绍一下|介绍|讲一下|讲讲|解释一下|解释|说明一下|说明)",
        r"^(?:都)?有哪些",
        r"^什么是",
    )
    trailing_patterns = (
        r"(?:是)?如何实现$",
        r"(?:是)?怎么实现$",
        r"是怎样实现的$",
        r"是什么$",
        r"有哪些$",
        r"怎么做$",
    )
    changed = True
    while changed and subject:
        before = subject
        for pattern in leading_patterns:
            subject = re.sub(pattern, "", subject).strip()
        for pattern in trailing_patterns:
            subject = re.sub(pattern, "", subject).strip()
        changed = subject != before
    return [subject or str(topic or "教学主题").strip()]
