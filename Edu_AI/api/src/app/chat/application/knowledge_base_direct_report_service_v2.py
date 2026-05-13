from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.knowledge_base_document_content_provider import KnowledgeBaseDocumentContentProvider
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
    def __init__(self, *, content_provider=None, llm=None, course_storage_manager=None):
        self.content_provider = content_provider or KnowledgeBaseDocumentContentProvider()
        self.llm = llm or get_fallback_llm()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager

    def generate(self, payload):
        selected_doc_ids = [
            str(item or "").strip()
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if str(item or "").strip()
        ]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        if self.llm is None:
            raise RuntimeError("report_llm_unavailable")

        owner = str(getattr(payload, "owner", "") or "").strip() or None
        document_result = self.content_provider.get_selected_document_contents(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(document_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents content is empty")

        report_markdown = self._generate_markdown(payload=payload, documents=documents)
        result = {
            "action": {"name": "generate.report.direct"},
            "artifacts": [
                {
                    "artifact_id": f"report-{uuid4().hex[:12]}",
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
                "generation_mode": "knowledge_base_direct_llm",
            },
        }
        finalize_report_result(
            payload=payload,
            result=result,
            course_storage_manager=self.course_storage_manager,
            compact_message=False,
        )
        return result

    def _generate_markdown(self, *, payload, documents: list[dict[str, Any]]) -> str:
        final_user_prompt = str(getattr(payload, "final_user_prompt", "") or "").strip()
        user_question = final_user_prompt or str(getattr(payload, "question", "") or "").strip()
        prompt_draft = str(getattr(payload, "prompt_draft", "") or "").strip()
        selected_card = getattr(payload, "selected_card", None)
        card_title = str((selected_card or {}).get("card_id") if isinstance(selected_card, dict) else getattr(selected_card, "card_id", "") or "").strip()
        report_title = ""
        report_config = getattr(payload, "report_config", None)
        if isinstance(report_config, dict):
            report_title = str(report_config.get("title") or "").strip()

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

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名专业中文报告写作助手。"
                    "现在要基于知识库中已选文档直接生成报告正文。"
                    "不要引用对话历史，不要要求确认，不要输出解释过程。"
                    "请直接输出完整 Markdown 报告正文。"
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
                    "请严格基于以下已选文档内容生成一份中文 Markdown 报告。\n"
                    "报告应当结构完整、内容具体、避免空泛，不得编造文档中不存在的信息。\n\n"
                    f"{chr(10).join(document_blocks)}"
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
