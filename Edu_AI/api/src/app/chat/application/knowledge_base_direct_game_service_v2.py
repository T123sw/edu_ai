from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from jsonschema import ValidationError, validate

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.game_template_registry import get_game_template_spec
from app.chat.application.knowledge_base_document_content_provider import KnowledgeBaseDocumentContentProvider
from app.workspace_scope import SCOPE_TYPE_COURSE
from core.config import Config
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


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return cleaned or fallback


class KnowledgeBaseDirectGameServiceV2:
    def __init__(self, *, content_provider=None, llm=None, course_storage_manager=None, storage_root=None):
        self.content_provider = content_provider or KnowledgeBaseDocumentContentProvider()
        self.llm = llm or get_fallback_llm()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager
        self.storage_root = Path(storage_root or (Config.STORAGE_ROOT / "chat_games")).resolve()

    def generate(self, payload):
        selected_doc_ids = [
            _clean(item)
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if _clean(item)
        ]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        if self.llm is None:
            raise RuntimeError("game_llm_unavailable")

        template = get_game_template_spec(_clean(getattr(payload, "game_type", "")))
        owner = _clean(getattr(payload, "owner", "")) or "anonymous"
        documents = self._load_documents(selected_doc_ids=selected_doc_ids, owner=owner)
        game_data = self._generate_validated_game_data(template=template, documents=documents)
        artifact_id = f"game-{uuid4().hex[:12]}"
        html_relative_path, html_url = self._render_html(
            owner=owner,
            course_id=_clean(getattr(payload, "course_id", "")) or "direct",
            artifact_id=artifact_id,
            template=template,
            game_data=game_data,
        )
        artifact = {
            "artifact_id": artifact_id,
            "artifact_type": "game",
            "title": f"{_clean(game_data.get('title')) or template.display_name}.html",
            "content": {
                "game_type": template.game_type,
                "template_id": template.template_id,
                "game_data": game_data,
                "html_path": html_relative_path,
                "html_url": html_url,
            },
            "generation_state": {
                "status": "completed",
                "mode": "knowledge_base_direct",
                "selected_doc_count": len(selected_doc_ids),
            },
        }
        self._persist_game(payload=payload, artifact=artifact, selected_doc_ids=selected_doc_ids, documents=documents)
        return {
            "action": {"name": "generate.game.direct"},
            "artifacts": [artifact],
            "trace": {
                "path": "direct",
                "generation_mode": "knowledge_base_direct_game",
                "selected_doc_count": len(selected_doc_ids),
                "content_doc_count": len(documents),
            },
        }

    def _load_documents(self, *, selected_doc_ids: list[str], owner: str | None) -> list[dict[str, Any]]:
        document_result = self.content_provider.get_selected_document_contents(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(document_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents content is empty")
        return documents

    def _generate_validated_game_data(self, *, template, documents: list[dict[str, Any]]) -> dict[str, Any]:
        schema = json.loads(template.schema_path.read_text(encoding="utf-8"))
        messages = self._build_generate_messages(template=template, documents=documents, schema=schema)
        first_text = _extract_text_from_response(self.llm.invoke(messages))
        try:
            return self._parse_and_validate_json(first_text, schema=schema)
        except ValueError as exc:
            repair_messages = self._build_repair_messages(
                template=template,
                documents=documents,
                schema=schema,
                invalid_json=first_text,
                error_text=str(exc),
            )
            second_text = _extract_text_from_response(self.llm.invoke(repair_messages))
            try:
                return self._parse_and_validate_json(second_text, schema=schema)
            except ValueError as repair_exc:
                raise ValueError("game_generation_invalid_schema") from repair_exc

    def _build_generate_messages(self, *, template, documents: list[dict[str, Any]], schema: dict[str, Any]) -> list[dict[str, str]]:
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
                    "你是一个教学小游戏数据生成助手。"
                    "请严格基于已选文档生成小游戏内容，不要编造文档之外的信息。"
                    "你只能输出 JSON，且必须严格符合给定 schema。"
                    f"目标游戏类型：{template.display_name}。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
                    f"{chr(10).join(document_blocks)}"
                ),
            },
        ]

    def _build_repair_messages(
        self,
        *,
        template,
        documents: list[dict[str, Any]],
        schema: dict[str, Any],
        invalid_json: str,
        error_text: str,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你必须修复一个不合法的小游戏 JSON。"
                    "仅输出修复后的 JSON，不要输出解释。"
                    f"目标游戏类型：{template.display_name}。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"校验错误：{error_text}\n"
                    f"目标 Schema：{json.dumps(schema, ensure_ascii=False)}\n"
                    f"原始 JSON：{invalid_json}\n"
                    f"文档标题：{'；'.join(_clean(item.get('title')) for item in documents if _clean(item.get('title')))}"
                ),
            },
        ]

    def _parse_and_validate_json(self, text: str, *, schema: dict[str, Any]) -> dict[str, Any]:
        raw = text.strip()
        if "{" in raw and "}" in raw:
            raw = raw[raw.find("{") : raw.rfind("}") + 1]
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid_json:{exc}") from exc
        try:
            validate(instance=payload, schema=schema)
        except ValidationError as exc:
            raise ValueError(f"invalid_schema:{exc.message}") from exc
        return payload

    def _render_html(self, *, owner: str, course_id: str, artifact_id: str, template, game_data: dict[str, Any]) -> tuple[str, str]:
        owner_segment = _safe_segment(owner, "anonymous")
        course_segment = _safe_segment(course_id, "direct")
        target_dir = (self.storage_root / owner_segment / course_segment / artifact_id).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        html = template.html_template_path.read_text(encoding="utf-8").replace(
            "__GAME_DATA_JSON__",
            json.dumps(game_data, ensure_ascii=False),
        )
        target_path = (target_dir / "index.html").resolve()
        target_path.write_text(html, encoding="utf-8")
        relative_path = target_path.relative_to(self.storage_root).as_posix()
        html_url = f"/api/chat/v2/games/html?path={quote(relative_path, safe='')}"
        return relative_path, html_url

    def _persist_game(self, *, payload, artifact: dict[str, Any], selected_doc_ids: list[str], documents: list[dict[str, Any]]) -> None:
        course_id = _clean(getattr(payload, "course_id", ""))
        if not course_id or self.course_storage_manager is None:
            return

        material_id = _clean(artifact.get("artifact_id"))
        if not material_id:
            return

        self.course_storage_manager.save_generated_material(
            course_id=course_id,
            material_type="game",
            material_id=material_id,
            scope_type=_clean(getattr(payload, "scope_type", "")) or SCOPE_TYPE_COURSE,
            scope_id=_clean(getattr(payload, "scope_id", "")) or None,
            material_data={
                "title": _clean(artifact.get("title")) or "小游戏.html",
                "material_type": "game",
                "content": artifact.get("content"),
                "generation_state": dict(artifact.get("generation_state") or {}),
                "selected_doc_ids": selected_doc_ids,
                "documents_used": [_clean(item.get("title")) for item in documents if _clean(item.get("title"))],
            },
        )


def build_default_knowledge_base_direct_game_service_v2() -> KnowledgeBaseDirectGameServiceV2:
    return KnowledgeBaseDirectGameServiceV2(
        content_provider=KnowledgeBaseDocumentContentProvider(),
        llm=get_fallback_llm(),
        course_storage_manager=default_course_storage_manager,
    )
