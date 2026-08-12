from __future__ import annotations

import json
import re
from typing import Any, Callable

from app.chat.tools.agent_tools import rag_search_tool
from core.config import Config


def _trace_enabled() -> bool:
    return str(getattr(Config, "QUIZ_WORKFLOW_TRACE", "1") or "").strip().lower() in {"1", "true", "yes"}


def _preview(value: Any, *, limit: int = 260) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _trace_event(event: str, payload: dict[str, Any]) -> None:
    if not _trace_enabled():
        return
    print(f"[quiz_generator] {event}")
    print(f"  - data: {json.dumps(payload, ensure_ascii=False, default=str)}")


class QuizGenerator:
    def __init__(self, *, llm: Any | None = None, rag_fetcher: Callable[..., dict] | None = None):
        self.llm = llm
        self.rag_fetcher = rag_fetcher or rag_search_tool

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _normalize_type(self, value: str) -> str:
        normalized = self._clean(value).lower()
        if normalized in {"code_output", "code_trace", "debug_fix", "code_implementation"}:
            return normalized
        if "choice" in normalized or normalized in {"single", "multiple"} or any(token in normalized for token in ("选择", "单选", "多选")):
            return "choice"
        if "blank" in normalized or "填空" in normalized:
            return "blank"
        if "short" in normalized or "简答" in normalized:
            return "short"
        if "judge" in normalized or "true" in normalized or "false" in normalized or any(token in normalized for token in ("判断", "对错", "正误")):
            return "judge"
        return "choice"

    def _first_text(self, question: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = question.get(key)
            if value not in (None, ""):
                return self._clean(value)
        return ""

    def _text_list(self, value: Any) -> list[str]:
        raw_items = value if isinstance(value, list) else [value]
        return [self._clean(item) for item in raw_items if self._clean(item)]

    def _normalize_options(self, value: Any) -> list[str] | None:
        if not value or not isinstance(value, list):
            return None
        options: list[str] = []
        for item in value:
            if isinstance(item, dict):
                label = self._clean(item.get("label") or item.get("key") or item.get("id"))
                text = self._clean(item.get("text") or item.get("content") or item.get("value") or item.get("选项"))
                option = f"{label}. {text}" if label and text and not text.lower().startswith(label.lower()) else text or label
            else:
                option = self._clean(item)
            if option:
                options.append(option)
        return options or None

    def _strip_option_prefix(self, value: str) -> str:
        text = self._clean(value)
        return re.sub(r"^[A-Za-z][\.\)\]、:：\s-]+", "", text).strip()

    def _looks_like_generic_explanation(self, value: str) -> bool:
        text = self._clean(value)
        if not text:
            return True
        generic_prefixes = ("本题考查", "这道题考查", "考查", "用于检查", "围绕已整理出的知识点")
        generic_tokens = ("这一重点", "这一知识点", "识记", "检查是否")
        return text.startswith(generic_prefixes) or any(token in text for token in generic_tokens)

    def _resolve_choice_answer_text(self, answer: str, options: list[str] | None) -> tuple[str, str]:
        normalized_answer = self._clean(answer)
        if not normalized_answer:
            return "", ""
        if not options:
            return "", normalized_answer

        letter_match = re.match(r"^([A-Za-z])(?:[\.\)\]、:：\s-].*)?$", normalized_answer)
        answer_key = letter_match.group(1).upper() if letter_match else ""
        for index, option in enumerate(options):
            label = chr(ord("A") + index)
            stripped = self._strip_option_prefix(option)
            option_text = self._clean(option)
            if answer_key and label == answer_key:
                return label, stripped or option_text
            if normalized_answer in {option_text, stripped}:
                return label, stripped or option_text
        return answer_key, normalized_answer

    def _build_answer_focused_explanation(self, question: dict[str, Any]) -> str:
        question_type = self._normalize_type(self._clean(question.get("type")))
        answer = self._clean(question.get("answer"))
        options = question.get("options")

        if question_type == "choice":
            label, answer_text = self._resolve_choice_answer_text(answer, options if isinstance(options, list) else None)
            answer_display = answer
            if label and answer_text:
                answer_display = f"{label}（{answer_text}）"
            elif answer_text:
                answer_display = answer_text
            return (
                f"正确答案：{answer_display or '见标准答案'}。"
                "因为这一项最符合题干和材料中的关键信息；其余选项要么偏离题意，要么属于干扰项。"
            )

        if question_type == "judge":
            normalized_answer = answer or "正确"
            relation = "与题干和材料信息一致" if normalized_answer in {"正确", "对", "true", "True"} else "与题干和材料信息不一致"
            return f"正确答案：{normalized_answer}。因为题干表述{relation}，所以应判断为{normalized_answer}。"

        if question_type == "blank":
            return f"参考答案：{answer or '见标准答案'}。因为题干要求补出关键概念或信息，填入该内容后句意和知识点才完整。"

        if question_type == "short":
            return f"参考答案应围绕“{answer or '题目核心要求'}”展开，作答时要直接回应题干要求，说明其含义、关系或作用。"

        return f"参考答案：{answer or '见标准答案'}。解析需要结合题干和材料，说明为什么这个答案成立。"

    def _normalize_explanation(self, question: dict[str, Any]) -> str:
        explanation = self._clean(question.get("explanation"))
        if self._looks_like_generic_explanation(explanation):
            return self._build_answer_focused_explanation(question)
        return explanation

    def _extract_payload(self, text: str) -> dict[str, Any]:
        if "```" in text:
            for part in text.split("```"):
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{") and candidate.endswith("}"):
                    text = candidate
                    break
        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start : end + 1] if start >= 0 and end > start else text)

    def _extract_question_items(self, payload: dict[str, Any]) -> list[Any]:
        candidates = (
            payload.get("questions"),
            payload.get("items"),
            payload.get("题目"),
            payload.get("试题"),
            (payload.get("quiz") or {}).get("questions") if isinstance(payload.get("quiz"), dict) else None,
            (payload.get("data") or {}).get("questions") if isinstance(payload.get("data"), dict) else None,
        )
        for candidate in candidates:
            if isinstance(candidate, list):
                return candidate
        return []

    def _parse_questions(self, raw: Any) -> list[dict[str, Any]]:
        text = getattr(raw, "content", raw)
        text = self._clean(text)
        payload = self._extract_payload(text)
        questions = self._extract_question_items(payload)
        normalized_questions: list[dict[str, Any]] = []
        for index, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                continue
            question_type = self._first_text(question, ("type", "question_type", "题型", "类型"))
            stem = self._first_text(question, ("content", "stem", "question", "title", "题干", "题目", "问题"))
            normalized_question = {
                "id": str(question.get("id") or index),
                "type": self._normalize_type(question_type),
                "stem": stem,
                "options": self._normalize_options(question.get("options") or question.get("choices") or question.get("选项")),
                "answer": self._first_text(question, ("answer", "correct_answer", "答案", "正确答案")),
                "explanation": self._first_text(question, ("analysis", "explanation", "解析", "讲解")),
                "knowledge_points": self._text_list(
                    question.get("knowledge_points")
                    or question.get("knowledge_point_ids")
                ),
            }
            normalized_question["explanation"] = self._normalize_explanation(normalized_question)
            normalized_questions.append(normalized_question)
        return [question for question in normalized_questions if question["stem"]]

    def _fallback_questions(
        self,
        *,
        preparation: dict[str, Any],
        question_count: int,
        question_types: list[str],
        start_index: int = 1,
    ) -> list[dict[str, Any]]:
        topic = self._clean(preparation.get("topic")) or "当前主题"
        focus_points = [
            self._clean(item)
            for item in list(preparation.get("knowledge_points") or []) + list(preparation.get("weak_points") or [])
            if self._clean(item)
        ] or [topic]
        normalized_types = [self._normalize_type(item) for item in (question_types or ["choice"])]
        questions: list[dict[str, Any]] = []
        for offset in range(question_count):
            index = start_index + offset
            focus = focus_points[offset % len(focus_points)]
            question_type = normalized_types[offset % len(normalized_types)]
            if question_type == "blank":
                questions.append(
                    {
                        "id": str(index),
                        "type": "blank",
                        "stem": f"请填写与“{topic}”相关的关键知识点：{focus}。",
                        "options": None,
                        "answer": focus,
                        "explanation": "",
                        "knowledge_points": [focus],
                    }
                )
                continue
            if question_type == "short":
                questions.append(
                    {
                        "id": str(index),
                        "type": "short",
                        "stem": f"请简要说明“{focus}”与“{topic}”之间的关系。",
                        "options": None,
                        "answer": f"应围绕“{focus}”说明其在“{topic}”中的作用、含义或联系。",
                        "explanation": "",
                        "knowledge_points": [focus],
                    }
                )
                continue
            if question_type == "judge":
                questions.append(
                    {
                        "id": str(index),
                        "type": "judge",
                        "stem": f"“{focus}”是理解“{topic}”时需要重点关注的内容。",
                        "options": None,
                        "answer": "正确",
                        "explanation": "",
                        "knowledge_points": [focus],
                    }
                )
                continue
            questions.append(
                {
                    "id": str(index),
                    "type": "choice",
                    "stem": f"关于“{topic}”，以下哪一项最符合本次对话整理出的重点？",
                    "options": [focus, "与本次主题无关的细节", "只依据虚构情节作判断", "无法从材料中判断"],
                    "answer": "A",
                    "explanation": "",
                    "knowledge_points": [focus],
                }
            )
        return questions

    def generate(
        self,
        *,
        preparation: dict[str, Any],
        context_summary: str,
        conversation_id: str,
        owner: str | None,
        allow_rag: bool,
        selected_doc_ids: list[str],
    ) -> dict[str, Any]:
        if self.llm is None:
            raise RuntimeError("quiz_generator_llm_unavailable")

        topic = self._clean(preparation.get("topic")) or "quiz"
        question_count = int(preparation.get("question_count") or 10)
        question_types = list(preparation.get("question_types") or ["choice"])
        difficulty = self._clean(preparation.get("difficulty") or "medium")
        rag_context = ""
        if allow_rag and selected_doc_ids:
            rag_result = self.rag_fetcher(
                query=f"quiz generation basis for {topic}",
                top_k=6,
                selected_doc_ids=selected_doc_ids,
                owner=owner,
            )
            rag_context = self._clean(((rag_result.get("payload") or {}).get("answer")))

        prompt = (
            f"Generate {question_count} quiz questions about {topic}. "
            f"Allowed question types: {', '.join(question_types)}. Choose the types that best assess the supplied material; use code questions only for programming material. "
            f"Difficulty: {difficulty}. "
            f"Knowledge points: {', '.join(list(preparation.get('knowledge_points') or []))}. "
            f"Weak points: {', '.join(list(preparation.get('weak_points') or []))}. "
            f"Context summary: {context_summary}. "
            f"RAG context: {rag_context}. "
            "Return JSON with a top-level questions array. "
            "For each question, include a knowledge_points array inferred from the supplied context when no knowledge points were provided. "
            "Each explanation must explain why the answer is correct; for choice questions, also clarify that the other options do not fit the stem."
        )
        raw = self.llm.invoke(prompt)
        return self.build_artifact_from_raw(
            raw=raw,
            preparation=preparation,
            conversation_id=conversation_id,
        )

    def build_artifact_from_raw(
        self,
        *,
        raw: Any,
        preparation: dict[str, Any],
        conversation_id: str,
    ) -> dict[str, Any]:
        topic = self._clean(preparation.get("topic")) or "quiz"
        question_count = int(preparation.get("question_count") or 10)
        question_types = list(preparation.get("question_types") or ["choice"])
        difficulty = self._clean(preparation.get("difficulty") or "medium")
        raw_text = self._clean(getattr(raw, "content", raw))
        try:
            questions = self._parse_questions(raw)
            parse_error = ""
        except Exception as exc:
            questions = []
            parse_error = str(exc)
        parsed_count = len(questions)
        fallback_used = parsed_count < question_count
        if fallback_used:
            questions = [
                *questions,
                *self._fallback_questions(
                    preparation=preparation,
                    question_count=question_count - parsed_count,
                    question_types=question_types,
                    start_index=parsed_count + 1,
                ),
            ]
        questions = questions[:question_count]
        for question in questions:
            question["explanation"] = self._normalize_explanation(question)
        _trace_event(
            "generation_parse_result",
            {
                "topic": topic,
                "requested_count": question_count,
                "parsed_count": parsed_count,
                "final_count": len(questions),
                "fallback_used": fallback_used,
                "parse_error": parse_error,
                "raw_preview": _preview(raw_text),
            },
        )
        question_type = "mixed" if len({item["type"] for item in questions}) > 1 else (questions[0]["type"] if questions else "choice")
        return {
            "artifact_id": f"{conversation_id}:quiz",
            "artifact_type": "quiz",
            "title": f"{topic}-quiz.json",
            "content": {
                "title": f"{topic} quiz",
                "difficulty": difficulty,
                "question_type": question_type,
                "questions": questions,
            },
            "generation_state": {
                "status": "completed",
                "generation_mode": "initial",
                "source_scope": list(preparation.get("source_scope") or []),
                "requested_count": question_count,
                "parsed_count": parsed_count,
                "final_count": len(questions),
                "fallback_used": fallback_used,
                "parse_error": parse_error,
            },
        }
