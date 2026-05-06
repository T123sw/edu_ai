from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider
from app.chat.application.ppt_direct_draft_store import (
    get_default_ppt_direct_draft_store,
)
from app.chat.workflows.ppt.outline_builder import PptOutlineBuilder


def _normalize_selected_doc_ids(values: list[str] | None) -> list[str]:
    return [
        str(item or "").strip()
        for item in list(values or [])
        if str(item or "").strip()
    ]


def _normalize_key_points(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        normalized.append(text)
        seen.add(key)
    return normalized


_LENGTH_TO_SLIDE_COUNT = {
    "short": 10,
    "medium": 16,
    "long": 24,
}


def _normalize_length_option(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"short", "medium", "long"}:
        return text
    return "medium"


def _extract_audience(text: str) -> str:
    pairs = [
        ("高中生", "高中生"),
        ("高一", "高中生"),
        ("高二", "高中生"),
        ("高三", "高中生"),
        ("初中生", "初中生"),
        ("小学生", "小学生"),
        ("本科生", "本科生"),
        ("研究生", "研究生"),
        ("教师", "教师"),
    ]
    for token, audience in pairs:
        if token in text:
            return audience
    return ""


def _extract_objective(text: str, card_hint: str) -> str:
    if any(token in text for token in ("答辩", "汇报")):
        return "汇报答辩"
    if any(token in text for token in ("课堂", "讲解", "授课")):
        return "课堂讲解"
    if any(token in text for token in ("分享", "宣讲", "介绍")):
        return "主题分享"
    return card_hint or ""


def _extract_length_option(text: str, explicit_value: str) -> str:
    if any(token in text for token in ("较长", "详细", "完整", "长一些", "20页", "二十页")):
        return "long"
    if any(token in text for token in ("较短", "精简", "简短", "10页", "十页")):
        return "short"
    return explicit_value or "medium"


def _extract_key_points(text: str, explicit_points: list[str]) -> list[str]:
    if explicit_points:
        return explicit_points
    matches = []
    for token in ("定义", "流程", "案例", "应用", "对比", "机制", "总结"):
        if token in text:
            matches.append(token)
    return _normalize_key_points(matches)


class KnowledgeBaseDirectPptOutlineServiceV2:
    def __init__(self, *, summary_provider=None, outline_builder=None, draft_store=None):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()
        self.outline_builder = outline_builder or PptOutlineBuilder()
        self.draft_store = draft_store or get_default_ppt_direct_draft_store()

    def generate_outline(self, payload):
        selected_doc_ids = _normalize_selected_doc_ids(getattr(payload, "selected_doc_ids", []))
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")

        ppt_config = getattr(payload, "ppt_config", None)
        if hasattr(ppt_config, "model_dump"):
            ppt_config_payload = ppt_config.model_dump()
        else:
            ppt_config_payload = dict(ppt_config or {})

        normalized_config = {
            "deck_title": str(ppt_config_payload.get("deck_title") or "").strip(),
            "deck_subtitle": str(ppt_config_payload.get("deck_subtitle") or "").strip() or None,
            "audience": str(ppt_config_payload.get("audience") or "").strip(),
            "objective": str(ppt_config_payload.get("objective") or "").strip(),
            "theme_id": str(ppt_config_payload.get("theme_id") or "heu_academic_elegant").strip(),
            "length_option": _normalize_length_option(ppt_config_payload.get("length_option") or "medium"),
            "target_slide_count": int(ppt_config_payload.get("target_slide_count") or 0),
            "key_points": _normalize_key_points(ppt_config_payload.get("key_points") or []),
            "style_hint": str(ppt_config_payload.get("style_hint") or "").strip() or None,
            "special_requirements": str(ppt_config_payload.get("special_requirements") or "").strip() or None,
            "general_requirements": str(ppt_config_payload.get("general_requirements") or "").strip() or None,
            "selected_card": ppt_config_payload.get("selected_card") or None,
        }
        selected_card = dict(normalized_config.get("selected_card") or {})
        card_objective_hint = {
            "knowledge_lecture": "课堂讲解",
            "topic_briefing": "主题分享",
            "comparison_analysis": "对比分析",
            "defense_summary": "汇报答辩",
        }.get(str(selected_card.get("preset_key") or "").strip(), "")
        general_requirements = str(normalized_config.get("general_requirements") or "")
        normalized_config["audience"] = normalized_config["audience"] or _extract_audience(general_requirements)
        normalized_config["objective"] = normalized_config["objective"] or _extract_objective(general_requirements, card_objective_hint)
        normalized_config["length_option"] = _extract_length_option(general_requirements, normalized_config["length_option"])
        if not normalized_config["target_slide_count"]:
            normalized_config["target_slide_count"] = _LENGTH_TO_SLIDE_COUNT[normalized_config["length_option"]]
        normalized_config["key_points"] = _extract_key_points(general_requirements, normalized_config["key_points"])

        owner = str(getattr(payload, "owner", "") or "").strip() or None
        summary_result = self.summary_provider.get_selected_document_summaries(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(summary_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents summary is empty")

        preparation = SimpleNamespace(
            deck_topic=normalized_config["deck_title"] or "PPT",
            audience=normalized_config["audience"] or "general learners",
            objective=normalized_config["objective"] or "classroom teaching",
            key_points=normalized_config["key_points"] or [normalized_config["deck_title"] or "PPT"],
            slide_count=normalized_config["target_slide_count"],
            theme_id=normalized_config["theme_id"],
            source_basis=[
                str(item.get("title") or "").strip()
                for item in documents
                if str(item.get("title") or "").strip()
            ],
            source_excerpts=[
                str(item.get("summary") or "").strip()
                for item in documents
                if str(item.get("summary") or "").strip()
            ],
        )
        outline = self.outline_builder.build(preparation=preparation)
        draft_id = f"ppt-draft-{uuid4().hex[:12]}"
        snapshot_id = f"snap-{uuid4().hex[:12]}"
        outline_payload = outline.model_dump(exclude_none=True)
        draft = {
            "draft_id": draft_id,
            "course_id": str(getattr(payload, "course_id", "") or "").strip() or None,
            "scope_type": str(getattr(payload, "scope_type", "") or "").strip() or None,
            "scope_id": str(getattr(payload, "scope_id", "") or "").strip() or None,
            "selected_doc_ids": selected_doc_ids,
            "selected_doc_snapshot_id": snapshot_id,
            "selected_doc_snapshot": documents,
            "summary_updated_at_snapshot": list(summary_result.get("summary_updated_at_snapshot") or []),
            "normalized_ppt_config": normalized_config,
            "draft_outline": outline_payload,
            "status": "outline_ready",
        }
        self.draft_store.save(draft)

        return {
            "action": {"name": "generate.ppt.outline.direct"},
            "draft": {
                "draft_id": draft_id,
                "status": "outline_ready",
                "selected_doc_snapshot_id": snapshot_id,
            },
            "artifacts": [
                {
                    "artifact_id": f"{draft_id}:outline",
                    "artifact_type": "ppt_outline",
                    "title": f"{outline.deck_title}.outline.json",
                    "content": outline_payload,
                }
            ],
            "trace": {
                "path": "direct",
                "draft_id": draft_id,
                "source_scope": "selected_documents_only",
                "uses_chat_context": False,
                "selected_doc_snapshot_id": snapshot_id,
                "selected_doc_count": len(selected_doc_ids),
            },
        }


def build_default_knowledge_base_direct_ppt_outline_service_v2() -> KnowledgeBaseDirectPptOutlineServiceV2:
    return KnowledgeBaseDirectPptOutlineServiceV2(
        summary_provider=KnowledgeBaseSummaryProvider(),
        outline_builder=PptOutlineBuilder(llm=get_fallback_llm()),
        draft_store=get_default_ppt_direct_draft_store(),
    )
