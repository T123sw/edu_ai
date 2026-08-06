from __future__ import annotations

import hashlib
import os
import time
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.knowledge_base_summary_provider import (
    KnowledgeBaseSummaryProvider,
)
from app.chat.application.ppt_direct_draft_store import (
    get_default_ppt_direct_draft_store,
)
from app.chat.domain.ppt_outline import PptOutline
from app.chat.workflows.ppt.content_gate import PptContentGate
from app.chat.workflows.ppt.content_markdown_generator import (
    PptContentMarkdownGenerator,
)
from app.chat.workflows.ppt.html2ppt_client import Html2PptClient
from app.chat.workflows.ppt.outline_builder import PptOutlineBuilder
from app.services.job_store import JobStatus, get_job, update_job
from app.workspace_scope import SCOPE_TYPE_COURSE
from core.course_storage import storage_manager as default_course_storage_manager


_LENGTH_TO_SLIDE_COUNT = {"short": 8, "medium": 12, "long": 18}
_SUPPORTED_THEMES = {"heu_academic_elegant", "heu_academic_basic"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


class KnowledgeBaseDirectPptServiceV2:
    def __init__(
        self,
        *,
        summary_provider=None,
        outline_builder=None,
        content_generator=None,
        content_gate=None,
        draft_store=None,
        html2ppt_client=None,
        course_storage_manager=None,
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 900,
    ):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()
        self.outline_builder = outline_builder or PptOutlineBuilder()
        self.content_generator = content_generator or PptContentMarkdownGenerator()
        self.content_gate = content_gate or PptContentGate()
        self.draft_store = draft_store or get_default_ppt_direct_draft_store()
        self.html2ppt_client = html2ppt_client or Html2PptClient(
            base_url=os.getenv("HTML2PPT_BASE_URL", "http://127.0.0.1:46080")
        )
        self.course_storage_manager = (
            course_storage_manager or default_course_storage_manager
        )
        self.poll_interval_seconds = max(0.0, float(poll_interval_seconds))
        self.max_poll_attempts = max(1, int(max_poll_attempts))

    def generate_outline(self, payload) -> dict[str, Any]:
        owner = _clean(getattr(payload, "owner", ""))
        selected_doc_ids = list(
            dict.fromkeys(
                _clean(item)
                for item in list(getattr(payload, "selected_doc_ids", []) or [])
                if _clean(item)
            )
        )
        if not owner:
            raise ValueError("owner is required")
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        config = dict(getattr(payload, "ppt_config", {}) or {})
        length = _clean(config.get("length_option")).lower()
        if length not in _LENGTH_TO_SLIDE_COUNT:
            length = "medium"
        target_count = int(config.get("target_slide_count") or 0)
        target_count = max(5, min(30, target_count or _LENGTH_TO_SLIDE_COUNT[length]))
        theme_id = _clean(config.get("theme_id"))
        if theme_id not in _SUPPORTED_THEMES:
            theme_id = "heu_academic_elegant"

        summary_result = self.summary_provider.get_selected_document_summaries(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(summary_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents summary is empty")
        title = _clean(config.get("deck_title")) or _clean(documents[0].get("title")) or "课程课件"
        key_points = [
            _clean(item)
            for item in list(config.get("key_points") or [])
            if _clean(item)
        ]
        preparation = SimpleNamespace(
            deck_topic=title,
            audience=_clean(config.get("audience")) or "课程学习者",
            objective=_clean(config.get("objective")) or "课堂讲解",
            key_points=key_points or [title],
            slide_count=target_count,
            theme_id=theme_id,
            source_basis=[
                _clean(item.get("title"))
                for item in documents
                if _clean(item.get("title"))
            ],
            source_excerpts=[
                _clean(item.get("summary"))
                for item in documents
                if _clean(item.get("summary"))
            ],
        )
        outline = self.outline_builder.build(preparation=preparation)
        draft_id = f"ppt-draft-{uuid4().hex[:16]}"
        outline_payload = outline.model_dump(exclude_none=True)
        normalized_config = {
            **config,
            "deck_title": title,
            "length_option": length,
            "target_slide_count": target_count,
            "theme_id": theme_id,
            "key_points": key_points,
        }
        self.draft_store.save(
            owner=owner,
            draft={
                "draft_id": draft_id,
                "course_id": _clean(getattr(payload, "course_id", "")),
                "scope_type": _clean(getattr(payload, "scope_type", ""))
                or SCOPE_TYPE_COURSE,
                "scope_id": _clean(getattr(payload, "scope_id", "")) or None,
                "selected_doc_ids": selected_doc_ids,
                "selected_doc_snapshot": documents,
                "normalized_ppt_config": normalized_config,
                "draft_outline": outline_payload,
                "status": "outline_ready",
            },
        )
        return {
            "action": {"name": "generate.ppt.outline.direct"},
            "draft": {"draft_id": draft_id, "status": "outline_ready"},
            "artifacts": [
                {
                    "artifact_id": f"{draft_id}:outline",
                    "artifact_type": "ppt_outline",
                    "title": f"{title}-大纲",
                    "content": outline_payload,
                }
            ],
            "trace": {
                "path": "direct",
                "selected_doc_count": len(selected_doc_ids),
                "source_scope": "selected_documents_only",
            },
        }

    def get_draft(self, *, owner: str, draft_id: str) -> dict[str, Any]:
        return self.draft_store.get(owner=owner, draft_id=draft_id)

    def generate(
        self,
        payload,
        *,
        job_id: str,
        config_snapshot_id: str,
    ) -> dict[str, Any]:
        owner = _clean(getattr(payload, "owner", ""))
        draft_id = _clean(getattr(payload, "draft_id", ""))
        if not bool(getattr(payload, "confirm", False)):
            raise ValueError("confirm is required")
        draft = self.draft_store.get(owner=owner, draft_id=draft_id)
        outline_payload = dict(
            getattr(payload, "outline", None) or draft.get("draft_outline") or {}
        )
        outline = PptOutline.model_validate(outline_payload)
        config = dict(draft.get("normalized_ppt_config") or {})
        preparation = SimpleNamespace(
            topic=outline.deck_title,
            deck_topic=outline.deck_title,
            audience=_clean(config.get("audience")) or "课程学习者",
            objective=_clean(config.get("objective")) or "课堂讲解",
            key_points=list(config.get("key_points") or []),
            theme_id=outline.theme_id,
            slide_count=len(list(outline.slides or [])),
            source_basis=[
                _clean(item.get("title"))
                for item in list(draft.get("selected_doc_snapshot") or [])
                if _clean(item.get("title"))
            ],
            source_excerpts=[
                _clean(item.get("summary"))
                for item in list(draft.get("selected_doc_snapshot") or [])
                if _clean(item.get("summary"))
            ],
        )
        content_markdown, _debug = self.content_generator.generate(
            outline=outline,
            preparation=preparation,
        )
        gated = self.content_gate.apply(
            content_markdown=content_markdown,
            outline=outline,
        )
        if not bool(gated.get("ok")):
            raise ValueError("PPT 内容校验失败，请调整大纲后重试")
        final_markdown = _clean(gated.get("final_markdown")) or content_markdown
        digest = hashlib.sha256(
            f"{owner}:{draft_id}:{final_markdown}".encode("utf-8")
        ).hexdigest()[:16]
        created = self.html2ppt_client.create_job(
            content_markdown=final_markdown,
            theme_id=outline.theme_id,
            metadata={
                "request_id": job_id,
                "idempotency_key": f"ppt-{digest}",
                "user_id": owner,
            },
        )
        provider_job_id = _clean(created.get("job_id"))
        if not provider_job_id:
            raise RuntimeError("PPT 引擎未返回任务编号")
        update_job(
            job_id,
            step="exporting_pptx",
            progress=35,
            message="正在生成并导出 PPTX",
            provider_job_ref={"provider": "html2ppt", "job_id": provider_job_id},
        )
        status = dict(created)
        results: dict[str, Any] | None = None
        for _ in range(self.max_poll_attempts):
            active_job = get_job(job_id)
            if active_job and active_job.status == JobStatus.CANCEL_REQUESTED:
                raise RuntimeError("PPT 生成已取消")
            status = self.html2ppt_client.get_job_status(provider_job_id)
            normalized_status = _clean(status.get("status")).lower()
            progress = max(35, min(95, int(status.get("progress") or 0)))
            update_job(
                job_id,
                step=_clean(status.get("phase")) or "exporting_pptx",
                progress=progress,
                message=_clean(status.get("message")) or "正在导出 PPTX",
            )
            if normalized_status == "succeeded":
                results = self.html2ppt_client.get_job_results(provider_job_id)
                break
            if normalized_status == "failed":
                raise RuntimeError(
                    _clean(status.get("message")) or "PPT 引擎生成失败"
                )
            time.sleep(self.poll_interval_seconds)
        if results is None:
            raise TimeoutError("PPT 生成超时，请稍后重试")

        result_payload = dict(results.get("results") or {})
        result_payload.update(
            {
                "job_id": provider_job_id,
                "slide_count": int(results.get("slide_count") or len(outline.slides)),
                "content_markdown": final_markdown,
            }
        )
        material_id = (
            _clean(getattr(payload, "material_id", ""))
            or f"ppt-{uuid4().hex[:16]}"
        )
        generation_state = {
            "status": "completed",
            "phase": "completed",
            "progress": 100,
            "provider_job_id": provider_job_id,
        }
        saved = bool(
            self.course_storage_manager.save_generated_material(
                course_id=_clean(draft.get("course_id")),
                material_type="ppt",
                material_id=material_id,
                scope_type=_clean(draft.get("scope_type")) or SCOPE_TYPE_COURSE,
                scope_id=_clean(draft.get("scope_id")) or None,
                owner_user_id=owner,
                source_job_id=job_id,
                config_snapshot_id=config_snapshot_id,
                material_data={
                    "title": f"{outline.deck_title}.pptx",
                    "content": result_payload,
                    "outline": outline_payload,
                    "generation_state": generation_state,
                    "source": {
                        "selected_doc_ids": list(draft.get("selected_doc_ids") or []),
                        "draft_id": draft_id,
                    },
                },
            )
        )
        return {
            "saved": saved,
            "error": None if saved else "course material manifest write failed",
            "artifacts": [
                {
                    "artifact_id": material_id,
                    "artifact_type": "ppt_deck",
                    "title": f"{outline.deck_title}.pptx",
                    "content": result_payload,
                    "generation_state": generation_state,
                }
            ],
            "result_ref": {
                "resource_type": "course_material" if saved else "generated_artifact",
                "course_id": _clean(draft.get("course_id")),
                "material_type": "ppt",
                "material_id": material_id,
            },
        }


def build_default_knowledge_base_direct_ppt_service_v2():
    llm = get_fallback_llm()
    return KnowledgeBaseDirectPptServiceV2(
        summary_provider=KnowledgeBaseSummaryProvider(),
        outline_builder=PptOutlineBuilder(llm=llm),
        content_generator=PptContentMarkdownGenerator(llm=llm),
        content_gate=PptContentGate(),
        draft_store=get_default_ppt_direct_draft_store(),
        course_storage_manager=default_course_storage_manager,
    )

