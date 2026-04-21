from __future__ import annotations

import json
import re
from typing import Any

from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.quiz_preparation import QuizContextSummary, QuizPreparationResult
from app.chat.utils.json_utils import extract_json_block
from app.chat.utils.llm_compat import llm_base_url, llm_model_label, should_skip_function_calling
from app.chat.workflows.quiz.assembler import QuizAssembler
from core.config import Config


def _quiz_trace_enabled() -> bool:
    return str(getattr(Config, "QUIZ_WORKFLOW_TRACE", "0") or "").strip().lower() in {"1", "true", "yes"}


def _quiz_trace(*lines: str) -> None:
    if not _quiz_trace_enabled():
        return
    print("[quiz_context_organizer]")
    for line in lines:
        print(f"  - {line}")


class QuizContextOrganizer:
    _QUESTION_TYPE_MARKERS = (
        ("choice", ("choice", "choices", "single choice", "multiple choice", "选择", "单选", "多选")),
        ("blank", ("blank", "fill in the blank", "填空")),
        ("short", ("short", "short answer", "简答")),
        ("judge", ("judge", "true false", "true/false", "判断")),
    )
    _COUNT_PATTERNS = (
        re.compile(r"(\d+)\s*(?:道|个)?\s*(?:题|习题|练习题|测试题)"),
        re.compile(r"(\d+)\s*(?:道|个)\s*(?:选择题|单选题|多选题|填空题|简答题|判断题)"),
        re.compile(r"(\d+)\s*(?:道|个)"),
        re.compile(r"(\d+)\s*questions?", flags=re.IGNORECASE),
    )
    _DIFFICULTY_MARKERS = (
        ("easy", ("easy", "simple", "basic", "入门", "基础", "简单", "容易")),
        ("medium", ("medium", "normal", "standard", "中等", "适中", "普通")),
        ("hard", ("hard", "advanced", "challenging", "提高", "拔高", "困难", "较难")),
    )
    _TOPIC_ONLY_FILLERS = {
        "",
        "主题",
        "题量",
        "题型",
        "数量",
        "难度",
        "出题",
        "生成习题",
        "根据以上内容",
        "基于以上内容",
        "根据当前内容",
        "基于当前内容",
        "根据以上内容生成习题",
    }
    _LOW_SIGNAL_TOPIC_MARKERS = (
        "生成习题",
        "生成练习",
        "根据以上内容",
        "出题",
        "练习",
        "习题",
        "quiz",
    )
    _QUIZ_OBJECT_MARKERS = (
        "习题",
        "练习",
        "练习题",
        "测试",
        "测试题",
        "出题",
        "选择题",
        "单选题",
        "多选题",
        "填空题",
        "简答题",
        "判断题",
        "quiz",
        "exercise",
        "practice",
        "test",
    )
    _QUIZ_ACTION_MARKERS = ("生成", "出", "组", "写", "设计", "create", "generate", "make", "prepare", "build")
    _ADJUST_MARKERS = ("继续", "保持", "不变", "改成", "增加", "减少", "调整", "修改", "补充", "continue", "adjust", "change")

    def __init__(self, *, llm: Any | None = None, assembler: QuizAssembler | None = None):
        self.llm = llm
        self.assembler = assembler or QuizAssembler()

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _is_low_signal_topic(self, value: Any) -> bool:
        text = self._clean(value).lower()
        if not text:
            return True
        if text in self._TOPIC_ONLY_FILLERS:
            return True
        return any(marker in text for marker in self._LOW_SIGNAL_TOPIC_MARKERS)

    def _extract_question_types(self, value: Any) -> list[str]:
        text = " ".join(self._clean(item) for item in value) if isinstance(value, (list, tuple, set)) else self._clean(value)
        if not text:
            return []
        normalized_text = text.lower()
        detected: list[str] = []
        for normalized_type, markers in self._QUESTION_TYPE_MARKERS:
            if any(marker in normalized_text for marker in markers) and normalized_type not in detected:
                detected.append(normalized_type)
        return detected

    def _normalize_difficulty(self, value: Any) -> str:
        text = self._clean(value).lower()
        if not text:
            return ""
        for normalized, markers in self._DIFFICULTY_MARKERS:
            if any(marker in text for marker in markers):
                return normalized
        return ""

    def _request_has_quiz_object(self, request_text: str) -> bool:
        lowered = request_text.lower()
        return (
            any(marker in request_text for marker in self._QUIZ_OBJECT_MARKERS)
            or any(marker in lowered for marker in self._QUIZ_OBJECT_MARKERS)
            or bool(self._extract_question_types(request_text))
        )

    def _request_has_generation_action(self, request_text: str) -> bool:
        lowered = request_text.lower()
        return any(marker in request_text for marker in self._QUIZ_ACTION_MARKERS) or any(
            marker in lowered for marker in self._QUIZ_ACTION_MARKERS
        )

    def _request_has_adjustment_signal(self, request_text: str) -> bool:
        lowered = request_text.lower()
        return any(marker in request_text for marker in self._ADJUST_MARKERS) or any(
            marker in lowered for marker in self._ADJUST_MARKERS
        )

    def _request_has_quiz_directives(self, request_text: str) -> bool:
        if any(pattern.search(request_text) for pattern in self._COUNT_PATTERNS):
            return True
        if self._extract_question_types(request_text):
            return True
        if self._normalize_difficulty(request_text):
            return True
        lowered = request_text.lower()
        return any(marker in lowered for marker in ("answer", "answers", "explanation", "explanations")) or any(
            marker in request_text for marker in ("答案", "解析")
        )

    def _extract_topic_from_request(self, request_text: str) -> str:
        patterns = (
            r"(?:围绕|关于|针对)\s*(?P<topic>[^，。！？?]{1,40}?)(?:生成|出|制作|设计|编写)?(?:习题|练习|练习题|测试|测试题|quiz)",
            r"(?:主题|topic)\s*(?:是|为|:|：)\s*(?P<topic>[^，。！？?]{1,40})",
            r"(?:generate|create|make|prepare)\s+(?:a\s+)?quiz\s+(?:on|about)\s+(?P<topic>[A-Za-z0-9][A-Za-z0-9\\-_ ]{0,40})",
            r"quiz\s+me\s+on\s+(?P<topic>[A-Za-z0-9][A-Za-z0-9\\-_ ]{0,40})",
        )
        for pattern in patterns:
            match = re.search(pattern, request_text, flags=re.IGNORECASE)
            if not match:
                continue
            topic = self._clean(match.group("topic")).strip("，。！？?：: ")
            if topic:
                return topic
        return ""

    def _extract_topic_from_freeform_slot_answer(self, request_text: str) -> str:
        segments = [segment.strip("，。！？?：: ") for segment in re.split(r"[，,、；;]+", self._clean(request_text)) if segment.strip()]
        if not segments:
            return ""

        for segment in segments:
            normalized = segment.lower()
            if segment.isdigit():
                continue
            if self._extract_question_types(segment):
                continue
            if self._normalize_difficulty(segment):
                continue
            if any(pattern.fullmatch(segment) for pattern in self._COUNT_PATTERNS):
                continue
            if normalized in self._TOPIC_ONLY_FILLERS:
                continue
            cleaned = re.sub(r"(?:题量|题型|数量|难度|主题)\s*[:：]?", "", segment, flags=re.IGNORECASE).strip()
            if cleaned and cleaned.lower() not in self._TOPIC_ONLY_FILLERS and not self._is_low_signal_topic(cleaned):
                return cleaned

        cleaned = self._clean(request_text)
        for pattern in self._COUNT_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        cleaned = re.sub(r"(?:选择题|单选题|多选题|填空题|简答题|判断题|choice|blank|short(?: answer)?|judge)", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(?:简单|基础|入门|中等|适中|普通|提高|拔高|困难|easy|medium|hard)", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(?:题量|题型|数量|难度|主题)\s*[:：]?", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[，,、；;]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip("，。！？?：: ")
        if cleaned and cleaned.lower() not in self._TOPIC_ONLY_FILLERS and not self._is_low_signal_topic(cleaned):
            return cleaned
        return ""

    def _extract_explicit_topic_switch_from_request(self, request_text: str) -> str:
        patterns = (
            r"\b(?:switch to|change topic to|change to)\s+(?P<topic>[A-Za-z0-9][A-Za-z0-9\- ]{0,40})\s*$",
            r"(?:主题改成|主题改为|切换到|换成|改为)\s*(?P<topic>[A-Za-z0-9\u4e00-\u9fff·\-_ ]{1,30})\s*$",
        )
        for pattern in patterns:
            match = re.search(pattern, request_text, flags=re.IGNORECASE)
            if not match:
                continue
            topic = self._clean(match.group("topic")).strip("，。！？?：: ")
            if topic:
                return topic
        return ""

    def _derive_topic_from_context_content(self, context: GenerationContext) -> str:
        candidates: list[str] = []
        if self._clean(context.summary_text):
            candidates.append(self._clean(context.summary_text))
        candidates.extend(self._clean(item) for item in list(context.confirmed_facts or []))
        candidates.extend(self._clean(item.get("content")) for item in list(context.evidence_points or []) if isinstance(item, dict))
        for message in list(context.recent_relevant_messages or []):
            if not isinstance(message, dict):
                continue
            content = self._clean(message.get("content"))
            if content:
                candidates.append(content)

        stopwords = {
            "根据",
            "以上",
            "内容",
            "生成",
            "习题",
            "练习",
            "建议",
            "可以",
            "分析",
            "对比",
            "问题",
            "方向",
            "主题",
            "题型",
            "题量",
            "难度",
            "当前",
            "继续",
        }
        frequency: dict[str, int] = {}
        first_seen: dict[str, int] = {}
        for index, text in enumerate(candidates):
            for match in re.finditer(r"[\u4e00-\u9fffA-Za-z0-9·]{2,12}", text):
                token = match.group(0).strip()
                if not token or token in stopwords:
                    continue
                if self._is_low_signal_topic(token):
                    continue
                if len(token) > 8 and not any(marker in token for marker in ("关羽", "襄樊", "水淹", "北伐", "课堂")):
                    continue
                frequency[token] = frequency.get(token, 0) + 1
                first_seen.setdefault(token, index)

        if frequency:
            ranked = sorted(
                frequency,
                key=lambda item: (
                    -frequency[item],
                    first_seen.get(item, 0),
                    0 if len(item) <= 6 else 1,
                    -len(item),
                ),
            )
            return ranked[0]

        for text in candidates:
            cleaned = re.sub(r"\s+", " ", text).strip("，。！？?：: ")
            if cleaned and not self._is_low_signal_topic(cleaned):
                return cleaned[:40]
        return ""

    def _pick_topic(
        self,
        *,
        context: GenerationContext,
        request_text: str,
        stored_slots: dict[str, str] | None,
        slot_hints: dict[str, Any] | None,
    ) -> str:
        stored_topic = self._clean((stored_slots or {}).get("topic"))
        switched_topic = self._extract_explicit_topic_switch_from_request(request_text)
        if switched_topic:
            return switched_topic
        if stored_topic and not self._is_low_signal_topic(stored_topic) and self._request_has_adjustment_signal(request_text):
            return stored_topic
        request_topic = self._extract_topic_from_request(request_text)
        if request_topic:
            return request_topic
        freeform_topic = self._extract_topic_from_freeform_slot_answer(request_text)
        if freeform_topic:
            return freeform_topic
        if stored_topic and not self._is_low_signal_topic(stored_topic):
            return stored_topic
        hinted_topic = self._clean((slot_hints or {}).get("topic"))
        if hinted_topic and not self._is_low_signal_topic(hinted_topic):
            return hinted_topic
        for topic in list(context.current_topics or []):
            text = self._clean(topic)
            if text and not self._is_low_signal_topic(text):
                return text

        derived_topic = self._derive_topic_from_context_content(context)
        if derived_topic:
            return derived_topic

        summary = self._clean(context.summary_text)
        if summary and not self._is_low_signal_topic(summary):
            return summary
        return ""

    def _pick_question_count(
        self,
        *,
        request_text: str,
        stored_slots: dict[str, str] | None,
        slot_hints: dict[str, Any] | None,
    ) -> int | None:
        for pattern in self._COUNT_PATTERNS:
            match = pattern.search(request_text)
            if match:
                return int(match.group(1))
        for segment in [part.strip() for part in re.split(r"[，,、；;]+", self._clean(request_text)) if part.strip()]:
            if segment.isdigit():
                return int(segment)
        stored_count = self._clean((stored_slots or {}).get("question_count") or (stored_slots or {}).get("count"))
        if stored_count.isdigit():
            return int(stored_count)
        hinted_count = self._clean((slot_hints or {}).get("question_count") or (slot_hints or {}).get("count"))
        if hinted_count.isdigit():
            return int(hinted_count)
        return None

    def _pick_question_types(
        self,
        *,
        request_text: str,
        stored_slots: dict[str, str] | None,
        slot_hints: dict[str, Any] | None,
    ) -> list[str]:
        detected = self._extract_question_types(request_text)
        if detected:
            return detected
        stored_text = (stored_slots or {}).get("question_types") or (stored_slots or {}).get("question_type")
        detected = self._extract_question_types(stored_text)
        if detected:
            return detected
        hinted_text = (slot_hints or {}).get("question_types") or (slot_hints or {}).get("question_type")
        return self._extract_question_types(hinted_text)

    def _pick_difficulty(
        self,
        *,
        request_text: str,
        stored_slots: dict[str, str] | None,
        slot_hints: dict[str, Any] | None,
    ) -> str | None:
        request_difficulty = self._normalize_difficulty(request_text)
        if request_difficulty:
            return request_difficulty
        stored_difficulty = self._normalize_difficulty((stored_slots or {}).get("difficulty"))
        if stored_difficulty:
            return stored_difficulty
        hinted_difficulty = self._normalize_difficulty((slot_hints or {}).get("difficulty"))
        if hinted_difficulty:
            return hinted_difficulty
        return None

    def _pick_include_answers(self, request_text: str) -> bool:
        if any(marker in request_text for marker in ("不要答案", "不含答案", "无需答案", "别给答案", "只要题目")):
            return False
        if any(marker in request_text for marker in ("要答案", "保留答案", "答案保留", "带答案")):
            return True
        return True

    def _pick_include_explanations(self, request_text: str) -> bool:
        if any(marker in request_text for marker in ("不要解析", "不含解析", "无需解析", "别给解析", "只要题目")):
            return False
        if any(marker in request_text for marker in ("要解析", "保留解析", "解析保留", "带解析")):
            return True
        return True

    def _pick_knowledge_points(self, context: GenerationContext) -> list[str]:
        points: list[str] = []
        for item in list(context.confirmed_facts or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
        return points

    def _pick_weak_points(self, context: GenerationContext) -> list[str]:
        points: list[str] = []
        for item in list(context.student_signals or []):
            text = self._clean(item)
            if text and text not in points:
                points.append(text)
        return points

    def _quiz_intent(self, request_text: str) -> str:
        if not self._request_has_quiz_object(request_text):
            return "unclear"
        if self._request_has_generation_action(request_text):
            return "generate_quiz"
        if self._request_has_adjustment_signal(request_text):
            return "generate_quiz"
        if self._request_has_quiz_directives(request_text):
            return "generate_quiz"
        return "unclear"

    def _build_soft_confirm_message(
        self,
        *,
        topic: str,
        question_count: int | None,
        question_types: list[str],
        difficulty: str | None,
    ) -> str:
        if not topic:
            return ""
        count_text = f"{question_count}道" if question_count else "一组"
        type_map = {"choice": "选择题", "blank": "填空题", "short": "简答题", "judge": "判断题"}
        parts = [f"我可以先基于“{topic}”直接生成{count_text}习题"]
        if question_types:
            parts.append(f"题型为{'、'.join(type_map.get(item, item) for item in question_types)}")
        if difficulty:
            difficulty_map = {"easy": "基础", "medium": "中等", "hard": "提高"}
            parts.append(f"难度按{difficulty_map.get(difficulty, difficulty)}")
        return "，".join(parts) + "。如果可以，我就开始生成。"

    def _source_scope_labels(self, context: GenerationContext) -> list[str]:
        raw_scope = dict(context.source_scope or {})
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
        if context.current_course_id:
            labels.append("course_context")
        if not labels:
            labels.append("conversation_summary")
        return labels

    def _build_summary(
        self,
        *,
        topic: str,
        question_count: int | None,
        question_types: list[str],
        difficulty: str | None,
        include_answers: bool,
        include_explanations: bool,
        knowledge_points: list[str],
        weak_points: list[str],
        context: GenerationContext,
        source_scope: list[str],
    ) -> QuizContextSummary:
        settings = [
            f"count={question_count or ''}",
            f"types={'/'.join(question_types)}",
            f"difficulty={difficulty or ''}",
            f"answers={'yes' if include_answers else 'no'}",
            f"explanations={'yes' if include_explanations else 'no'}",
        ]
        return QuizContextSummary(
            topic_summary=self._clean(topic or context.summary_text),
            settings_summary=self._clean(" ".join(settings)),
            weak_points=weak_points,
            knowledge_points=knowledge_points,
            constraints=dict(context.constraints or {}),
            source_scope=source_scope,
        )

    def _build_fallback_result(
        self,
        *,
        context: GenerationContext,
        request_question: str,
        stored_slots: dict[str, str] | None,
    ) -> QuizPreparationResult:
        assembled = self.assembler.from_generation_context(context)
        slot_hints = dict(assembled.get("slot_hints") or {})
        request_text = self._clean(request_question)
        topic = self._pick_topic(context=context, request_text=request_text, stored_slots=stored_slots, slot_hints=slot_hints)
        question_count = self._pick_question_count(request_text=request_text, stored_slots=stored_slots, slot_hints=slot_hints)
        question_types = self._pick_question_types(request_text=request_text, stored_slots=stored_slots, slot_hints=slot_hints)
        difficulty = self._pick_difficulty(request_text=request_text, stored_slots=stored_slots, slot_hints=slot_hints)
        knowledge_points = self._pick_knowledge_points(context)
        weak_points = self._pick_weak_points(context)
        include_answers = self._pick_include_answers(request_text)
        include_explanations = self._pick_include_explanations(request_text)
        source_scope = self._source_scope_labels(context)
        missing_critical_fields = [] if topic else ["topic"]
        confidence = "high" if topic and (question_count or question_types or knowledge_points or weak_points) else "low"

        result = QuizPreparationResult(
            quiz_intent=self._quiz_intent(request_text),
            topic=topic or None,
            question_count=question_count,
            question_types=question_types,
            difficulty=difficulty,
            include_answers=include_answers,
            include_explanations=include_explanations,
            quiz_context_summary=self._build_summary(
                topic=topic,
                question_count=question_count,
                question_types=question_types,
                difficulty=difficulty,
                include_answers=include_answers,
                include_explanations=include_explanations,
                knowledge_points=knowledge_points,
                weak_points=weak_points,
                context=context,
                source_scope=source_scope,
            ),
            constraints=dict(context.constraints or {}),
            source_scope=source_scope,
            knowledge_points=knowledge_points,
            weak_points=weak_points,
            missing_critical_fields=missing_critical_fields,
            confidence=confidence,
            soft_confirm_message=self._build_soft_confirm_message(
                topic=topic,
                question_count=question_count,
                question_types=question_types,
                difficulty=difficulty,
            ),
        )
        _quiz_trace(
            "mode=fallback_rule_based",
            f"request={request_text}",
            f"topic={self._clean(result.topic)}",
            f"question_count={result.question_count}",
            f"question_types={list(result.question_types or [])}",
            f"difficulty={self._clean(result.difficulty)}",
            f"missing={list(result.missing_critical_fields or [])}",
        )
        return result

    def _sanitize_result(
        self,
        *,
        context: GenerationContext,
        request_question: str,
        stored_slots: dict[str, str] | None,
        raw_result: QuizPreparationResult,
    ) -> QuizPreparationResult:
        fallback = self._build_fallback_result(context=context, request_question=request_question, stored_slots=stored_slots)
        topic = self._clean(raw_result.topic or fallback.topic)
        question_count = raw_result.question_count if raw_result.question_count is not None else fallback.question_count
        question_types = list(raw_result.question_types or []) or list(fallback.question_types or [])
        difficulty = self._normalize_difficulty(raw_result.difficulty) or self._normalize_difficulty(fallback.difficulty)
        include_answers = raw_result.include_answers if raw_result.include_answers is not None else fallback.include_answers
        include_explanations = raw_result.include_explanations if raw_result.include_explanations is not None else fallback.include_explanations
        knowledge_points = list(raw_result.knowledge_points or []) or list(fallback.knowledge_points or [])
        weak_points = list(raw_result.weak_points or []) or list(fallback.weak_points or [])
        source_scope = list(raw_result.source_scope or []) or list(fallback.source_scope or [])
        raw_quiz_intent = self._clean(raw_result.quiz_intent)
        fallback_quiz_intent = self._clean(fallback.quiz_intent)
        has_generation_basis = bool(question_count or question_types or knowledge_points or weak_points)
        if raw_quiz_intent == "generate_quiz" or fallback_quiz_intent == "generate_quiz":
            quiz_intent = "generate_quiz"
        elif topic and has_generation_basis and (
            self._request_has_quiz_object(request_question)
            or self._request_has_generation_action(request_question)
            or self._request_has_quiz_directives(request_question)
        ):
            quiz_intent = "generate_quiz"
        else:
            quiz_intent = raw_quiz_intent or fallback_quiz_intent or "unclear"
        missing_critical_fields = [] if topic else ["topic"]
        confidence = self._clean(raw_result.confidence or "") or ("high" if topic and (question_count or question_types or knowledge_points or weak_points) else "low")
        summary = raw_result.quiz_context_summary or self._build_summary(
            topic=topic,
            question_count=question_count,
            question_types=question_types,
            difficulty=difficulty,
            include_answers=include_answers,
            include_explanations=include_explanations,
            knowledge_points=knowledge_points,
            weak_points=weak_points,
            context=context,
            source_scope=source_scope,
        )
        if not list(summary.knowledge_points or []):
            summary = summary.model_copy(update={"knowledge_points": knowledge_points})
        if not list(summary.weak_points or []):
            summary = summary.model_copy(update={"weak_points": weak_points})
        if not list(summary.source_scope or []):
            summary = summary.model_copy(update={"source_scope": source_scope})
        if not self._clean(summary.topic_summary):
            summary = summary.model_copy(update={"topic_summary": topic or self._clean(context.summary_text)})
        if not self._clean(summary.settings_summary):
            summary = summary.model_copy(update={"settings_summary": fallback.quiz_context_summary.settings_summary})

        result = raw_result.model_copy(
            update={
                "quiz_intent": quiz_intent,
                "topic": topic or None,
                "question_count": question_count,
                "question_types": question_types,
                "difficulty": difficulty or None,
                "include_answers": include_answers,
                "include_explanations": include_explanations,
                "quiz_context_summary": summary,
                "constraints": dict(raw_result.constraints or {}) or dict(context.constraints or {}),
                "source_scope": source_scope,
                "knowledge_points": knowledge_points,
                "weak_points": weak_points,
                "missing_critical_fields": missing_critical_fields,
                "confidence": confidence,
                "soft_confirm_message": self._build_soft_confirm_message(
                    topic=topic,
                    question_count=question_count,
                    question_types=question_types,
                    difficulty=difficulty,
                ),
            }
        )
        _quiz_trace(
            "mode=llm_sanitized",
            f"quiz_intent={self._clean(result.quiz_intent)}",
            f"topic={self._clean(result.topic)}",
            f"question_count={result.question_count}",
            f"question_types={list(result.question_types or [])}",
            f"difficulty={self._clean(result.difficulty)}",
            f"knowledge_points={list(result.knowledge_points or [])}",
            f"weak_points={list(result.weak_points or [])}",
            f"missing={list(result.missing_critical_fields or [])}",
        )
        return result

    def _build_llm_prompt(self, *, context: GenerationContext, request_question: str) -> str:
        return (
            "你是习题工作流入口的上下文整理器。请根据当前对话上下文，整理出可直接用于出题的 preparation 结果。\n"
            "请优先识别并补全这些槽位：topic、question_count、question_types、difficulty、include_answers、include_explanations、knowledge_points、weak_points。\n"
            "如果上下文已经足够支持先生成一版题目，请尽量补全 knowledge_points 或 weak_points，避免机械地把题量/题型都标记为缺失。\n"
            "只有在 topic 缺失时，才把它放进 missing_critical_fields。\n"
            "question_types 只返回标准值 choice / blank / short / judge。\n"
            "difficulty 只返回 easy / medium / hard。\n\n"
            f"request_question={request_question}\n"
            f"summary={getattr(context, 'summary_text', '')}\n"
            f"current_topics={json.dumps(list(getattr(context, 'current_topics', []) or []), ensure_ascii=False)}\n"
            f"user_goals={json.dumps(list(getattr(context, 'user_goals', []) or []), ensure_ascii=False)}\n"
            f"confirmed_facts={json.dumps(list(getattr(context, 'confirmed_facts', []) or []), ensure_ascii=False)}\n"
            f"constraints={json.dumps(dict(getattr(context, 'constraints', {}) or {}), ensure_ascii=False)}\n"
            f"student_signals={json.dumps(list(getattr(context, 'student_signals', []) or []), ensure_ascii=False)}\n"
            f"teaching_issues={json.dumps(list(getattr(context, 'teaching_issues', []) or []), ensure_ascii=False)}\n"
            f"evidence_points={json.dumps(list(getattr(context, 'evidence_points', []) or []), ensure_ascii=False)}\n"
            f"recent_relevant_messages={json.dumps(list(getattr(context, 'recent_relevant_messages', []) or []), ensure_ascii=False)}"
        )

    def organize(
        self,
        *,
        context: GenerationContext,
        request_question: str,
        stored_slots: dict[str, str] | None = None,
    ) -> QuizPreparationResult:
        model_label = llm_model_label(self.llm)
        if self.llm is not None:
            prompt = self._build_llm_prompt(context=context, request_question=request_question)
            _quiz_trace(
                "llm_path=enabled",
                f"llm_model={model_label}",
                f"base_url={llm_base_url(self.llm)}",
                f"request={self._clean(request_question)}",
            )
            if should_skip_function_calling(self.llm):
                _quiz_trace("llm_mode=structured_output", "status=skipped_qwen_compat")
            else:
                try:
                    structured = self.llm.with_structured_output(QuizPreparationResult, method="function_calling")
                    structured_result = structured.invoke(prompt)
                    if structured_result is not None:
                        return self._sanitize_result(
                            context=context,
                            request_question=request_question,
                            stored_slots=stored_slots,
                            raw_result=structured_result,
                        )
                except Exception as exc:
                    _quiz_trace("llm_mode=structured_output", f"status=failed error={exc}")
            try:
                raw = self.llm.invoke(prompt)
                payload = extract_json_block(getattr(raw, "content", raw))
                if isinstance(payload, dict) and payload:
                    return self._sanitize_result(
                        context=context,
                        request_question=request_question,
                        stored_slots=stored_slots,
                        raw_result=QuizPreparationResult.model_validate(payload),
                    )
            except Exception as exc:
                _quiz_trace("llm_mode=raw_json", f"status=failed error={exc}")

        return self._build_fallback_result(context=context, request_question=request_question, stored_slots=stored_slots)
