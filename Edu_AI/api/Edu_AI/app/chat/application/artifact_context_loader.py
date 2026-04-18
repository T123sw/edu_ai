from __future__ import annotations

from typing import Any


def _load_source_artifact(*, artifact_type: str, artifact_id: str, snapshot, course_storage_manager, course_id: str) -> dict[str, Any] | None:
    source_artifact: dict[str, Any] | None = None

    if (
        course_storage_manager is not None
        and hasattr(course_storage_manager, "get_generated_material")
        and course_id
        and artifact_id
    ):
        if artifact_type.startswith("ppt_"):
            material_type = "ppt"
        elif artifact_type.startswith("lesson_plan"):
            material_type = "lesson_plan"
        else:
            material_type = "report"
        material = course_storage_manager.get_generated_material(course_id, material_type, artifact_id)
        if material:
            source_artifact = dict(material)

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

    return source_artifact


def _load_ppt_outline(*, source_artifact: dict[str, Any], artifact_id: str, snapshot) -> dict[str, Any]:
    outline = source_artifact.get("outline")
    if isinstance(outline, dict):
        return outline

    workflow_state = getattr(snapshot, "workflow_state", None)
    artifacts = list(getattr(workflow_state, "artifacts", []) or []) if workflow_state is not None else []
    outline_artifact = next(
        (
            dict(artifact)
            for artifact in artifacts
            if str(artifact.get("artifact_type") or "").strip() == "ppt_outline"
            and (
                str(artifact.get("artifact_id") or "").strip() == f"{artifact_id}:outline"
            )
        ),
        None,
    )
    if outline_artifact is None:
        outline_artifact = next(
            (
                dict(artifact)
                for artifact in artifacts
                if str(artifact.get("artifact_type") or "").strip() == "ppt_outline"
            ),
            None,
        )
    return dict((outline_artifact or {}).get("content") or {})


def _build_report_context(*, artifact_type: str, source_artifact: dict[str, Any]) -> str:
    if artifact_type == "report":
        return str(source_artifact.get("report") or source_artifact.get("content") or "").strip()

    outline = list(source_artifact.get("outline") or source_artifact.get("content") or [])
    return "\n".join(
        f"{index}. {item.get('chapter_title') or ''}".strip()
        for index, item in enumerate(outline, start=1)
        if isinstance(item, dict)
    ).strip()


def _build_ppt_context(*, title: str, artifact_id: str, source_artifact: dict[str, Any], snapshot) -> str:
    content = dict(source_artifact.get("content") or {})
    outline = _load_ppt_outline(source_artifact=source_artifact, artifact_id=artifact_id, snapshot=snapshot)
    slide_lines = [
        f"\u7b2c {slide.get('slide_index')} \u9875\uff1a{slide.get('title')}"
        for slide in list(outline.get("slides") or [])
        if isinstance(slide, dict) and slide.get("slide_index")
    ]
    slide_count = content.get("slide_count") or len(slide_lines) or 0
    context_lines = [
        f"\u6807\u9898\uff1a{title}",
        f"\u9875\u6570\uff1a{slide_count}",
        *slide_lines,
    ]
    return "\n".join(line for line in context_lines if str(line or "").strip()).strip()


def _build_lesson_plan_context(*, artifact_type: str, source_artifact: dict[str, Any], title: str) -> str:
    if artifact_type == "lesson_plan":
        plan = dict(source_artifact.get("plan") or source_artifact.get("content") or {})
        process = list(plan.get("process") or [])
        context_lines = [f"\u6807\u9898\uff1a{plan.get('title') or title}"]
        context_lines.extend(
            f"\u76ee\u6807\uff1a{item}"
            for item in list(plan.get("objectives") or [])
            if str(item or "").strip()
        )
        context_lines.extend(
            f"\u73af\u8282 {index}\uff1a{step.get('step')} - {step.get('goal')}"
            for index, step in enumerate(process, start=1)
            if isinstance(step, dict) and (str(step.get("step") or "").strip() or str(step.get("goal") or "").strip())
        )
        return "\n".join(line for line in context_lines if str(line or "").strip()).strip()

    outline = dict(source_artifact.get("outline") or source_artifact.get("content") or {})
    basic_info = dict(outline.get("basic_info") or {})
    lesson_flow = list(outline.get("lesson_flow") or [])
    context_lines = [f"\u4e3b\u9898\uff1a{basic_info.get('topic') or title}"]
    if str(basic_info.get("duration") or "").strip():
        context_lines.append(f"\u65f6\u957f\uff1a{basic_info.get('duration')}")
    context_lines.extend(
        f"\u73af\u8282 {index}\uff1a{item.get('step')} - {item.get('goal')}"
        for index, item in enumerate(lesson_flow, start=1)
        if isinstance(item, dict) and (str(item.get("step") or "").strip() or str(item.get("goal") or "").strip())
    )
    return "\n".join(line for line in context_lines if str(line or "").strip()).strip()


def load_artifact_context(*, artifact_reference: dict[str, Any], snapshot, course_storage_manager, course_id: str) -> dict[str, str] | None:
    artifact_type = str(artifact_reference.get("artifact_type") or "").strip()
    artifact_id = str(artifact_reference.get("artifact_id") or "").strip()
    title = str(artifact_reference.get("title") or "").strip() or artifact_id

    source_artifact = _load_source_artifact(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        snapshot=snapshot,
        course_storage_manager=course_storage_manager,
        course_id=course_id,
    )
    if source_artifact is None:
        return None

    if artifact_type in {"report", "report_outline"}:
        context_text = _build_report_context(artifact_type=artifact_type, source_artifact=source_artifact)
    elif artifact_type == "ppt_deck":
        context_text = _build_ppt_context(
            title=title,
            artifact_id=artifact_id,
            source_artifact=source_artifact,
            snapshot=snapshot,
        )
    elif artifact_type in {"lesson_plan", "lesson_plan_outline"}:
        context_text = _build_lesson_plan_context(
            artifact_type=artifact_type,
            source_artifact=source_artifact,
            title=title,
        )
    else:
        return None

    if not context_text:
        return None

    return {
        "artifact_type": artifact_type,
        "title": title,
        "context_text": context_text,
    }
