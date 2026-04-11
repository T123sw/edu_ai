from __future__ import annotations

import os
from types import SimpleNamespace

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.ppt_direct_draft_store import get_default_ppt_direct_draft_store
from app.chat.application.report_service_v2 import _persist_ppt_course_material
from app.chat.domain.ppt_outline import PptOutline
from app.chat.workflows.ppt.content_markdown_generator import PptContentMarkdownGenerator
from app.chat.workflows.ppt.content_validator import PptContentValidator
from app.chat.workflows.ppt.html2ppt_client import Html2PptClient
from app.chat.workflows.ppt.post_outline_executor import PptPostOutlineExecutor
from core.course_storage import storage_manager as default_course_storage_manager


class _DirectPreparation:
    def __init__(
        self,
        *,
        deck_title: str,
        audience: str,
        objective: str,
        key_points: list[str],
        theme_id: str,
        slide_count: int | None,
        source_basis: list[str],
        source_excerpts: list[str],
    ) -> None:
        self.topic = deck_title
        self.deck_topic = deck_title
        self.audience = audience
        self.objective = objective
        self.key_points = list(key_points or [])
        self.theme_id = theme_id
        self.slide_count = slide_count
        self.source_basis = list(source_basis or [])
        self.source_excerpts = list(source_excerpts or [])

    def model_dump(self, exclude_none: bool = True) -> dict:
        payload = {
            "topic": self.topic,
            "audience": self.audience,
            "objective": self.objective,
            "key_points": list(self.key_points or []),
            "source_basis": list(self.source_basis or []),
            "source_excerpts": list(self.source_excerpts or []),
            "theme": self.theme_id,
            "page_count": self.slide_count,
        }
        if not exclude_none:
            return payload
        return {key: value for key, value in payload.items() if value not in (None, "", [])}


def build_direct_ppt_metadata_from_draft(*, draft_id: str, draft: dict) -> dict:
    normalized_config = dict(draft.get("normalized_ppt_config") or {})
    source_snapshot = list(draft.get("selected_doc_snapshot") or [])
    preparation = _DirectPreparation(
        deck_title=str(normalized_config.get("deck_title") or "").strip() or "PPT",
        audience=str(normalized_config.get("audience") or "").strip() or "general learners",
        objective=str(normalized_config.get("objective") or "").strip() or "classroom teaching",
        key_points=[str(item).strip() for item in list(normalized_config.get("key_points") or []) if str(item).strip()],
        theme_id=str(normalized_config.get("theme_id") or "heu_academic_elegant").strip(),
        slide_count=int(normalized_config.get("target_slide_count") or 0) or None,
        source_basis=[
            str(item.get("title") or "").strip()
            for item in source_snapshot
            if str(item.get("title") or "").strip()
        ],
        source_excerpts=[
            str(item.get("summary") or "").strip()
            for item in source_snapshot
            if str(item.get("summary") or "").strip()
        ],
    )
    return {
        "artifact_scope_id": draft_id,
        "draft_id": draft_id,
        "preparation": preparation,
        "trace": {
            "path": "direct",
            "draft_id": draft_id,
            "source_scope": "selected_documents_only",
            "uses_chat_context": False,
            "selected_doc_snapshot_id": draft.get("selected_doc_snapshot_id"),
        },
    }


class KnowledgeBaseDirectPptGenerationServiceV2:
    def __init__(self, *, draft_store=None, post_outline_executor=None, course_storage_manager=None):
        self.draft_store = draft_store or get_default_ppt_direct_draft_store()
        self.post_outline_executor = post_outline_executor or PptPostOutlineExecutor()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager

    def generate(self, payload):
        draft_id = str(getattr(payload, "draft_id", "") or "").strip()
        if not draft_id:
            raise ValueError("draft_id is required")
        if not bool(getattr(payload, "confirm", False)):
            raise ValueError("confirm is required")

        draft = self.draft_store.get(draft_id)
        outline_payload = dict(getattr(payload, "outline", None) or draft.get("draft_outline") or {})
        outline = PptOutline.model_validate(outline_payload)
        request = SimpleNamespace(
            conversation_id="",
            owner=str(getattr(payload, "owner", "") or "").strip(),
        )
        metadata = build_direct_ppt_metadata_from_draft(draft_id=draft_id, draft=draft)
        result = self.post_outline_executor.execute(outline=outline, request=request, metadata=metadata)
        if "action" in result and "run" in result:
            response = result
        else:
            response = {
                "action": {"name": "generate.ppt.direct"},
                "run": {
                    "run_id": str(result.get("run_id") or f"ppt-run-{draft_id}"),
                    "status": str(result.get("status") or "running"),
                    "job_id": str(result.get("job_id") or ""),
                },
                "artifacts": list(result.get("artifacts") or []),
                "trace": dict(result.get("trace") or {}),
            }
        _persist_ppt_course_material(
            payload=SimpleNamespace(course_id=draft.get("course_id")),
            result={"artifacts": response.get("artifacts") or []},
            course_storage_manager=self.course_storage_manager,
        )
        return response


def build_default_knowledge_base_direct_ppt_generation_service_v2() -> KnowledgeBaseDirectPptGenerationServiceV2:
    return KnowledgeBaseDirectPptGenerationServiceV2(
        draft_store=get_default_ppt_direct_draft_store(),
        post_outline_executor=PptPostOutlineExecutor(
            content_markdown_generator=PptContentMarkdownGenerator(llm=get_fallback_llm()),
            content_validator=PptContentValidator(),
            html2ppt_client_factory=lambda: Html2PptClient(
                base_url=os.getenv("HTML2PPT_BASE_URL", "http://127.0.0.1:46080")
            ),
        ),
        course_storage_manager=default_course_storage_manager,
    )
