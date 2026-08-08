from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any

from .models import (
    SelectedVisual,
    VisualBrief,
    VisualPipelineResult,
    VisualSlot,
)
from .planner import parse_visual_brief


_MIN_DIMENSION = 240


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return {
        key: getattr(value, key)
        for key in (
            "url",
            "source_page",
            "title",
            "alt",
            "width",
            "height",
            "document_id",
        )
        if hasattr(value, key)
    }


class VisualAssetPipeline:
    def __init__(
        self,
        *,
        knowledge_search: Callable[..., list] | None = None,
        web_search: Callable[..., list] | None = None,
        localize: Callable[..., Any] | None = None,
        rank: Callable[[VisualSlot, dict[str, Any]], float] | None = None,
    ) -> None:
        self.knowledge_search = knowledge_search
        self.web_search = web_search
        self.localize = localize or self._default_localize
        self.rank = rank or self._default_rank

    def plan_with_model(
        self,
        llm,
        *,
        resource_type: str,
        topic: str,
        source_context: str = "",
    ) -> VisualBrief:
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "你是教学资源结构与配图规划器。只返回 JSON，不写正文。"
                        "先给出 outline，再为确实需要视觉支撑的位置给出 visuals。"
                        "图片不是越多越好；不需要图片的章节不要创建槽位。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"resource_type={resource_type}\n"
                        f"topic={topic}\n"
                        f"source_context={source_context[:6000]}\n"
                        "返回结构："
                        '{"outline":[{"section_id":"...","title":"..."}],'
                        '"visuals":[{"section_id":"...","purpose":"...",'
                        '"query":"英文或精确检索词","preferred_kind":"diagram|chart|photo|illustration|any",'
                        '"required":false,"caption_hint":"...",'
                        '"source_preference":["knowledge_base","web"]}]}。'
                    ),
                },
            ]
        )
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "\n".join(
                str(item.get("text") or "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return parse_visual_brief(
            str(content or ""),
            resource_type=resource_type,
            topic=topic,
        )

    def run(
        self,
        brief: VisualBrief,
        *,
        course_id: str,
        owner: str | None,
        selected_document_ids: list[str],
    ) -> VisualPipelineResult:
        selected: list[SelectedVisual] = []
        rejected: Counter[str] = Counter()
        candidate_count = 0
        seen_hashes: set[str] = set()

        for slot in brief.slots:
            candidates: list[dict[str, Any]] = []
            slot_hashes = set(seen_hashes)
            if self.knowledge_search and selected_document_ids:
                for raw in self.knowledge_search(
                    query=slot.query,
                    selected_document_ids=list(selected_document_ids),
                    course_id=course_id,
                    owner=owner,
                ) or []:
                    candidates.append(
                        {**_dict(raw), "source_type": "knowledge_base"}
                    )
            if self.web_search:
                for raw in self.web_search(
                    query=slot.query,
                    kind=slot.preferred_kind,
                    owner=owner,
                ) or []:
                    candidates.append({**_dict(raw), "source_type": "web"})

            candidate_count += len(candidates)
            qualified: list[tuple[float, dict[str, Any]]] = []
            for candidate in candidates:
                url = str(candidate.get("url") or "").strip()
                if not url:
                    rejected["missing_url"] += 1
                    continue
                width = int(candidate.get("width") or 0)
                height = int(candidate.get("height") or 0)
                if (width and width < _MIN_DIMENSION) or (
                    height and height < _MIN_DIMENSION
                ):
                    rejected["too_small"] += 1
                    continue
                localized = _dict(
                    self.localize(
                        candidate,
                        course_id=course_id,
                        owner=owner,
                    )
                )
                local_url = str(
                    localized.get("local_url")
                    or localized.get("url")
                    or ""
                ).strip()
                if not local_url:
                    rejected["localization_failed"] += 1
                    continue
                content_hash = str(
                    localized.get("content_hash")
                    or hashlib.sha256(url.encode("utf-8")).hexdigest()
                )
                if content_hash in slot_hashes:
                    rejected["duplicate"] += 1
                    continue
                slot_hashes.add(content_hash)
                merged = {
                    **candidate,
                    **localized,
                    "local_url": local_url,
                    "content_hash": content_hash,
                }
                qualified.append((self.rank(slot, merged), merged))

            if not qualified:
                rejected["no_qualified_candidate"] += 1
                continue
            score, chosen = max(qualified, key=lambda item: item[0])
            seen_hashes.add(str(chosen["content_hash"]))
            title = str(chosen.get("title") or chosen.get("alt") or "图片").strip()
            selected.append(
                SelectedVisual(
                    slot_id=slot.slot_id,
                    local_url=str(chosen["local_url"]),
                    title=title,
                    caption=slot.caption_hint or title,
                    source_page=str(chosen.get("source_page") or ""),
                    source_type=str(chosen.get("source_type") or "web"),
                    score=float(score),
                )
            )

        return VisualPipelineResult(
            brief=brief,
            selected=tuple(selected),
            candidate_count=candidate_count,
            rejected_counts=dict(rejected),
        )

    @staticmethod
    def assemble(markdown: str, selected: list[SelectedVisual] | tuple[SelectedVisual, ...]) -> str:
        locked = {item.slot_id: item for item in selected}

        def replace(match: re.Match[str]) -> str:
            item = locked.get(match.group(1).strip())
            if item is None:
                return ""
            caption = item.caption or item.title or "图片"
            attribution = (
                f"\n\n> {caption} · [图片来源]({item.source_page})"
                if item.source_page.startswith(("http://", "https://"))
                else f"\n\n> {caption}"
            )
            return f"![{caption}]({item.local_url}){attribution}"

        return re.sub(r"\{\{VISUAL:([^}]+)\}\}", replace, markdown)

    @staticmethod
    def _default_rank(slot: VisualSlot, candidate: dict[str, Any]) -> float:
        source_type = str(candidate.get("source_type") or "web")
        source_score = 1.0 if source_type == slot.source_preference[0] else 0.7
        width = int(candidate.get("width") or 0)
        height = int(candidate.get("height") or 0)
        resolution_score = min((width * height) / 1_000_000, 1.0) if width and height else 0.5
        return source_score + (resolution_score * 0.2)

    @staticmethod
    def _default_localize(candidate: dict[str, Any], **kwargs) -> dict[str, Any]:
        url = str(candidate.get("url") or "")
        if url.startswith("/"):
            return {
                **candidate,
                "local_url": url,
                "content_hash": hashlib.sha256(url.encode("utf-8")).hexdigest(),
            }
        from app.chat.workflows.report.image_downloader import (
            LocalizedAsset,
            localize_image,
        )

        result = localize_image(
            candidate,
            owner=kwargs.get("owner"),
            course_id=kwargs.get("course_id"),
        )
        if isinstance(result, LocalizedAsset):
            return {
                **candidate,
                "local_url": result.local_url,
                "content_hash": result.hash,
            }
        return {}
