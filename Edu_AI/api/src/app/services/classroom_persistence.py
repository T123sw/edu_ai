"""落库 generate_classroom 的产出（SPEC-02 §4/§6、SPEC-04 §6）。

流程：sidecar 返回 `GenerateClassroomResult{id,url,stage,scenes,
scenesCount,createdAt}` → 校验（SPEC-02 §6，见 classroom_validation.py）→
全部通过才落库，否则抛 `ClassroomValidationError` 让调用方判 edu_job=failed。

落库复用 `core.course_storage.CourseStorageManager` 已有的
generated_materials 机制（`material_type="classroom"`），Stage+Scene[] 整段
JSON 存一份，不拆独立的 `classroom_scenes` 表——本轮没有"按场景寻址/局部
重生成"的需求（那是 Phase 3 交互课堂的事），拆表只会徒增迁移成本（同
SPEC-02 §4 的"为什么整段 JSON 落库"）。同 `Stage.id` 幂等 upsert 天然成立：
`material_id=Stage.id`，`save_generated_material` 本身就是按
`(course_id, material_type, material_id)` upsert。
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.classroom_validation import validate_stage
from core.course_storage import CourseStorageManager


class ClassroomValidationError(Exception):
    """SPEC-02 §6 不变量校验失败。`violations` 是可读的中文违规列表。"""

    def __init__(self, violations: list[str]):
        super().__init__("; ".join(violations))
        self.violations = violations


class ClassroomPersistError(Exception):
    """校验通过但落盘失败（磁盘/权限等），非数据问题。"""


def persist_classroom_result(
    *,
    course_storage_manager: CourseStorageManager,
    course_id: str,
    owner: Optional[str],
    result: dict[str, Any],
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict[str, Any]:
    """校验 + 落库一份 generate_classroom 的产出，返回 edu_job.result_ref 用的引用。

    `result` 是 sidecar `GenerateClassroomResult` 的原样 dict。
    """
    stage = result.get("stage") or {}
    scenes = result.get("scenes") or []

    violations = validate_stage(stage, scenes)
    if violations:
        raise ClassroomValidationError(violations)

    classroom_id = stage.get("id") or result.get("id")
    if not classroom_id:
        raise ClassroomValidationError(["Stage.id 与 result.id 均缺失，无法落库"])

    material_data = {
        "title": stage.get("name") or "Untitled Classroom",
        "owner": owner,
        "stage": stage,
        "scenes": scenes,
        "scenes_count": result.get("scenesCount", len(scenes)),
        "sidecar_url": result.get("url"),
        "sidecar_created_at": result.get("createdAt"),
    }

    saved = course_storage_manager.save_generated_material(
        course_id,
        "classroom",
        classroom_id,
        material_data,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    if not saved:
        raise ClassroomPersistError(
            f"Failed to persist classroom {classroom_id} for course {course_id}"
        )

    return {
        "classroom_id": classroom_id,
        "course_id": course_id,
        "scenes_count": material_data["scenes_count"],
    }
