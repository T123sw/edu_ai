"""Generate auditable Chinese fallback material for a single leaf knowledge point."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


MIN_GENERATED_MATERIAL_LENGTH = 800
MIN_REVIEW_SCORE = 80


@dataclass(frozen=True)
class ReviewedSupplement:
    title: str
    content: str
    review_score: int
    approved: bool
    issues: tuple[str, ...]
    audit: dict[str, Any]


def _clean_model_text(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _structural_issues(content: str, leaf_title: str) -> list[str]:
    issues: list[str] = []
    if len(content) < MIN_GENERATED_MATERIAL_LENGTH:
        issues.append(f"正文不足 {MIN_GENERATED_MATERIAL_LENGTH} 字符")
    if len(re.findall(r"^##\s+", content, flags=re.MULTILINE)) < 3:
        issues.append("至少需要三个二级章节")
    if leaf_title not in content:
        issues.append("正文未明确覆盖目标知识点")
    if re.search(r"https?://|www\.", content, flags=re.IGNORECASE):
        issues.append("模型补充材料不得虚构或附带外部链接")
    if re.search(r"(?:参考文献|引用来源|许可证|license)\s*[:：]", content, flags=re.IGNORECASE):
        issues.append("模型补充材料不得虚构引用或许可信息")
    return issues


def _parse_review(value: object) -> tuple[int, bool, tuple[str, ...]]:
    text = _clean_model_text(value)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return 0, False, ("质量审查未返回 JSON",)
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return 0, False, ("质量审查 JSON 无法解析",)
    score = max(0, min(100, int(payload.get("score") or 0)))
    issues = tuple(str(item) for item in payload.get("issues") or [] if str(item).strip())
    approved = bool(payload.get("approved")) and score >= MIN_REVIEW_SCORE and not issues
    return score, approved, issues


def generate_reviewed_supplement(
    *,
    course_title: str,
    leaf_title: str,
    sequence: int,
    call_model: Callable[[str], str],
) -> ReviewedSupplement:
    title = f"{leaf_title}学习材料（AI 补充 {sequence}）"
    last_issues: tuple[str, ...] = ()
    last_score = 0
    for attempt in range(1, 3):
        generation_prompt = f"""
你是课程知识库资料编写专家。请为课程《{course_title}》的叶级知识点“{leaf_title}”编写一份独立、准确、可教学的中文 Markdown 学习材料。

硬性要求：
1. 正文不少于 {MIN_GENERATED_MATERIAL_LENGTH} 个字符，标题为“# {leaf_title}学习材料”。
2. 至少包含“概念说明、示例或步骤、常见错误、练习与小结”中的三个二级章节。
3. 内容必须紧扣该知识点，示例可执行或可验证，适合独立入库检索。
4. 不得编造网址、参考文献、引用、作者或许可证；不要声称内容来自某个外部来源。
5. 只输出 Markdown 正文，不要输出写作说明。

这是第 {attempt} 次生成；资料序号为 {sequence}。
""".strip()
        content = _clean_model_text(call_model(generation_prompt))
        structural = tuple(_structural_issues(content, leaf_title))
        if structural:
            last_issues = structural
            continue
        review_prompt = f"""
你是独立的课程资料质量审查员，不是原作者。请审查下面这份面向“{leaf_title}”的材料。
按准确性 35 分、知识点覆盖 25 分、教学结构 20 分、示例与练习 20 分评分。若存在事实错误、偏题、虚构引用或不可用示例，approved 必须为 false。
只返回 JSON：{{"score": 0-100, "approved": true/false, "issues": ["问题"]}}。

材料：
{content}
""".strip()
        score, approved, review_issues = _parse_review(call_model(review_prompt))
        last_score, last_issues = score, review_issues
        if approved:
            return ReviewedSupplement(
                title=title,
                content=content,
                review_score=score,
                approved=True,
                issues=(),
                audit={
                    "generation_attempts": attempt,
                    "review_score": score,
                    "review_threshold": MIN_REVIEW_SCORE,
                    "review_method": "independent_model_review",
                },
            )
    raise ValueError(
        f"模型补充资料未通过质量审查（score={last_score}, issues={list(last_issues)}）"
    )
