from __future__ import annotations

import json
from typing import Any

from app.chat.domain.report_preparation import ReportContextSummary, ReportPreparationResult


class ReportContextOrganizer:
    _LOW_SIGNAL_VALUES = {
        "",
        "具体一点",
        "详细一点",
        "展开一点",
        "介绍下整个过程",
        "介绍整个过程",
        "整个过程",
        "继续分析",
        "继续生成",
        "请基于当前内容生成一份报告",
        "生成一份报告",
        "帮我生成一份报告",
    }

    def __init__(self, *, llm: Any | None = None):
        self.llm = llm

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip().strip("。！？!?")

    def _is_low_signal(self, value: Any) -> bool:
        text = self._clean(value)
        if not text:
            return True
        if text in self._LOW_SIGNAL_VALUES:
            return True
        if text.startswith("比如"):
            return True
        if text.endswith("过程") and len(text) <= 8:
            return True
        if text.endswith("一点") and len(text) <= 8:
            return True
        return False

    @staticmethod
    def _looks_like_report_intent(*, request_question: str, context) -> bool:
        question = str(request_question or "").strip()
        if "报告" in question:
            return True
        return "生成报告" in "".join(list(getattr(context, "user_goals", []) or []))

    def _extract_subject_from_report_request(self, request_question: str) -> str | None:
        text = self._clean(request_question)
        if not text or "报告" not in text:
            return None

        patterns = (
            r"(?:围绕|关于|针对|聚焦|就)(?P<subject>.+?)(?:生成|整理|输出|写)(?:一份|一个)?(?:分析)?报告",
            r"(?:生成|整理|输出|写)(?:一份|一个)?(?:关于|围绕|针对)(?P<subject>.+?)(?:的)?(?:分析)?报告",
        )
        for pattern in patterns:
            match = __import__("re").search(pattern, text)
            if not match:
                continue
            subject = self._clean(match.group("subject"))
            if subject and not self._is_low_signal(subject):
                return subject
        return None

    def _resolve_subject(self, *, context, request_question: str, candidate_subject: str | None = None) -> str | None:
        candidate = self._clean(candidate_subject or "")
        if candidate and not self._is_low_signal(candidate):
            extracted = self._extract_subject_from_report_request(candidate)
            if extracted:
                return extracted
            if "报告" not in candidate:
                return candidate

        request_subject = self._extract_subject_from_report_request(request_question)
        if request_subject:
            return request_subject

        fallback_subject = self._pick_subject(context=context)
        if fallback_subject and not self._is_low_signal(fallback_subject):
            return fallback_subject
        return None

    def _resolve_focus(self, *, context, report_subject: str | None, candidate_focus: str | None = None) -> str | None:
        candidate = self._clean(candidate_focus or "")
        if candidate and not self._is_low_signal(candidate):
            return candidate
        return self._pick_focus(context=context, report_subject=report_subject)

    def _build_missing_fields(self, *, report_intent: str, report_subject: str | None) -> list[str]:
        missing: list[str] = []
        if report_intent != "generate_report":
            missing.append("report_intent")
        if not str(report_subject or "").strip():
            missing.append("report_subject")
        return missing

    def _build_followups(self, *, missing: list[str]) -> list[str]:
        if "report_subject" in list(missing or []):
            return ["你希望这份报告围绕哪个主题来写？"]
        if "report_intent" in list(missing or []):
            return ["你是想继续分析，还是现在直接生成报告？"]
        return []

    def _build_confidence(
        self,
        *,
        report_subject: str | None,
        report_focus: str | None,
        key_points: list[str],
        evidence_points: list[dict],
    ) -> str:
        if report_subject and (report_focus or len(key_points) >= 2 or len(evidence_points) >= 2):
            return "high"
        if report_subject:
            return "medium"
        return "low"

    def _sanitize_result(self, *, context, request_question: str, raw_result: ReportPreparationResult) -> ReportPreparationResult:
        report_intent = "generate_report" if self._looks_like_report_intent(request_question=request_question, context=context) else str(raw_result.report_intent or "").strip() or "unclear"
        report_subject = self._resolve_subject(
            context=context,
            request_question=request_question,
            candidate_subject=raw_result.report_subject,
        )
        report_focus = self._resolve_focus(
            context=context,
            report_subject=report_subject,
            candidate_focus=raw_result.report_focus,
        )
        key_points = list(raw_result.key_points or []) or self._pick_key_points(context=context)
        evidence_points = list(raw_result.evidence_points or []) or list(getattr(context, "evidence_points", []) or [])[:3]
        constraints = dict(raw_result.constraints or {}) or dict(getattr(context, "constraints", {}) or {})
        source_scope, source_labels = self._build_source_scope(context=context)
        missing = self._build_missing_fields(report_intent=report_intent, report_subject=report_subject)
        followups = self._build_followups(missing=missing)
        confidence = self._build_confidence(
            report_subject=report_subject,
            report_focus=report_focus,
            key_points=key_points,
            evidence_points=evidence_points,
        )
        summary = ReportContextSummary(
            subject_summary=self._clean(getattr(context, "summary_text", "") or report_subject or ""),
            focus_summary=self._clean(report_focus or ""),
            key_points=key_points,
            evidence_points=evidence_points,
            constraints=constraints,
            source_scope=source_labels,
        )
        return raw_result.model_copy(
            update={
                "report_intent": report_intent,
                "report_subject": report_subject,
                "report_focus": report_focus,
                "report_context_summary": summary,
                "key_points": key_points,
                "evidence_points": evidence_points,
                "constraints": constraints,
                "source_scope": source_scope,
                "missing_critical_fields": missing,
                "confidence": confidence,
                "soft_confirm_message": self._build_soft_confirm_message(subject=report_subject, focus=report_focus),
                "followup_candidates": followups,
            }
        )

    def _pick_subject(self, *, context) -> str | None:
        for topic in list(getattr(context, "current_topics", []) or []):
            text = self._clean(topic)
            if text and not self._is_low_signal(text):
                return text

        for message in list(getattr(context, "recent_relevant_messages", []) or []):
            if str((message or {}).get("role") or "").strip() != "user":
                continue
            text = self._clean((message or {}).get("content") or "")
            if text and not self._is_low_signal(text):
                return text

        summary = self._clean(getattr(context, "summary_text", "") or "")
        return summary or None

    def _pick_focus(self, *, context, report_subject: str | None) -> str | None:
        for key in ("teaching_issues", "student_signals"):
            for item in list(getattr(context, key, []) or []):
                text = self._clean(item)
                if text and not self._is_low_signal(text):
                    return text
        if report_subject:
            return f"综合分析{report_subject}下的主要问题与结论"
        return None

    def _pick_key_points(self, *, context) -> list[str]:
        points: list[str] = []
        for item in list(getattr(context, "confirmed_facts", []) or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
            if len(points) >= 3:
                return points
        for item in list(getattr(context, "evidence_points", []) or []):
            if not isinstance(item, dict):
                continue
            text = self._clean(item.get("content") or "")
            if text and text not in points:
                points.append(text)
            if len(points) >= 3:
                return points
        return points

    def _build_source_scope(self, *, context) -> tuple[dict, list[str]]:
        raw_scope = dict(getattr(context, "source_scope", {}) or {})
        structured_scope = {
            "from_conversation": bool(raw_scope.get("from_recent_messages") or raw_scope.get("from_summary") or raw_scope.get("from_memory")),
            "from_docs": bool(raw_scope.get("from_docs")),
            "from_course": bool(getattr(context, "current_course_id", None)),
            "from_artifacts": bool(raw_scope.get("from_artifacts")),
        }
        labels = [key for key, enabled in structured_scope.items() if enabled]
        return structured_scope, labels

    def _build_soft_confirm_message(self, *, subject: str | None, focus: str | None) -> str:
        if not subject:
            return ""
        focus_text = self._clean(focus or "") or f"综合分析{subject}下的主要问题与结论"
        return f"我将基于“{subject}”，重点围绕“{focus_text}”，结合当前对话内容先生成一版报告。可以直接开始吗？"

    def _fallback_prepare(self, *, context, request_question: str) -> ReportPreparationResult:
        question = self._clean(request_question)
        combined_goals = "".join(list(getattr(context, "user_goals", []) or []))
        report_intent = "generate_report" if ("报告" in question or "生成报告" in combined_goals) else "unclear"
        report_subject = self._resolve_subject(context=context, request_question=request_question)
        report_focus = self._resolve_focus(context=context, report_subject=report_subject)
        key_points = self._pick_key_points(context=context)
        evidence_points = list(getattr(context, "evidence_points", []) or [])[:3]
        constraints = dict(getattr(context, "constraints", {}) or {})
        source_scope, source_labels = self._build_source_scope(context=context)

        missing = self._build_missing_fields(report_intent=report_intent, report_subject=report_subject)
        followups = self._build_followups(missing=missing)

        summary = ReportContextSummary(
            subject_summary=self._clean(getattr(context, "summary_text", "") or report_subject or ""),
            focus_summary=self._clean(report_focus or ""),
            key_points=key_points,
            evidence_points=evidence_points,
            constraints=constraints,
            source_scope=source_labels,
        )

        confidence = self._build_confidence(
            report_subject=report_subject,
            report_focus=report_focus,
            key_points=key_points,
            evidence_points=evidence_points,
        )

        return ReportPreparationResult(
            report_intent=report_intent,
            report_subject=report_subject,
            report_focus=report_focus,
            report_context_summary=summary,
            key_points=key_points,
            evidence_points=evidence_points,
            constraints=constraints,
            source_scope=source_scope,
            open_questions=[],
            missing_critical_fields=missing,
            confidence=confidence,
            soft_confirm_message=self._build_soft_confirm_message(subject=report_subject, focus=report_focus),
            followup_candidates=followups,
        )

    def organize(self, *, context, request_question: str) -> ReportPreparationResult:
        if self.llm is not None:
            try:
                prompt = (
                    "你是报告工作流入口的上下文整理器。请根据给定上下文，产出一份结构化的报告准备结果。"
                    "如果 report_subject 明确但 focus 不明确，可以补出综合型 focus。"
                    "只在 report_intent 或 report_subject 缺失时标记为关键缺口。\n\n"
                    f"request_question={request_question}\n"
                    f"summary={getattr(context, 'summary_text', '')}\n"
                    f"current_topics={json.dumps(list(getattr(context, 'current_topics', []) or []), ensure_ascii=False)}\n"
                    f"user_goals={json.dumps(list(getattr(context, 'user_goals', []) or []), ensure_ascii=False)}\n"
                    f"confirmed_facts={json.dumps(list(getattr(context, 'confirmed_facts', []) or []), ensure_ascii=False)}\n"
                    f"constraints={json.dumps(dict(getattr(context, 'constraints', {}) or {}), ensure_ascii=False)}\n"
                    f"teaching_issues={json.dumps(list(getattr(context, 'teaching_issues', []) or []), ensure_ascii=False)}\n"
                    f"student_signals={json.dumps(list(getattr(context, 'student_signals', []) or []), ensure_ascii=False)}\n"
                    f"evidence_points={json.dumps(list(getattr(context, 'evidence_points', []) or []), ensure_ascii=False)}\n"
                    f"recent_relevant_messages={json.dumps(list(getattr(context, 'recent_relevant_messages', []) or []), ensure_ascii=False)}"
                )
                structured = self.llm.with_structured_output(ReportPreparationResult, method="function_calling")
                return structured.invoke(prompt)
            except Exception:
                pass
        return self._fallback_prepare(context=context, request_question=request_question)


from app.chat.utils.json_utils import extract_json_block  # noqa: E402
from core.config import Config  # noqa: E402


def _report_context_trace_enabled() -> bool:
    return str(getattr(Config, "UNIVERSAL_REPORT_TRACE", "0") or "").strip().lower() in {"1", "true", "yes"}


def _report_context_trace(*lines: str) -> None:
    if not _report_context_trace_enabled():
        return
    print("[报告工作流] report_context_organizer")
    for line in lines:
        print(f"  - {line}")


def _report_context_organize_v2(self, *, context, request_question: str) -> ReportPreparationResult:
    if self.llm is not None:
        _report_context_trace("llm_path=enabled", f"request={self._clean(request_question)}")
        prompt = (
            "你是报告工作流入口的上下文整理器。请根据给定上下文，产出一份结构化的报告准备结果。"
            "如果 report_subject 明确但 report_focus 不明确，可以补出综合型 focus。"
            "只在 report_intent 或 report_subject 缺失时标记为关键缺口。\n\n"
            f"request_question={request_question}\n"
            f"summary={getattr(context, 'summary_text', '')}\n"
            f"current_topics={list(getattr(context, 'current_topics', []) or [])}\n"
            f"user_goals={list(getattr(context, 'user_goals', []) or [])}\n"
            f"confirmed_facts={list(getattr(context, 'confirmed_facts', []) or [])}\n"
            f"constraints={dict(getattr(context, 'constraints', {}) or {})}\n"
            f"teaching_issues={list(getattr(context, 'teaching_issues', []) or [])}\n"
            f"student_signals={list(getattr(context, 'student_signals', []) or [])}\n"
            f"evidence_points={list(getattr(context, 'evidence_points', []) or [])}\n"
            f"recent_relevant_messages={list(getattr(context, 'recent_relevant_messages', []) or [])}\n\n"
            "请严格输出 JSON 对象，字段必须可被 ReportPreparationResult 解析。"
        )
        try:
            structured = self.llm.with_structured_output(ReportPreparationResult, method="function_calling")
            result = structured.invoke(prompt)
            _report_context_trace("llm_mode=structured_output", "status=ok")
            return result
        except Exception as exc:
            _report_context_trace("llm_mode=structured_output", f"status=failed error={exc}")
            try:
                raw = self.llm.invoke(prompt)
                payload = extract_json_block(getattr(raw, "content", raw))
                if isinstance(payload, dict) and payload:
                    result = ReportPreparationResult.model_validate(payload)
                    _report_context_trace("llm_mode=raw_json", "status=ok")
                    return result
                _report_context_trace("llm_mode=raw_json", "status=empty_or_invalid")
            except Exception as raw_exc:
                _report_context_trace("llm_mode=raw_json", f"status=failed error={raw_exc}")
    _report_context_trace("llm_path=fallback")
    return self._fallback_prepare(context=context, request_question=request_question)


ReportContextOrganizer.organize = _report_context_organize_v2


def _report_context_model_label(llm: Any | None) -> str:
    if llm is None:
        return ""
    for attr in ("model", "model_name", "model_id"):
        value = str(getattr(llm, attr, "") or "").strip()
        if value:
            return value
    return llm.__class__.__name__


def _report_context_result_with_meta(result: ReportPreparationResult, *, source: str, model: str) -> ReportPreparationResult:
    return result.model_copy(
        update={
            "preparation_source": source,
            "preparation_model": model,
        }
    )


def _report_context_trace_result(result: ReportPreparationResult) -> None:
    _report_context_trace(
        f"result_subject={str(result.report_subject or '').strip()}",
        f"result_focus={str(result.report_focus or '').strip()}",
        f"result_confidence={str(result.confidence or '').strip()}",
        f"result_missing={list(result.missing_critical_fields or [])}",
    )


def _report_context_organize_v3(self, *, context, request_question: str) -> ReportPreparationResult:
    model_label = _report_context_model_label(self.llm)
    if self.llm is not None:
        _report_context_trace("llm_path=enabled", f"llm_model={model_label}", f"request={self._clean(request_question)}")
        prompt = (
            "你是报告工作流入口的上下文整理器。请根据给定上下文，提取真正适合生成报告的主题、重点、关键要点、证据和约束。"
            "要主动过滤脏数据、系统软确认文案、泛化句、追问模板、'这是一个非常好的问题'这类低信息内容。"
            "如果 report_subject 明确但 report_focus 不明确，可以给出一个更自然的综合型 focus。"
            "只有 report_intent 或 report_subject 缺失时，才标记为关键缺口。\n\n"
            f"request_question={request_question}\n"
            f"summary={getattr(context, 'summary_text', '')}\n"
            f"current_topics={list(getattr(context, 'current_topics', []) or [])}\n"
            f"user_goals={list(getattr(context, 'user_goals', []) or [])}\n"
            f"confirmed_facts={list(getattr(context, 'confirmed_facts', []) or [])}\n"
            f"constraints={dict(getattr(context, 'constraints', {}) or {})}\n"
            f"teaching_issues={list(getattr(context, 'teaching_issues', []) or [])}\n"
            f"student_signals={list(getattr(context, 'student_signals', []) or [])}\n"
            f"evidence_points={list(getattr(context, 'evidence_points', []) or [])}\n"
            f"recent_relevant_messages={list(getattr(context, 'recent_relevant_messages', []) or [])}\n\n"
            "请严格输出 JSON 对象，字段必须可被 ReportPreparationResult 解析。"
        )
        try:
            structured = self.llm.with_structured_output(ReportPreparationResult, method="function_calling")
            result = _report_context_result_with_meta(
                structured.invoke(prompt),
                source="llm_structured_output",
                model=model_label,
            )
            _report_context_trace("llm_mode=structured_output", "status=ok")
            _report_context_trace_result(result)
            return result
        except Exception as exc:
            _report_context_trace("llm_mode=structured_output", f"status=failed error={exc}")
            try:
                raw = self.llm.invoke(prompt)
                payload = extract_json_block(getattr(raw, "content", raw))
                if isinstance(payload, dict) and payload:
                    result = _report_context_result_with_meta(
                        ReportPreparationResult.model_validate(payload),
                        source="llm_raw_json",
                        model=model_label,
                    )
                    _report_context_trace("llm_mode=raw_json", "status=ok")
                    _report_context_trace_result(result)
                    return result
                _report_context_trace("llm_mode=raw_json", "status=empty_or_invalid")
            except Exception as raw_exc:
                _report_context_trace("llm_mode=raw_json", f"status=failed error={raw_exc}")
    _report_context_trace("llm_path=fallback")
    result = _report_context_result_with_meta(
        self._fallback_prepare(context=context, request_question=request_question),
        source="fallback_rule_based",
        model=model_label,
    )
    _report_context_trace_result(result)
    return result


ReportContextOrganizer.organize = _report_context_organize_v3


def _report_context_organize_v4(self, *, context, request_question: str) -> ReportPreparationResult:
    model_label = _report_context_model_label(self.llm)
    if self.llm is not None:
        _report_context_trace("llm_path=enabled", f"llm_model={model_label}", f"request={self._clean(request_question)}")
        prompt = (
            "你是报告工作流入口的上下文整理器。请根据给定上下文，提取真正适合生成报告的主题、重点、关键要点、证据和约束。"
            "要主动过滤脏数据、系统软确认文案、泛化句、追问模板，以及“这是一个非常好的问题”这类低信息内容。"
            "如果 report_subject 明确但 report_focus 不明确，可以给出一个更自然的综合型 focus。"
            "只有 report_intent 或 report_subject 缺失时，才标记为关键缺口。\n\n"
            f"request_question={request_question}\n"
            f"summary={getattr(context, 'summary_text', '')}\n"
            f"current_topics={list(getattr(context, 'current_topics', []) or [])}\n"
            f"user_goals={list(getattr(context, 'user_goals', []) or [])}\n"
            f"confirmed_facts={list(getattr(context, 'confirmed_facts', []) or [])}\n"
            f"constraints={dict(getattr(context, 'constraints', {}) or {})}\n"
            f"teaching_issues={list(getattr(context, 'teaching_issues', []) or [])}\n"
            f"student_signals={list(getattr(context, 'student_signals', []) or [])}\n"
            f"evidence_points={list(getattr(context, 'evidence_points', []) or [])}\n"
            f"recent_relevant_messages={list(getattr(context, 'recent_relevant_messages', []) or [])}\n\n"
            "请严格输出 JSON 对象，字段必须可被 ReportPreparationResult 解析。"
        )
        try:
            structured = self.llm.with_structured_output(ReportPreparationResult, method="function_calling")
            structured_result = structured.invoke(prompt)
            if structured_result is None:
                raise ValueError("structured_output_returned_none")
            result = _report_context_result_with_meta(
                structured_result,
                source="llm_structured_output",
                model=model_label,
            )
            result = self._sanitize_result(
                context=context,
                request_question=request_question,
                raw_result=result,
            )
            _report_context_trace("llm_mode=structured_output", "status=ok")
            _report_context_trace_result(result)
            return result
        except Exception as exc:
            _report_context_trace("llm_mode=structured_output", f"status=failed error={exc}")
            try:
                raw = self.llm.invoke(prompt)
                payload = extract_json_block(getattr(raw, "content", raw))
                if isinstance(payload, dict) and payload:
                    result = _report_context_result_with_meta(
                        ReportPreparationResult.model_validate(payload),
                        source="llm_raw_json",
                        model=model_label,
                    )
                    result = self._sanitize_result(
                        context=context,
                        request_question=request_question,
                        raw_result=result,
                    )
                    _report_context_trace("llm_mode=raw_json", "status=ok")
                    _report_context_trace_result(result)
                    return result
                _report_context_trace("llm_mode=raw_json", "status=empty_or_invalid")
            except Exception as raw_exc:
                _report_context_trace("llm_mode=raw_json", f"status=failed error={raw_exc}")
    _report_context_trace("llm_path=fallback")
    result = _report_context_result_with_meta(
        self._fallback_prepare(context=context, request_question=request_question),
        source="fallback_rule_based",
        model=model_label,
    )
    result = self._sanitize_result(
        context=context,
        request_question=request_question,
        raw_result=result,
    )
    _report_context_trace_result(result)
    return result


ReportContextOrganizer.organize = _report_context_organize_v4
