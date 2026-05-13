from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import re

from app.chat.orchestrator.report_edit_intent_parser import parse_report_edit_intent
from app.chat.orchestrator.report_structure_parser import parse_report_nodes


def _normalize_reference(value) -> dict:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(exclude_none=True))
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            key: raw
            for key, raw in dict(vars(value)).items()
            if not key.startswith("_") and raw is not None
        }
    return {}


def _extract_main_title(content: str) -> str:
    for line in str(content or "").splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return str(match.group(1) or "").strip()
    return "报告"


def _normalize_material_source(material_type: str, material: dict) -> dict:
    normalized = dict(material or {})
    if material_type == "report":
        normalized["content"] = normalized.get("report") or normalized.get("content") or ""
    elif material_type == "report_outline":
        normalized["content"] = normalized.get("outline") or normalized.get("content") or []
    return normalized


class ReportEditRuntime:
    def __init__(self, *, llm=None):
        self.llm = llm

    @staticmethod
    def _awaiting_input_result(*, message: str, edit_request: dict) -> dict:
        return {
            "message": {"role": "assistant", "content": message},
            "conversation": {},
            "action": {"name": "report.edit"},
            "workflow": {"type": "report", "status": "awaiting_input"},
            "artifacts": [],
            "sources": [],
            "trace": {"path": "workflow", "artifact_edit": edit_request},
        }

    def _invoke_model(self, prompt: str) -> str:
        if self.llm is None:
            return prompt
        response = self.llm.invoke(prompt)
        content = getattr(response, "content", response)
        return str(content or "").strip()

    @staticmethod
    def _build_version_metadata(source_artifact: dict) -> dict:
        source_version = dict(source_artifact.get("version") or {})
        source_artifact_id = str(source_artifact.get("artifact_id") or "").strip()
        root_artifact_id = str(source_version.get("root_artifact_id") or source_artifact_id)
        version_number = int(source_version.get("version_number") or 1) + 1
        return {
            "root_artifact_id": root_artifact_id,
            "parent_artifact_id": source_artifact_id,
            "version_id": f"v{version_number}",
            "version_number": version_number,
            "derived_from_action": "artifact_edit",
            "derived_from_reference": source_artifact_id,
        }

    def _rewrite_report_markdown(self, *, source_artifact: dict, edit_request: dict) -> str:
        content = str(source_artifact.get("content") or "")
        title = _extract_main_title(content)
        nodes = parse_report_nodes(
            artifact_id=str(source_artifact.get("artifact_id") or ""),
            version_id=str((source_artifact.get("version") or {}).get("version_id") or ""),
            artifact_type="report",
            content=content,
        )
        rewritten = []
        for node in nodes:
            body = str(node.get("content") or "")
            if node.get("node_id") == edit_request.get("target_node_id"):
                prompt = (
                    f"你正在修改报告《{title}》中的章节《{node.get('title') or ''}》。\n"
                    f"用户要求：{edit_request.get('instruction') or ''}\n"
                    f"原内容：\n{body}\n\n"
                    "请只输出修改后的章节正文，不要额外解释。"
                )
                body = self._invoke_model(prompt).strip() or body
            rewritten.append(f"## {node.get('title')}\n{body}".strip())
        return f"# {title}\n\n" + "\n\n".join(rewritten).strip()

    def _rewrite_outline(self, *, source_artifact: dict, edit_request: dict) -> list[dict]:
        outline = deepcopy(list(source_artifact.get("content") or []))
        target_node_id = str(edit_request.get("target_node_id") or "").strip()
        if not target_node_id:
            return outline
        for index, chapter in enumerate(outline, start=1):
            current_node_id = f"{source_artifact.get('artifact_id')}:{index}"
            if current_node_id != target_node_id:
                continue
            next_chapter = dict(chapter)
            existing_goal = str(next_chapter.get("chapter_goal") or "").strip()
            prompt = (
                f"你正在修改报告大纲章节《{next_chapter.get('chapter_title') or ''}》。\n"
                f"用户要求：{edit_request.get('instruction') or ''}\n"
                f"现有章节目标：{existing_goal}\n"
                "请输出修改后的章节目标，一句话即可。"
            )
            rewritten_goal = self._invoke_model(prompt).strip()
            next_chapter["chapter_goal"] = rewritten_goal or existing_goal or str(edit_request.get("instruction") or "")
            outline[index - 1] = next_chapter
            break
        return outline

    def _build_generation_state(self, *, source_artifact: dict, version: dict, mode: str, question: str, source_outline_id: str | None = None) -> dict:
        title = str(source_artifact.get("title") or "").replace(".md", "").strip()
        return {
            "state_id": f"state-{uuid4().hex[:12]}",
            "artifact_id": "",
            "version_id": version.get("version_id"),
            "topic": title or "报告",
            "focus": question,
            "length_requirement": "",
            "style": "",
            "audience": "",
            "references": [],
            "source_outline_artifact_id": source_outline_id or "",
            "source_report_artifact_id": str(source_artifact.get("artifact_id") or "") if str(source_artifact.get("artifact_type") or "") == "report" else "",
            "source_version_id": str((source_artifact.get("version") or {}).get("version_id") or ""),
            "generated_at": "",
            "generation_mode": mode,
            "model_name": getattr(self.llm, "model_name", "") if self.llm is not None else "",
            "trace_fingerprint": f"artifact-edit:{mode}",
        }

    def run(self, *, question: str, artifact_reference: dict, source_artifact: dict) -> dict:
        artifact_reference = _normalize_reference(artifact_reference)
        source_artifact = dict(source_artifact or {})
        source_artifact_type = str(source_artifact.get("artifact_type") or artifact_reference.get("artifact_type") or "").strip()
        source_artifact["artifact_type"] = source_artifact_type
        nodes = parse_report_nodes(
            artifact_id=str(source_artifact.get("artifact_id") or artifact_reference.get("artifact_id") or ""),
            version_id=str((source_artifact.get("version") or {}).get("version_id") or artifact_reference.get("version_id") or ""),
            artifact_type=source_artifact_type,
            content=source_artifact.get("content"),
        )
        edit_request = parse_report_edit_intent(
            artifact_reference=artifact_reference,
            question=question,
            structure_nodes=nodes,
        )

        if edit_request.get("action_type") == "ask_about_artifact":
            artifact_label = "报告正文" if source_artifact_type == "report" else "报告大纲"
            return self._awaiting_input_result(
                message=f"当前已引用的是{artifact_label}。如果你是想继续提问，请先移除引用；如果你是想编辑，请明确要修改的结构节点。",
                edit_request=edit_request,
            )

        if edit_request.get("needs_disambiguation"):
            candidate_labels = [
                str(label).strip()
                for label in list(edit_request.get("candidate_labels") or [])
                if str(label).strip()
            ]
            hint = "、".join(candidate_labels)
            return self._awaiting_input_result(
                message=f"请明确要修改的结构节点。可选节点：{hint}" if hint else "请明确要修改的结构节点。",
                edit_request=edit_request,
            )

        version = self._build_version_metadata(source_artifact)

        if source_artifact_type == "report_outline" and edit_request.get("action_type") == "regenerate":
            outline_content = list(source_artifact.get("content") or [])
            outline_text = "\n".join(str(item.get("chapter_title") or "") for item in outline_content if isinstance(item, dict))
            prompt = (
                f"请基于以下报告大纲生成一份完整正式报告 Markdown。\n用户要求：{question}\n"
                f"大纲：\n{outline_text}\n"
            )
            report_content = self._invoke_model(prompt).strip()
            report_artifact_id = f"{source_artifact.get('artifact_id')}-{version['version_id']}-{uuid4().hex[:6]}"
            generation_state = self._build_generation_state(
                source_artifact=source_artifact,
                version=version,
                mode="regenerate_from_outline",
                question=question,
                source_outline_id=str(source_artifact.get("artifact_id") or ""),
            )
            generation_state["artifact_id"] = report_artifact_id
            return {
                "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                "conversation": {},
                "action": {"name": "report.edit"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [
                    {
                        "artifact_id": report_artifact_id,
                        "artifact_type": "report",
                        "title": str(source_artifact.get("title") or "报告").replace("-大纲", "").strip(),
                        "content": report_content,
                        "version": version,
                        "generation_state": generation_state,
                    }
                ],
                "sources": [],
                "trace": {"path": "workflow", "artifact_edit": edit_request},
            }

        if source_artifact_type == "report_outline":
            next_outline = self._rewrite_outline(source_artifact=source_artifact, edit_request=edit_request)
            outline_artifact_id = f"{source_artifact.get('artifact_id')}-{version['version_id']}-{uuid4().hex[:6]}"
            return {
                "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                "conversation": {},
                "action": {"name": "report.edit"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [
                    {
                        "artifact_id": outline_artifact_id,
                        "artifact_type": "report_outline",
                        "title": str(source_artifact.get("title") or "报告大纲").strip(),
                        "content": next_outline,
                        "version": version,
                    }
                ],
                "sources": [],
                "trace": {"path": "workflow", "artifact_edit": edit_request},
            }

        rewritten_content = self._rewrite_report_markdown(source_artifact=source_artifact, edit_request=edit_request)
        report_artifact_id = f"{source_artifact.get('artifact_id')}-{version['version_id']}-{uuid4().hex[:6]}"
        generation_state = self._build_generation_state(
            source_artifact=source_artifact,
            version=version,
            mode="revise_report",
            question=question,
        )
        generation_state["artifact_id"] = report_artifact_id
        return {
            "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
            "conversation": {},
            "action": {"name": "report.edit"},
            "workflow": {"type": "report", "status": "completed"},
            "artifacts": [
                {
                    "artifact_id": report_artifact_id,
                    "artifact_type": "report",
                    "title": str(source_artifact.get("title") or "报告").strip(),
                    "content": rewritten_content,
                    "version": version,
                    "generation_state": generation_state,
                }
            ],
            "sources": [],
            "trace": {"path": "workflow", "artifact_edit": edit_request},
        }

    def run_from_request(self, *, request, snapshot, course_storage_manager):
        artifact_reference = _normalize_reference(getattr(request, "artifact_reference", None))
        if not artifact_reference:
            raise ValueError("artifact_reference is required")
        source_artifact = None
        course_id = str(getattr(request, "course_id", "") or "").strip()
        artifact_type = str(artifact_reference.get("artifact_type") or "").strip()
        if course_storage_manager is not None and course_id:
            material = course_storage_manager.get_generated_material(course_id, "report", artifact_reference.get("artifact_id"))
            if material:
                source_artifact = _normalize_material_source(artifact_type, material)
                source_artifact["artifact_id"] = artifact_reference.get("artifact_id")
                source_artifact["artifact_type"] = artifact_type
                source_artifact.setdefault("title", artifact_reference.get("title"))
        if source_artifact is None and snapshot is not None:
            workflow_state = getattr(snapshot, "workflow_state", None)
            artifacts = list(getattr(workflow_state, "artifacts", []) or []) if workflow_state is not None else []
            source_artifact = next(
                (
                    dict(artifact)
                    for artifact in artifacts
                    if str(artifact.get("artifact_id") or "").strip() == str(artifact_reference.get("artifact_id") or "").strip()
                ),
                None,
            )
        if source_artifact is None:
            raise ValueError("referenced artifact not found")
        return self.run(
            question=str(getattr(request, "question", "") or ""),
            artifact_reference=artifact_reference,
            source_artifact=source_artifact,
        )
