from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.knowledge_base_document_content_provider import (
    KnowledgeBaseDocumentContentProvider,
    get_generation_document_contents,
)
from app.chat.application.report_service_v2 import finalize_report_result
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


class KnowledgeBaseDirectReportServiceV2:
    def __init__(
        self,
        *,
        content_provider=None,
        llm=None,
        course_storage_manager=None,
    ):
        self.content_provider = content_provider or KnowledgeBaseDocumentContentProvider()
        self.llm = llm or get_fallback_llm()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager

    def generate(
        self,
        payload,
        *,
        job_id: str | None = None,
        config_snapshot_id: str | None = None,
        progress=None,
    ):
        selected_doc_ids = [
            str(item or "").strip()
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if str(item or "").strip()
        ]
        if self.llm is None:
            raise RuntimeError("report_llm_unavailable")

        owner = str(getattr(payload, "owner", "") or "").strip() or None
        document_result = {"documents": [], "truncated": False}
        if selected_doc_ids:
            document_result = get_generation_document_contents(
                self.content_provider,
                payload=payload,
                selected_doc_ids=selected_doc_ids,
                owner=owner,
            )
        documents = list(document_result.get("documents") or [])
        if selected_doc_ids and not documents:
            raise ValueError("selected documents content is empty")

        research_context = str(getattr(payload, "research_context", "") or "").strip()
        if research_context:
            documents.append({"document_id": "course-context", "title": "当前课程资料", "content": research_context})

        notify = progress or (lambda *_args: None)
        notify(15, 'writing', '正在编写报告正文')
        report_markdown = self._generate_markdown(payload=payload, documents=documents)
        result = {
            "action": {"name": "generate.report.direct"},
            "artifacts": [
                {
                    "artifact_id": str(
                        getattr(payload, "material_id", "") or ""
                    ).strip()
                    or f"report-{uuid4().hex[:12]}",
                    "artifact_type": "report",
                    "title": "报告.md",
                    "content": report_markdown,
                    "generation_state": {
                        "status": "completed",
                        "mode": "knowledge_base_direct",
                    },
                    "version": {
                        "version_id": "v1",
                        "version_number": 1,
                        "root_artifact_id": None,
                        "parent_artifact_id": None,
                    },
                }
            ],
            "trace": {
                "path": "direct",
                "selected_doc_count": len(selected_doc_ids),
                "content_doc_count": len(documents),
                "content_truncated": bool(document_result.get("truncated")),
                "generation_mode": (
                    "knowledge_base_direct_llm"
                    if documents
                    else "topic_direct_llm"
                ),
            },
        }
        notify(90, 'saving', '正在保存报告')
        finalize_report_result(
            payload=payload,
            result=result,
            course_storage_manager=self.course_storage_manager,
            compact_message=False,
        )
        return result

    def _generate_markdown(
        self,
        *,
        payload,
        documents: list[dict[str, Any]],
    ) -> str:
        final_user_prompt = str(getattr(payload, "final_user_prompt", "") or "").strip()
        user_question = final_user_prompt or str(getattr(payload, "question", "") or "").strip()
        prompt_draft = str(getattr(payload, "prompt_draft", "") or "").strip()
        selected_card = getattr(payload, "selected_card", None)
        card_title = str((selected_card or {}).get("card_id") if isinstance(selected_card, dict) else getattr(selected_card, "card_id", "") or "").strip()
        report_title = ""
        report_config = getattr(payload, "report_config", None)
        if isinstance(report_config, dict):
            report_title = str(report_config.get("title") or "").strip()
        effective_config = {
            key: report_config.get(key)
            for key in (
                "template",
                "audience",
                "depth",
                "structure_emphasis",
                "special_requirements",
            )
            if isinstance(report_config, dict)
            and report_config.get(key) not in (None, "")
        }
        config_instruction = (
            "\n以下报告配置必须实际体现在措辞、详略和结构中：\n"
            + json.dumps(effective_config, ensure_ascii=False)
            if effective_config
            else ""
        )

        document_blocks: list[str] = []
        for index, document in enumerate(documents, start=1):
            document_blocks.append(
                "\n".join(
                    [
                        f"文档{index}标题：{str(document.get('title') or '').strip()}",
                        f"文档{index}摘要：{str(document.get('summary') or '').strip()}",
                        f"文档{index}正文：\n{str(document.get('content') or '').strip()}",
                    ]
                )
            )

        has_documents = bool(document_blocks)
        grounding_instruction = (
            "现在要基于知识库中已选文档直接生成报告正文。"
            "不得编造文档中不存在的信息。"
            if has_documents
            else "本次未提供课程资料，请围绕用户给出的主题和要求，基于通用知识生成报告。"
            "不要声称引用了未提供的课程资料。"
        )
        source_section = (
            "请严格基于以下已选文档内容生成一份中文 Markdown 报告。\n\n"
            + "\n".join(document_blocks)
            if has_documents
            else "本次不使用课程资料，请直接围绕主题完成报告。"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名专业中文报告写作助手。"
                    f"{grounding_instruction}"
                    "不要引用对话历史，不要要求确认，不要输出解释过程。"
                    "请直接输出完整 Markdown 报告正文，以文字、表格和代码解释内容，不插入图片或图片占位符。"
                    "如果用户给了明确标题，就使用该标题作为一级标题；否则自行概括一个准确标题。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户最终要求：{user_question}\n"
                    f"默认提示草稿：{prompt_draft}\n"
                    f"所选卡片：{card_title or '未指定'}\n"
                    f"期望标题：{report_title or '未指定'}\n\n"
                    "报告应当结构完整、内容具体、避免空泛。\n\n"
                    f"{source_section}{config_instruction}"
                ),
            },
        ]
        response = self.llm.invoke(messages)
        report_markdown = _extract_text_from_response(response)
        if not report_markdown:
            raise RuntimeError("report_generation_empty")
        return report_markdown


def build_default_knowledge_base_direct_report_service_v2() -> KnowledgeBaseDirectReportServiceV2:
    return KnowledgeBaseDirectReportServiceV2(
        content_provider=KnowledgeBaseDocumentContentProvider(),
        llm=get_fallback_llm(),
        course_storage_manager=default_course_storage_manager,
    )
