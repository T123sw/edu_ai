"""Structured validation for teacher-requested learning artifacts in Markdown."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any


_HEADING_LABELS = {
    "concept_explanation": r"(?:机制讲解|概念说明)",
    "worked_case": r"完整案例",
    "exercise_with_solution": r"(?:练习|习题)",
    "lab": r"(?:实验|实训)",
}
_REQUIRED_SIGNALS = {
    "concept_explanation": ("概念", "机制", "适用范围"),
    "worked_case": ("背景", "步骤", "输入", "输出", "验证"),
    "exercise_with_solution": ("题目", "答案", "解析", "评分点", "难度", "学习目标"),
    "lab": ("环境", "步骤", "预期结果", "故障排查"),
}


def artifact_generation_instructions(deliverables: Sequence[Mapping[str, Any]]) -> str:
    instructions: list[str] = []
    for item in deliverables:
        artifact_type = str(item.get("type") or "")
        count = max(0, int(item.get("count") or 0))
        if artifact_type == "concept_explanation":
            instructions.append(
                f"严格生成 {count} 个机制讲解，标题依次使用“## 机制讲解 1”格式；"
                "每个讲解必须明确写出概念、机制和适用范围。"
            )
        elif artifact_type == "worked_case":
            instructions.append(
                f"严格生成 {count} 个完整案例，标题依次使用“## 完整案例 1”格式；"
                "每个案例必须明确写出背景、步骤、输入、输出和验证。"
            )
        elif artifact_type == "exercise_with_solution":
            instructions.append(
                f"严格生成 {count} 道练习，标题依次使用“## 练习 1”格式；"
                "每道练习必须明确写出题目、答案、解析、评分点、难度和学习目标。"
            )
        elif artifact_type == "lab":
            instructions.append(
                f"严格生成 {count} 个实验，标题依次使用“## 实验 1”格式；"
                "每个实验必须明确写出环境、步骤、预期结果和故障排查。"
            )
    return "\n".join(instructions)


def _artifact_blocks(content: str, artifact_type: str) -> list[tuple[str, str]]:
    label = _HEADING_LABELS.get(artifact_type)
    if not label:
        return []
    pattern = re.compile(
        rf"^##\s+({label})\s*(\d+)\s*$([\s\S]*?)(?=^##\s+|\Z)",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return [(match.group(2), match.group(3).strip()) for match in pattern.finditer(content)]


def validate_requested_artifacts(
    content: str,
    *,
    topic_id: str,
    deliverables: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return only schema-valid artifact records plus actionable issues."""

    artifacts: list[dict[str, Any]] = []
    issues: list[str] = []
    for specification in deliverables:
        artifact_type = str(specification.get("type") or "")
        required_count = max(0, int(specification.get("count") or 0))
        if artifact_type not in _HEADING_LABELS:
            continue
        # Models occasionally repeat the required headings in a table of
        # contents before the real section. A heading without substantive body
        # is navigation, not a second learning artifact.
        blocks = [
            (sequence, body)
            for sequence, body in _artifact_blocks(content, artifact_type)
            if len(re.sub(r"\s+", "", body)) >= 20
        ]
        if len(blocks) != required_count:
            issues.append(
                f"{artifact_type} 数量应为 {required_count}，实际识别到 {len(blocks)}"
            )
        for sequence, body in blocks[:required_count]:
            missing_signals = [
                signal for signal in _REQUIRED_SIGNALS[artifact_type] if signal not in body
            ]
            if missing_signals:
                issues.append(
                    f"{artifact_type} {sequence} 缺少字段：{'、'.join(missing_signals)}"
                )
                continue
            requirement_id = str(specification.get("requirement_id") or "")
            identity = f"{requirement_id}:{topic_id}:{artifact_type}:{sequence}"
            artifacts.append(
                {
                    "artifact_id": "artifact_"
                    + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20],
                    "requirement_id": requirement_id,
                    "topic_id": topic_id,
                    "type": artifact_type,
                    "count": 1,
                    "sequence": int(sequence),
                    "validation_status": "passed",
                    "checks": list(_REQUIRED_SIGNALS[artifact_type]),
                }
            )
    return artifacts, issues
