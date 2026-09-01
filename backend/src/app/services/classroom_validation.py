"""SPEC-02 §6 不变量校验——生成结果落库前必须全部通过，否则拒绝落库。

只抽取落库关心的字段做结构校验，不重新定义/解析整个 DSL（同 SPEC-07 §2
"不重定义 DSL 字段语义"的原则）：入参是 sidecar 原样返回的 plain dict
（`Stage`/`Scene[]`，字段名已核对 OpenMAIC `packages/@openmaic/dsl/src/
{stage,slides,action}.ts`）。

覆盖不变量 1-5（SPEC-02 §6）；不变量 6"编辑不换 id"是编辑时的约定，生成
时无法校验，不在此列。
"""

from __future__ import annotations

from typing import Any

# action.ts:251/257 —— 这两类动作不推进时钟、只在 slide 场景内叠加聚焦效果。
FIRE_AND_FORGET_ELEMENT_ACTIONS = {"spotlight", "laser"}

# 跟 OpenMaicClient._default_base_url() 的默认值保持一致——这里不 import
# client 模块（validation 不该依赖 integrations 层），只是复用同一个默认值。
_DEFAULT_SIDECAR_BASE_URL = "http://localhost:3000"


def validate_stage(
    stage: dict[str, Any],
    scenes: list[dict[str, Any]],
    *,
    sidecar_base_url: str = _DEFAULT_SIDECAR_BASE_URL,
) -> list[str]:
    """返回违规描述列表；空列表 = 通过。不抛异常，由调用方决定落库策略。

    `sidecar_base_url` 用于不变量 5 的判定：只有 audioUrl 精确落在**这个
    sidecar 的地址**下才算"忘记迁移"，不能拿"是不是 localhost"来判断——
    edu_ai 自己的后端本地开发时也跑在 localhost（只是端口不同），拿
    localhost 一刀切会把 edu_ai 自己迁移改写后的地址也误判为违规。
    """
    violations: list[str] = []

    if not stage.get("id"):
        violations.append("Stage.id 缺失")

    seen_scene_ids: set[str] = set()
    for scene_index, scene in enumerate(scenes):
        scene_id = scene.get("id")
        if not scene_id:
            violations.append(f"scene[{scene_index}].id 缺失")
        elif scene_id in seen_scene_ids:
            violations.append(f"Scene.id 重复: {scene_id}")
        else:
            seen_scene_ids.add(scene_id)

        label = f"Scene[{scene_id or scene_index}]"
        violations.extend(_validate_scene(label, scene, sidecar_base_url))

    return violations


def _validate_scene(label: str, scene: dict[str, Any], sidecar_base_url: str) -> list[str]:
    violations: list[str] = []
    content = scene.get("content") or {}

    element_ids: set[str] = set()
    video_element_ids: set[str] = set()

    if content.get("type") == "slide":
        canvas = content.get("canvas") or {}
        # 不变量 2：viewportRatio 必须存在（渲染/导出/视频视口对齐依赖它）。
        if canvas.get("viewportRatio") is None:
            violations.append(f"{label}.content.canvas.viewportRatio 缺失")

        seen_element_ids: set[str] = set()
        for el_index, element in enumerate(canvas.get("elements") or []):
            el_id = element.get("id")
            if not el_id:
                violations.append(f"{label}.canvas.elements[{el_index}].id 缺失")
                continue
            # 不变量 1：element.id 在 slide 内唯一。
            if el_id in seen_element_ids:
                violations.append(f"{label} element.id 重复: {el_id}")
            seen_element_ids.add(el_id)
            element_ids.add(el_id)
            if element.get("type") == "video":
                video_element_ids.add(el_id)

    seen_action_ids: set[str] = set()
    for act_index, action in enumerate(scene.get("actions") or []):
        action_id = action.get("id")
        if not action_id:
            violations.append(f"{label}.actions[{act_index}].id 缺失")
        elif action_id in seen_action_ids:
            violations.append(f"{label} action.id 重复: {action_id}")
        else:
            seen_action_ids.add(action_id)

        action_type = action.get("type")
        if action_type in FIRE_AND_FORGET_ELEMENT_ACTIONS:
            # 不变量 3：spotlight/laser.elementId 必须指向同场景内存在的 element。
            violations.extend(
                _validate_element_reference(label, action_type, action.get("elementId"), element_ids)
            )
        elif action_type == "play_video":
            # 不变量 4：play_video.elementId 必须指向 video 类型的 element。
            element_id = action.get("elementId")
            if not element_id:
                violations.append(f"{label} play_video action 缺 elementId")
            elif element_id not in video_element_ids:
                violations.append(
                    f"{label} play_video.elementId={element_id!r} 不指向 video 类型 element"
                )
        elif action_type == "speech":
            # 不变量 5：已配音的 audioUrl 必须指向 edu_ai 可达存储，不能是 sidecar 临时地址。
            audio_url = action.get("audioUrl")
            if audio_url and _looks_like_sidecar_local_url(audio_url, sidecar_base_url):
                violations.append(
                    f"{label} speech.audioUrl 指向 sidecar 本地地址而非 edu_ai 存储: {audio_url}"
                )

    return violations


def _validate_element_reference(
    label: str, action_type: str, element_id: str | None, element_ids: set[str]
) -> list[str]:
    if not element_id:
        return [f"{label} {action_type} action 缺 elementId"]
    if element_id not in element_ids:
        return [f"{label} {action_type}.elementId={element_id!r} 在本场景 slide.elements 中不存在"]
    return []


def _looks_like_sidecar_local_url(url: str, sidecar_base_url: str) -> bool:
    return url.strip().lower().startswith(sidecar_base_url.strip().lower().rstrip("/"))
