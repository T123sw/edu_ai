from __future__ import annotations

from app.chat.domain.report_preparation import ReportPreparationResult


class GenerationReadinessJudge:
    """Judge whether current prepared context is sufficient for a first report draft."""

    def judge(self, result: ReportPreparationResult, *, entry_mode: str) -> dict:
        if not str(result.report_subject or "").strip():
            return {
                "action": "ask_critical_gap",
                "missing_critical_fields": ["report_subject"],
            }

        has_focus = bool(str(result.report_focus or "").strip())
        has_key_points = len(list(result.key_points or [])) >= 2
        has_evidence = len(list(result.evidence_points or [])) >= 2
        has_summary = bool(str(result.report_context_summary.subject_summary or "").strip())

        if has_focus or has_key_points or has_evidence or has_summary:
            action = "weak_soft_confirm" if str(entry_mode or "").strip().lower() == "button" else "strong_soft_confirm"
            return {
                "action": action,
                "missing_critical_fields": [],
            }

        return {
            "action": "ask_critical_gap",
            "missing_critical_fields": ["report_focus"],
        }
