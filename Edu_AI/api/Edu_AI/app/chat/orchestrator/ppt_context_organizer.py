from __future__ import annotations

import json
from typing import Any

from app.chat.domain.ppt_preparation import PptPreparationResult
from app.chat.utils.json_utils import extract_json_block
from app.chat.utils.llm_compat import llm_model_label, should_skip_function_calling


class PptContextOrganizer:
    _DEFAULT_PAGE_COUNT = 18
    _LOW_SIGNAL = {
        "",
        "create ppt",
        "generate ppt",
        "make a ppt",
        "build a ppt",
        "help me make slides",
        "帮我做一个ppt",
        "做一个ppt",
        "做个ppt",
        "生成ppt",
        "制作ppt",
    }

    def __init__(self, *, llm: Any | None = None):
        self.llm = llm

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _is_low_signal(self, value: Any) -> bool:
        text = self._clean(value).lower()
        return not text or text in self._LOW_SIGNAL

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in deduped:
                deduped.append(text)
        return deduped

    def _pick_topic(self, *, context, request_question: str) -> str | None:
        for topic in list(getattr(context, "current_topics", []) or []):
            text = self._clean(topic)
            if text and not self._is_low_signal(text):
                return text

        question = self._clean(request_question)
        if question and not self._is_low_signal(question):
            return question

        summary = self._clean(getattr(context, "summary_text", "") or "")
        if summary and not self._is_low_signal(summary):
            return summary

        for message in list(getattr(context, "recent_relevant_messages", []) or []):
            if str((message or {}).get("role") or "").strip() != "user":
                continue
            text = self._clean((message or {}).get("content") or "")
            if text and not self._is_low_signal(text):
                return text
        return None

    def _pick_audience(self, *, context) -> str | None:
        constraints = dict(getattr(context, "constraints", {}) or {})
        for key in ("audience", "target_audience"):
            text = self._clean(constraints.get(key))
            if text:
                return text
        return None

    def _pick_objective(self, *, context) -> str | None:
        constraints = dict(getattr(context, "constraints", {}) or {})
        text = self._clean(constraints.get("objective"))
        if text:
            return text

        for goal in list(getattr(context, "user_goals", []) or []):
            text = self._clean(goal)
            if text and not self._is_low_signal(text) and "ppt" not in text.lower():
                return text

        return None

    def _pick_key_points(self, *, context) -> list[str]:
        points: list[str] = []
        for item in list(getattr(context, "confirmed_facts", []) or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
            if len(points) >= 4:
                return points
        for item in list(getattr(context, "evidence_points", []) or []):
            if not isinstance(item, dict):
                continue
            text = self._clean(item.get("content") or "")
            if text and text not in points:
                points.append(text)
            if len(points) >= 4:
                return points
        for item in list(getattr(context, "teaching_issues", []) or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
            if len(points) >= 4:
                return points
        for item in list(getattr(context, "student_signals", []) or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
            if len(points) >= 4:
                return points
        return points

    def _pick_source_basis(self, *, context) -> list[str]:
        raw_scope = dict(getattr(context, "source_scope", {}) or {})
        labels: list[str] = []
        if bool(raw_scope.get("from_summary")):
            labels.append("conversation_summary")
        if bool(raw_scope.get("from_memory")):
            labels.append("conversation_memory")
        if bool(raw_scope.get("from_recent_messages")):
            labels.append("recent_messages")
        if bool(raw_scope.get("from_docs")):
            labels.append("selected_docs")
        if bool(raw_scope.get("from_artifacts")):
            labels.append("artifact_context")
        if getattr(context, "current_course_id", None):
            labels.append("course_context")
        if not labels:
            labels.append("conversation_summary")
        return labels

    def _pick_source_excerpts(self, *, context, limit: int = 6) -> list[str]:
        excerpts: list[str] = []

        def _append(text: Any, prefix: str = "") -> None:
            cleaned = self._clean(text)
            if not cleaned:
                return
            candidate = f"{prefix}{cleaned}" if prefix else cleaned
            if candidate not in excerpts:
                excerpts.append(candidate)

        summary = self._clean(getattr(context, "summary_text", "") or "")
        if summary:
            _append(summary, "摘要：")

        for item in list(getattr(context, "confirmed_facts", []) or []):
            _append(item, "事实：")
            if len(excerpts) >= limit:
                return excerpts[:limit]

        for item in list(getattr(context, "evidence_points", []) or []):
            if isinstance(item, dict):
                _append(item.get("content") or "", "证据：")
            else:
                _append(item, "证据：")
            if len(excerpts) >= limit:
                return excerpts[:limit]

        for message in list(getattr(context, "recent_relevant_messages", []) or []):
            role = self._clean((message or {}).get("role") or "")
            content = self._clean((message or {}).get("content") or "")
            if not content:
                continue
            prefix = "用户原话：" if role == "user" else "对话内容："
            _append(content, prefix)
            if len(excerpts) >= limit:
                return excerpts[:limit]

        return excerpts[:limit]

    @staticmethod
    def _pick_style(*, context) -> str | None:
        constraints = dict(getattr(context, "constraints", {}) or {})
        return str(constraints.get("style") or constraints.get("format_style") or "").strip() or None

    @staticmethod
    def _pick_theme(*, context) -> str | None:
        constraints = dict(getattr(context, "constraints", {}) or {})
        return str(constraints.get("theme") or constraints.get("template_style") or "").strip() or None

    @staticmethod
    def _parse_page_count(value: Any) -> int | None:
        try:
            return int(value) if value is not None and str(value).strip() else None
        except Exception:
            return None

    @classmethod
    def _pick_explicit_page_count(cls, *, context) -> int | None:
        constraints = dict(getattr(context, "constraints", {}) or {})
        raw = constraints.get("page_count") or constraints.get("slide_count")
        return cls._parse_page_count(raw)

    @staticmethod
    def _build_followup_question(*, missing_fields: list[str]) -> str:
        if "topic" in missing_fields:
            return "这份 PPT 主要想讲哪个主题？"
        if "audience" in missing_fields:
            return "这份 PPT 主要面向哪类学生或听众？"
        if "objective" in missing_fields:
            return "你希望这份 PPT 更偏课堂讲解、汇报展示，还是复习总结？"
        if "key_points" in missing_fields:
            return "你最希望这份 PPT 重点覆盖哪 2 到 4 个部分？"
        return ""

    def _build_missing_core_fields(
        self,
        *,
        topic: str | None,
        audience: str | None,
        objective: str | None,
        key_points: list[str],
    ) -> list[str]:
        missing: list[str] = []
        if not self._clean(topic):
            missing.append("topic")
        if not self._clean(audience):
            missing.append("audience")
        if not self._clean(objective):
            missing.append("objective")
        if len(list(key_points or [])) < 2:
            missing.append("key_points")
        return missing

    def _sanitize_result(self, *, context, request_question: str, raw_result: PptPreparationResult) -> PptPreparationResult:
        topic = self._clean(raw_result.topic) or self._clean(self._pick_topic(context=context, request_question=request_question))
        audience = self._clean(raw_result.audience) or self._clean(self._pick_audience(context=context))
        objective = self._clean(raw_result.objective) or self._clean(self._pick_objective(context=context))
        key_points = self._dedupe([self._clean(item) for item in list(raw_result.key_points or []) if self._clean(item)])
        if not key_points:
            key_points = self._pick_key_points(context=context)
        source_basis = self._dedupe([self._clean(item) for item in list(raw_result.source_basis or []) if self._clean(item)])
        if not source_basis:
            source_basis = self._pick_source_basis(context=context)
        source_excerpts = self._dedupe(
            [self._clean(item) for item in list(getattr(raw_result, "source_excerpts", []) or []) if self._clean(item)]
        )
        if not source_excerpts:
            source_excerpts = self._pick_source_excerpts(context=context)
        style = self._clean(raw_result.style) or self._clean(self._pick_style(context=context))
        theme = self._clean(raw_result.theme) or self._clean(self._pick_theme(context=context))
        explicit_page_count = self._pick_explicit_page_count(context=context)
        if explicit_page_count is not None:
            page_count = explicit_page_count
        else:
            page_count = self._parse_page_count(raw_result.page_count) or self._DEFAULT_PAGE_COUNT
        missing_core_fields = self._build_missing_core_fields(
            topic=topic,
            audience=audience,
            objective=objective,
            key_points=key_points,
        )
        followup_question = self._clean(raw_result.followup_question) or self._build_followup_question(
            missing_fields=missing_core_fields
        )

        return raw_result.model_copy(
            update={
                "topic": topic or None,
                "audience": audience or None,
                "objective": objective or None,
                "key_points": key_points,
                "source_basis": source_basis,
                "source_excerpts": source_excerpts,
                "style": style or None,
                "theme": theme or None,
                "page_count": page_count,
                "missing_core_fields": missing_core_fields,
                "followup_question": followup_question,
                "preparation_source": self._clean(raw_result.preparation_source) or ("llm" if self.llm is not None else "rules"),
                "preparation_model": self._clean(raw_result.preparation_model),
            }
        )

    def _fallback_prepare(self, *, context, request_question: str) -> PptPreparationResult:
        topic = self._pick_topic(context=context, request_question=request_question)
        audience = self._pick_audience(context=context)
        objective = self._pick_objective(context=context)
        key_points = self._pick_key_points(context=context)
        source_basis = self._pick_source_basis(context=context)
        source_excerpts = self._pick_source_excerpts(context=context)
        style = self._pick_style(context=context)
        theme = self._pick_theme(context=context)
        explicit_page_count = self._pick_explicit_page_count(context=context)
        page_count = explicit_page_count if explicit_page_count is not None else self._DEFAULT_PAGE_COUNT
        missing_core_fields = self._build_missing_core_fields(
            topic=topic,
            audience=audience,
            objective=objective,
            key_points=key_points,
        )

        return PptPreparationResult(
            topic=topic,
            audience=audience,
            objective=objective,
            key_points=key_points,
            source_basis=source_basis,
            source_excerpts=source_excerpts,
            style=style,
            theme=theme,
            page_count=page_count,
            missing_core_fields=missing_core_fields,
            followup_question=self._build_followup_question(missing_fields=missing_core_fields),
            preparation_source="rules",
        )

    def organize(self, *, context, request_question: str) -> PptPreparationResult:
        if self.llm is not None:
            model_label = llm_model_label(self.llm)
            try:
                prompt = (
                    "你是 PPT 工作流的上下文整理器。请先基于当前会话总结出可用于生成逐页大纲的 preparation 结果。"
                    "你的目标不是机械抽槽位，而是帮助后续大纲生成拿到足够清晰的教学主题、受众、目标、重点和来源依据。"
                    "如果信息已经基本够用，就用合理假设补齐，不要轻易把字段留空；"
                    "只有在明显无法稳定生成逐页大纲时，才保留 missing_core_fields。\n\n"
                    "请特别注意：\n"
                    "- topic 要尽量收敛成一个明确、适合做课件标题的主题。\n"
                    "- objective 要体现这份 PPT 是课堂讲解、汇报展示还是复习总结。\n"
                    "- key_points 应该提炼成 2 到 4 个最值得拆页展开的重点，而不是简单复读所有原话。\n"
                    "- source_basis 只保留真正有依据的来源标签。\n"
                    "- 输出必须符合 PptPreparationResult 结构。\n\n"
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
                if not should_skip_function_calling(self.llm):
                    structured = self.llm.with_structured_output(PptPreparationResult, method="function_calling")
                    raw_result = structured.invoke(prompt)
                    if isinstance(raw_result, PptPreparationResult):
                        return self._sanitize_result(
                            context=context,
                            request_question=request_question,
                            raw_result=raw_result,
                        )
                raw = self.llm.invoke(prompt)
                payload = extract_json_block(getattr(raw, "content", raw))
                if isinstance(payload, dict) and payload:
                    return self._sanitize_result(
                        context=context,
                        request_question=request_question,
                        raw_result=PptPreparationResult.model_validate(
                            {
                                **payload,
                                "preparation_source": str(payload.get("preparation_source") or "llm_raw_json").strip(),
                                "preparation_model": str(payload.get("preparation_model") or model_label).strip(),
                            }
                        ),
                    )
            except Exception:
                pass

        return self._fallback_prepare(context=context, request_question=request_question)
