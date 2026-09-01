"""Preview or execute all eight non-PPT teacher resource generation checks."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import uuid4

try:
    from scripts.teacher_smoke_common import poll_job, request_json, source_fields
except ModuleNotFoundError:  # Direct execution: python src/scripts/...
    from teacher_smoke_common import poll_job, request_json, source_fields


@dataclass(frozen=True)
class ResourceRequest:
    path: str
    payload: dict[str, Any]
    material_type: str


def build_resource_requests(
    *, course_id: str, topic: str, source_mode: str, selected_doc_ids: list[str]
) -> dict[str, ResourceRequest]:
    source = source_fields(source_mode, selected_doc_ids)

    def key(name: str) -> str:
        return f"teacher-smoke-{name}-{uuid4().hex}"

    common = {"course_id": course_id, **source}
    return {
        "report": ResourceRequest(
            "/api/chat/v2/report/direct",
            {**common, "question": f"生成一份关于{topic}的教学报告", "report_config": {"include_visuals": True}, "idempotency_key": key("report")},
            "report",
        ),
        "lesson_plan": ResourceRequest(
            "/api/chat/v2/lesson-plan/direct",
            {**common, "topic": topic, "audience": "本科生", "duration_minutes": 45, "objectives": [f"理解{topic}的基本原理"], "include_visuals": True, "idempotency_key": key("lesson-plan")},
            "lesson_plan",
        ),
        "quiz": ResourceRequest(
            "/api/chat/v2/quiz/direct",
            {**common, "quiz_config": {"topic": topic, "difficulty": "medium", "question_count": 5, "question_types": ["choice", "short"], "include_answers": True, "include_explanations": True}, "idempotency_key": key("quiz")},
            "quiz",
        ),
        "game": ResourceRequest(
            "/api/chat/v2/game/direct",
            {**common, "game_type": "drag_match", "topic": topic, "card_count": 8, "difficulty": "medium", "duration_minutes": 5, "idempotency_key": key("game")},
            "game",
        ),
        "flashcard": ResourceRequest(
            "/api/chat/v2/flashcard/direct",
            {**common, "flashcard_config": {"title": topic, "count": 10, "difficulty": "medium", "show_sources": True}, "idempotency_key": key("flashcard")},
            "flashcard",
        ),
        "graph": ResourceRequest(
            "/api/chat/v2/graph/direct",
            {**common, "title": topic, "description": f"梳理{topic}的概念、结构与实现步骤", "max_depth": 3, "idempotency_key": key("graph")},
            "graph",
        ),
        "blog": ResourceRequest(
            "/api/chat/v2/blog/direct",
            {**common, "topic": topic, "audience": "学习者", "tone": "popular", "length": "medium", "include_visuals": True, "idempotency_key": key("blog")},
            "blog",
        ),
        "classroom": ResourceRequest(
            f"/api/courses/{course_id}/classrooms/generate",
            {**source, "topic": topic, "requirement": f"生成一份讲解{topic}的互动课堂课件", "audience": "本科生", "objectives": [f"掌握{topic}的核心操作"], "scene_count": 6, "duration_minutes": 25, "teaching_style": "guided", "enable_web_search": False, "enable_tts": False, "include_visuals": True, "idempotency_key": key("classroom")},
            "classroom",
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("EDU_AI_SMOKE_BASE_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--course-id", default=os.getenv("EDU_AI_SMOKE_COURSE_ID"))
    parser.add_argument("--topic", default="链表的实现")
    parser.add_argument("--source-mode", choices=["none", "course_auto", "selected_documents"], default="course_auto")
    parser.add_argument("--selected-doc-id", action="append", default=[])
    parser.add_argument("--resources", nargs="*", choices=["report", "lesson_plan", "quiz", "game", "flashcard", "graph", "blog", "classroom"])
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--execute", action="store_true", help="Create resources and poll them to completion")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.course_id:
        raise SystemExit("--course-id (or EDU_AI_SMOKE_COURSE_ID) is required")
    matrix = build_resource_requests(
        course_id=args.course_id,
        topic=args.topic,
        source_mode=args.source_mode,
        selected_doc_ids=args.selected_doc_id,
    )
    selected = args.resources or list(matrix)
    if not args.execute:
        print(json.dumps({"mode": "preview", "resources": selected, "source_mode": args.source_mode}, ensure_ascii=False, indent=2))
        return 0

    token = os.getenv("EDU_AI_SMOKE_TOKEN", "").strip()
    if not token:
        raise SystemExit("EDU_AI_SMOKE_TOKEN is required with --execute")
    call = partial(request_json, args.base_url, token=token)
    preflight = call(
        "/api/chat/v2/generation/preflight",
        method="POST",
        payload={
            "course_id": args.course_id,
            "resource_type": selected[0],
            "source_mode": args.source_mode,
            "selected_doc_ids": args.selected_doc_id,
        },
    )
    if not preflight.get("valid"):
        raise AssertionError("generation source preflight failed")

    for name in selected:
        spec = matrix[name]
        submitted = call(spec.path, method="POST", payload=spec.payload)
        job_id = str(submitted.get("task_id") or submitted.get("edu_job_id") or "")
        if not job_id:
            raise AssertionError(f"{name}: submission returned no job id")
        job = poll_job(
            job_id,
            request_json=lambda method, path: call(path, method=method),
            timeout_seconds=args.timeout,
        )
        if job.get("status") != "succeeded" or not job.get("result_ref"):
            raise AssertionError(
                f"{name}: terminal status={job.get('status')}, error={job.get('error_message')}"
            )
        material_id = str((job.get("result_ref") or {}).get("material_id") or "")
        materials = call(
            f"/api/courses/{args.course_id}/materials?material_type={spec.material_type}&space=mine"
        )
        if material_id and not any(str(item.get("id") or item.get("material_id") or "") == material_id for item in materials):
            raise AssertionError(f"{name}: generated material {material_id} was not found in storage")
        print(f"PASS {name}: job={job_id}, material={material_id or 'result-ref-present'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
