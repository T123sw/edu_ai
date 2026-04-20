from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.knowledge_base_document_content_provider import KnowledgeBaseDocumentContentProvider
from app.chat.workflows.quiz.generator import QuizGenerator
from app.workspace_scope import SCOPE_TYPE_COURSE
from core.course_storage import storage_manager as default_course_storage_manager


def _extract_text_from_response(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = str(item.get("text") or "").strip()
            else:
                text = str(item or "").strip()
            if text:
                chunks.append(text)
        return "\n".join(chunks).strip()
    return str(content or "").strip()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    return [text] if text else []


class KnowledgeBaseDirectQuizServiceV2:
    def __init__(self, *, content_provider=None, llm=None, course_storage_manager=None):
        self.content_provider = content_provider or KnowledgeBaseDocumentContentProvider()
        self.llm = llm or get_fallback_llm()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager

    def prefill(self, payload):
        selected_doc_ids = [
            _clean(item)
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if _clean(item)
        ]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        if self.llm is None:
            raise RuntimeError("quiz_llm_unavailable")

        owner = _clean(getattr(payload, "owner", "")) or None
        document_result = self.content_provider.get_selected_document_contents(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(document_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents content is empty")

        prompt = self._build_prefill_messages(documents=documents)
        raw = self.llm.invoke(prompt)
        topic, hard_points = self._parse_prefill(raw, documents=documents)
        return {
            "entry_mode": "knowledge_base_quiz",
            "topic": topic,
            "hard_points": hard_points,
            "trace": {
                "path": "direct",
                "selected_doc_count": len(selected_doc_ids),
                "content_doc_count": len(documents),
                "content_truncated": bool(document_result.get("truncated")),
                "generation_mode": "knowledge_base_quiz_prefill",
            },
        }

    def generate(self, payload):
        selected_doc_ids = [
            _clean(item)
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if _clean(item)
        ]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        if self.llm is None:
            raise RuntimeError("quiz_llm_unavailable")

        owner = _clean(getattr(payload, "owner", "")) or None
        document_result = self.content_provider.get_selected_document_contents(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(document_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents content is empty")

        quiz_config = dict(getattr(payload, "quiz_config", {}) or {})
        preparation = {
            "topic": _clean(quiz_config.get("topic")) or self._fallback_topic(documents),
            "question_count": int(quiz_config.get("question_count") or 5),
            "question_types": _coerce_list(quiz_config.get("question_types")) or ["choice"],
            "difficulty": _clean(quiz_config.get("difficulty")) or "medium",
            "knowledge_points": _coerce_list(quiz_config.get("hard_points")),
            "weak_points": [],
            "source_scope": ["selected_docs", "direct_prompt"],
        }

        prompt = self._build_generate_messages(payload=payload, documents=documents, preparation=preparation)
        raw = self.llm.invoke(prompt)
        generator = QuizGenerator(llm=self.llm)
        artifact = generator.build_artifact_from_raw(
            raw=raw,
            preparation=preparation,
            conversation_id=f"direct-quiz-{uuid4().hex[:12]}",
        )
        artifact["generation_state"] = {
            **dict(artifact.get("generation_state") or {}),
            "status": "completed",
            "mode": "knowledge_base_direct",
            "selected_doc_count": len(selected_doc_ids),
        }

        result = {
            "action": {"name": "generate.quiz.direct"},
            "artifacts": [artifact],
            "trace": {
                "path": "direct",
                "selected_doc_count": len(selected_doc_ids),
                "content_doc_count": len(documents),
                "content_truncated": bool(document_result.get("truncated")),
                "generation_mode": "knowledge_base_direct_llm",
            },
        }
        self._persist_quiz(payload=payload, artifact=artifact, selected_doc_ids=selected_doc_ids, documents=documents)
        return result

    def _build_prefill_messages(self, *, documents: list[dict[str, Any]]) -> list[dict[str, str]]:
        doc_lines = []
        for index, document in enumerate(documents, start=1):
            doc_lines.append(
                "\n".join(
                    [
                        f"文档{index}标题：{_clean(document.get('title'))}",
                        f"文档{index}摘要：{_clean(document.get('summary'))}",
                    ]
                )
            )
        return [
            {
                "role": "system",
                "content": (
                    "你是一名教学设计助手。"
                    "请根据用户已勾选的文档，提炼一个适合生成习题的主题 topic，"
                    "并提炼 2 到 4 个学习难点 hard_points。"
                    "只返回 JSON，对象字段固定为 topic 和 hard_points。"
                ),
            },
            {
                "role": "user",
                "content": "\n\n".join(doc_lines),
            },
        ]

    def _build_generate_messages(
        self,
        *,
        payload,
        documents: list[dict[str, Any]],
        preparation: dict[str, Any],
    ) -> list[dict[str, str]]:
        prompt_draft = _clean(getattr(payload, "prompt_draft", ""))
        final_user_prompt = _clean(getattr(payload, "final_user_prompt", "")) or "请直接生成习题。"
        include_answers = bool((getattr(payload, "quiz_config", {}) or {}).get("include_answers", True))
        include_explanations = bool((getattr(payload, "quiz_config", {}) or {}).get("include_explanations", True))

        document_blocks = []
        for index, document in enumerate(documents, start=1):
            document_blocks.append(
                "\n".join(
                    [
                        f"文档{index}标题：{_clean(document.get('title'))}",
                        f"文档{index}摘要：{_clean(document.get('summary'))}",
                        f"文档{index}正文：\n{_clean(document.get('content'))}",
                    ]
                )
            )

        return [
            {
                "role": "system",
                "content": (
                    "你是一名中文习题生成助手。"
                    "请严格基于已选文档生成题目，不要脱离文档编造事实。"
                    "只输出 JSON，顶层字段为 questions。"
                    "每道题字段尽量使用 id、type、question、choices、correct_answer、analysis。"
                    "type 只能是 choice / blank / short / judge。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"固定习题生成提示：{prompt_draft}\n"
                    f"用户最终要求：{final_user_prompt}\n"
                    f"主题：{preparation['topic']}\n"
                    f"难度：{preparation['difficulty']}\n"
                    f"数量：{preparation['question_count']}\n"
                    f"题型：{'、'.join(preparation['question_types'])}\n"
                    f"学习难点：{'、'.join(list(preparation.get('knowledge_points') or [])) or '未指定'}\n"
                    f"是否附答案：{'是' if include_answers else '否'}\n"
                    f"是否附解析：{'是' if include_explanations else '否'}\n\n"
                    f"{chr(10).join(document_blocks)}"
                ),
            },
        ]

    def _parse_prefill(self, raw: Any, *, documents: list[dict[str, Any]]) -> tuple[str, list[str]]:
        text = _extract_text_from_response(raw)
        topic = ""
        hard_points: list[str] = []
        try:
            if "{" in text and "}" in text:
                text = text[text.find("{") : text.rfind("}") + 1]
            payload = json.loads(text)
            topic = _clean(payload.get("topic"))
            hard_points = _coerce_list(payload.get("hard_points"))
        except Exception:
            pass

        if not topic:
            topic = self._fallback_topic(documents)
        if not hard_points:
            hard_points = self._fallback_hard_points(documents)
        return topic, hard_points[:4]

    def _fallback_topic(self, documents: list[dict[str, Any]]) -> str:
        titles = [_clean(item.get("title")) for item in documents if _clean(item.get("title"))]
        if not titles:
            return "基于所选文档的综合练习"
        if len(titles) == 1:
            return titles[0]
        return f"{'、'.join(titles[:2])}综合练习"

    def _fallback_hard_points(self, documents: list[dict[str, Any]]) -> list[str]:
        points: list[str] = []
        for document in documents:
            summary = _clean(document.get("summary"))
            if summary:
                points.append(summary[:24])
            title = _clean(document.get("title"))
            if title and f"理解{title}的核心内容" not in points:
                points.append(f"理解{title}的核心内容")
            if len(points) >= 3:
                break
        return points or ["提炼文档核心信息", "区分重点与难点"]

    def _persist_quiz(self, *, payload, artifact: dict[str, Any], selected_doc_ids: list[str], documents: list[dict[str, Any]]) -> None:
        course_id = _clean(getattr(payload, "course_id", ""))
        if not course_id or self.course_storage_manager is None:
            return

        material_id = _clean(artifact.get("artifact_id"))
        if not material_id:
            return

        self.course_storage_manager.save_generated_material(
            course_id=course_id,
            material_type="quiz",
            material_id=material_id,
            scope_type=_clean(getattr(payload, "scope_type", "")) or SCOPE_TYPE_COURSE,
            scope_id=_clean(getattr(payload, "scope_id", "")) or None,
            material_data={
                "title": _clean(artifact.get("title")) or "quiz",
                "material_type": "quiz",
                "content": artifact.get("content"),
                "generation_state": dict(artifact.get("generation_state") or {}),
                "selected_doc_ids": selected_doc_ids,
                "documents_used": [_clean(item.get("title")) for item in documents if _clean(item.get("title"))],
            },
        )


def build_default_knowledge_base_direct_quiz_service_v2() -> KnowledgeBaseDirectQuizServiceV2:
    return KnowledgeBaseDirectQuizServiceV2(
        content_provider=KnowledgeBaseDocumentContentProvider(),
        llm=get_fallback_llm(),
        course_storage_manager=default_course_storage_manager,
    )
