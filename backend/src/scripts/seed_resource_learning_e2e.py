"""Seed an approved, deterministic AI classroom for resource-learning E2E tests."""

from __future__ import annotations

import argparse
import json
import os

from sqlalchemy import create_engine

from app.persistence.postgres_material_repository import PostgresMaterialRepository
from app.resource_learning.repository import ResourceLearningRepository
from app.standard_resources.models import StandardKind, stable_material_id
from app.standard_resources.repository import StandardResourceRepository
from app.standard_resources.review_service import StandardResourceReviewService
from core.course_storage import CourseStorageManager


COURSE_ID = "computational-thinking"
LEAF_ID = "sequence-selection-loop"
RESOURCE_ID = stable_material_id(LEAF_ID, StandardKind.CLASSROOM)
RESOURCE_VERSION = 3


def _canvas(scene_id: str, title: str, color: str) -> dict:
    return {
        "id": f"{scene_id}-canvas",
        "viewportSize": 1280,
        "viewportRatio": 0.5625,
        "theme": {
            "backgroundColor": "#f8fafc",
            "themeColors": [color],
            "fontColor": "#0f172a",
            "fontName": "Microsoft YaHei",
        },
        "background": {"type": "solid", "color": "#f8fafc"},
        "elements": [
            {
                "id": f"{scene_id}-title",
                "type": "text",
                "left": 120,
                "top": 220,
                "width": 1040,
                "height": 180,
                "rotate": 0,
                "content": (
                    '<p style="font-family:Microsoft YaHei;font-size:64px;'
                    f'text-align:center;color:{color}">{title}</p>'
                ),
                "defaultFontName": "Microsoft YaHei",
                "defaultColor": color,
            }
        ],
    }


def classroom_payload(*, version: int = RESOURCE_VERSION) -> dict:
    slides = [
        ("explain-1", "顺序结构", "程序按照既定顺序逐步执行。", "#2563eb"),
        ("explain-2", "分支结构", "条件判断决定程序选择哪条路径。", "#7c3aed"),
        ("explain-3", "循环结构", "循环让重复步骤自动执行多次。", "#0f766e"),
    ]
    scenes = [
        {
            "id": scene_id,
            "type": "slide",
            "title": title,
            "order": index,
            "content": {
                "type": "slide",
                "canvas": _canvas(scene_id, title, color),
            },
            "actions": [
                {
                    "id": f"{scene_id}-speech",
                    "type": "speech",
                    "text": narration,
                }
            ],
        }
        for index, (scene_id, title, narration, color) in enumerate(slides)
    ]
    scenes.extend(
        [
            {
                "id": "exercise-1",
                "type": "quiz",
                "title": "课堂练习",
                "order": 3,
                "content": {
                    "type": "quiz",
                    "questions": [
                        {
                            "id": "question-1",
                            "type": "single",
                            "question": "哪种结构适合按条件选择路径？",
                            "required": True,
                            "options": [
                                {"value": "A", "label": "顺序结构"},
                                {"value": "B", "label": "分支结构"},
                            ],
                            "answer": ["B"],
                            "analysis": "分支结构根据条件选择执行路径。",
                        },
                        {
                            "id": "question-2",
                            "type": "single",
                            "question": "哪种结构适合重复执行？",
                            "required": True,
                            "options": [
                                {"value": "A", "label": "循环结构"},
                                {"value": "B", "label": "顺序结构"},
                            ],
                            "answer": ["A"],
                            "analysis": "循环结构用于重复执行。",
                        },
                        {
                            "id": "question-3",
                            "type": "short_answer",
                            "question": "写出一个生活中的循环示例。",
                            "required": True,
                            "answer": ["重复"],
                            "commentPrompt": "只要提交非空答案就计入学习完成。",
                        },
                    ],
                },
                "actions": [],
            },
            {
                "id": "demo-1",
                "type": "interactive",
                "title": "循环演示",
                "order": 4,
                "content": {
                    "type": "interactive",
                    "html": """<!doctype html><html><body>
<button id="demo-action" onclick="window.parent.postMessage({__eduClassroomInteractive:true,kind:'user-interaction',actionId:'demo-click'},'*')">执行一次演示</button>
</body></html>""",
                },
                "actions": [],
            },
        ]
    )
    return {
        "course_id": COURSE_ID,
        "material_type": "classroom",
        "material_id": RESOURCE_ID,
        "title": "顺序、分支与循环结构 AI 课堂",
        "status": "ready",
        "visibility": "course",
        "origin_type": "standard",
        "standard_kind": "classroom",
        "generation_batch_id": "resource-learning-e2e",
        "current_review_status": "pending",
        "review_status": "pending",
        "version": version,
        "voice_status": "disabled",
        "stage": {"id": "resource-learning-e2e", "name": "程序控制结构"},
        "scenes_count": len(scenes),
        "scenes": scenes,
    }


def seed(database_url: str, *, version: int = RESOURCE_VERSION) -> dict:
    manager = CourseStorageManager()
    if manager.get_course_info(COURSE_ID) is None:
        raise RuntimeError(f"E2E course {COURSE_ID!r} is missing")

    engine = create_engine(database_url, pool_pre_ping=True)
    materials = PostgresMaterialRepository(engine)
    learning = ResourceLearningRepository(engine)
    review = StandardResourceReviewService(
        repository=StandardResourceRepository(engine),
        material_repository=materials,
    )
    materials.upsert(classroom_payload(version=version))
    approved = review.review(
        course_id=COURSE_ID,
        material_id=RESOURCE_ID,
        reviewer_id="teacher",
        decision="approved",
    )
    manifest = learning.get_manifest(COURSE_ID, RESOURCE_ID, version)
    if manifest is None:
        raise RuntimeError("resource learning manifest was not frozen")
    result = {
        "course_id": COURSE_ID,
        "resource_id": RESOURCE_ID,
        "resource_version": version,
        "approved_version": approved["approved_version"],
        "explanation_total_ms": manifest.explanation_total_ms,
        "required_question_ids": list(manifest.required_question_ids),
    }
    engine.dispose()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, default=RESOURCE_VERSION)
    args = parser.parse_args()
    if args.version < RESOURCE_VERSION:
        raise RuntimeError(f"version must be at least {RESOURCE_VERSION}")
    database_url = str(os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    print(json.dumps(seed(database_url, version=args.version), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
