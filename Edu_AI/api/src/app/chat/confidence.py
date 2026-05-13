from __future__ import annotations

from typing import Any, Dict


class ConfidenceScorer:
    """基于可观察信号的轻量置信度评分。"""

    @staticmethod
    def score(*, slots: Dict[str, str], clarify_result: Dict[str, Any], used_clarification: bool) -> Dict[str, Any]:
        topic = bool(str((slots or {}).get("topic", "") or "").strip())
        objective = bool(str((slots or {}).get("objective", "") or "").strip())
        audience = bool(str((slots or {}).get("audience", "") or "").strip())

        base = 0.45
        if topic:
            base += 0.20
        if objective:
            base += 0.20
        if audience:
            base += 0.10
        if used_clarification:
            base += 0.05

        if bool((clarify_result or {}).get("needs_clarification")):
            base -= 0.15

        score = max(0.05, min(0.99, base))
        if score >= 0.78:
            level = "high"
            reason = "上下文较完整，关键信息清晰。"
        elif score >= 0.58:
            level = "medium"
            reason = "核心信息基本够用，但仍有可补充项。"
        else:
            level = "low"
            reason = "关键信息不足，回答可能偏泛。"

        return {
            "confidence_score": round(score, 2),
            "confidence_level": level,
            "confidence_reason": reason,
        }
