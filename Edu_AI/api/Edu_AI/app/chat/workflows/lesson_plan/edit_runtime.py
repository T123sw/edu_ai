from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.chat.orchestrator.lesson_plan_edit_intent_parser import parse_lesson_plan_edit_intent
from app.chat.orchestrator.lesson_plan_structure_parser import parse_lesson_plan_nodes


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


def _extract_content(source_artifact: dict[str, Any], artifact_type: str) -> dict[str, Any]:
    if artifact_type == "lesson_plan":
        return dict(source_artifact.get("plan") or source_artifact.get("content") or {})
    return dict(source_artifact.get("outline") or source_artifact.get("content") or {})


class LessonPlanEditRuntime:
    def __init__(self, *, llm=None):
        self.llm = llm

    @staticmethod
    def _awaiting_input_result(message: str, edit_request: dict[str, Any]) -> dict:
        return {
            "message": {"role": "assistant", "content": message},
            "conversation": {},
            "action": {"name": "lesson_plan.edit"},
            "workflow": {"type": "lesson_plan", "status": "awaiting_input"},
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
    def _build_version_metadata(source_artifact: dict[str, Any]) -> dict:
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

    @staticmethod
    def _parse_json_response(text: str, *, fallback: Any) -> Any:
        try:
            return json.loads(str(text or "").strip())
        except Exception:
            return fallback

    def _rewrite_lesson_plan_content(self, *, source_content: dict[str, Any], edit_request: dict[str, Any]) -> dict[str, Any]:
        next_content = deepcopy(dict(source_content or {}))
        target_node_id = str(edit_request.get("target_node_id") or "").strip()

        if target_node_id.endswith(":objectives"):
            prompt = (
                f"请根据这个要求改写教案里的教学目标：{edit_request.get('instruction') or ''}\n"
                f"原目标：{json.dumps(next_content.get('objectives') or [], ensure_ascii=False)}\n"
                "只输出 JSON 数组。"
            )
            next_content["objectives"] = self._parse_json_response(
                self._invoke_model(prompt),
                fallback=next_content.get("objectives") or [],
            )
            return next_content

        if ":process:" in target_node_id:
            step_index = int(target_node_id.rsplit(":", 1)[-1]) - 1
            process = list(next_content.get("process") or [])
            if 0 <= step_index < len(process):
                prompt = (
                    f"请根据这个要求改写教案里的教学环节：{edit_request.get('instruction') or ''}\n"
                    f"原环节：{json.dumps(process[step_index], ensure_ascii=False)}\n"
                    "只输出 JSON 对象。"
                )
                process[step_index] = self._parse_json_response(
                    self._invoke_model(prompt),
                    fallback=process[step_index],
                )
                next_content["process"] = process
            return next_content

        if ":lesson_flow:" in target_node_id:
            step_index = int(target_node_id.rsplit(":", 1)[-1]) - 1
            lesson_flow = list(next_content.get("lesson_flow") or [])
            if 0 <= step_index < len(lesson_flow):
                prompt = (
                    f"请根据这个要求改写教案大纲里的教学环节：{edit_request.get('instruction') or ''}\n"
                    f"原环节：{json.dumps(lesson_flow[step_index], ensure_ascii=False)}\n"
                    "只输出 JSON 对象。"
                )
                lesson_flow[step_index] = self._parse_json_response(
                    self._invoke_model(prompt),
                    fallback=lesson_flow[step_index],
                )
                next_content["lesson_flow"] = lesson_flow
            return next_content

        return next_content

    def run(self, *, question: str, artifact_reference: dict, source_artifact: dict) -> dict:
        artifact_reference = _normalize_reference(artifact_reference)
        source_artifact = dict(source_artifact or {})
        artifact_type = str(source_artifact.get("artifact_type") or artifact_reference.get("artifact_type") or "").strip()
        source_artifact["artifact_type"] = artifact_type
        source_content = _extract_content(source_artifact, artifact_type)

        nodes = parse_lesson_plan_nodes(
            artifact_id=str(source_artifact.get("artifact_id") or artifact_reference.get("artifact_id") or ""),
            artifact_type=artifact_type,
            content=source_content,
        )
        edit_request = parse_lesson_plan_edit_intent(
            artifact_reference=artifact_reference,
            question=question,
            structure_nodes=nodes,
        )

        if edit_request.get("intent_type") == "ask_about_artifact":
            return self._awaiting_input_result(
                "当前引用的是教案内容。如需编辑，请明确字段、环节名或引用原文。",
                edit_request,
            )
        if edit_request.get("target_confidence") == "candidate":
            hint = " / ".join(edit_request.get("candidate_labels") or [])
            return self._awaiting_input_result(
                f"我还没有开始修改。你要改的是：{hint}？确认后我再修改。",
                edit_request,
            )
        if edit_request.get("target_confidence") == "unclear":
            return self._awaiting_input_result(
                "请告诉我你想修改哪一部分，可以直接说字段名、环节名、引用一句原文，或说第几个环节。",
                edit_request,
            )

        next_content = self._rewrite_lesson_plan_content(
            source_content=source_content,
            edit_request=edit_request,
        )
        version = self._build_version_metadata(source_artifact)
        artifact_id = f"{source_artifact.get('artifact_id')}-{version['version_id']}-{uuid4().hex[:6]}"
        return {
            "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
            "conversation": {},
            "action": {"name": "lesson_plan.edit"},
            "workflow": {"type": "lesson_plan", "status": "completed"},
            "artifacts": [
                {
                    "artifact_id": artifact_id,
                    "artifact_type": artifact_type,
                    "title": str(source_artifact.get("title") or "教案").strip(),
                    "content": next_content,
                    "version": version,
                }
            ],
            "sources": [],
            "trace": {"path": "workflow", "artifact_edit": edit_request},
        }

    def run_from_request(self, *, request, snapshot, course_storage_manager):
        artifact_reference = _normalize_reference(getattr(request, "artifact_reference", None))
        if not artifact_reference:
            raise ValueError("artifact_reference is required")

        artifact_id = str(artifact_reference.get("artifact_id") or "").strip()
        artifact_type = str(artifact_reference.get("artifact_type") or "").strip()
        source_artifact = None

        course_id = str(getattr(request, "course_id", "") or "").strip()
        if course_storage_manager is not None and course_id and artifact_id:
            material = course_storage_manager.get_generated_material(course_id, "lesson_plan", artifact_id)
            if material:
                source_artifact = dict(material)
                source_artifact["artifact_id"] = artifact_id
                source_artifact["artifact_type"] = artifact_type
                source_artifact.setdefault("title", artifact_reference.get("title"))
                source_artifact["content"] = _extract_content(source_artifact, artifact_type)

        if source_artifact is None and snapshot is not None:
            workflow_state = getattr(snapshot, "workflow_state", None)
            artifacts = list(getattr(workflow_state, "artifacts", []) or []) if workflow_state is not None else []
            source_artifact = next(
                (
                    dict(artifact)
                    for artifact in artifacts
                    if str(artifact.get("artifact_id") or "").strip() == artifact_id
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
