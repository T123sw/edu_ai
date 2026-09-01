from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from ..report_domain import REPORT_DEFAULTS, REPORT_SLOT_KEYS


def init_report_slots(raw: Optional[Dict[str, Any]]) -> Dict[str, str]:
    slots: Dict[str, str] = {k: "" for k in REPORT_SLOT_KEYS}
    slots["dynamic_constraints"] = "{}"
    if isinstance(raw, dict):
        for key in REPORT_SLOT_KEYS:
            value = raw.get(key)
            if value is None:
                continue
            if key == "dynamic_constraints":
                if isinstance(value, dict):
                    slots[key] = json.dumps(value, ensure_ascii=False)
                else:
                    slots[key] = str(value).strip() or "{}"
            else:
                slots[key] = str(value).strip()
    return slots


def merge_report_slots(old: Dict[str, str], new: Dict[str, str]) -> Dict[str, str]:
    merged = {k: str(old.get(k, "") or "").strip() for k in REPORT_SLOT_KEYS}
    for key in REPORT_SLOT_KEYS:
        nv = str(new.get(key, "") or "").strip()
        if nv:
            merged[key] = nv
    return merged


def render_report_known(slots: Dict[str, str]) -> str:
    parts = []
    ordered = ["core_topic", "focus_area", "dynamic_constraints", "length_requirement", "depth_level", "format_style"]
    labels = {
        "core_topic": "核心主题",
        "focus_area": "聚焦方向",
        "dynamic_constraints": "动态约束",
        "length_requirement": "篇幅要求",
        "depth_level": "深度层级",
        "format_style": "文风格式",
    }
    for key in ordered:
        value = str(slots.get(key, "") or "").strip()
        if value:
            parts.append(f"{labels.get(key, key)}：{value}")
    return "；".join(parts)


def log_agent_process(stage: str, plan: str, reflection: str, next_step: str) -> None:
    stage_cn = {
        "extractor": "提取阶段",
        "evaluator": "评估阶段",
        "ask": "追问阶段",
        "outline": "大纲阶段",
        "generate": "正文阶段",
    }.get(stage, stage)
    print(f"{stage_cn} 思考：{plan}")
    print(f"{stage_cn} 计划：{reflection}")
    print(f"{stage_cn} 行动：{next_step}")


def normalize_outline_ast(raw_outline: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_outline, list):
        return []
    normalized: List[Dict[str, Any]] = []
    chapter_idx = 0
    for item in raw_outline:
        if not isinstance(item, dict):
            continue
        chapter_idx += 1
        chapter_id = item.get("chapter_id")
        if isinstance(chapter_id, str) and chapter_id.isdigit():
            chapter_id = int(chapter_id)
        if not isinstance(chapter_id, int):
            chapter_id = chapter_idx
        chapter_title = str(item.get("chapter_title") or item.get("title") or "").strip() or f"第{chapter_id}章"
        chapter_goal = str(item.get("chapter_goal") or "").strip() or "本章围绕核心主题展开分析"
        raw_sections = item.get("sections") if isinstance(item.get("sections"), list) else []
        sections: List[Dict[str, Any]] = []
        sec_idx = 0
        for sec in raw_sections:
            if not isinstance(sec, dict):
                continue
            sec_idx += 1
            section_id = str(sec.get("section_id") or f"{chapter_id}.{sec_idx}").strip()
            title = str(sec.get("title") or "").strip()
            if not title:
                continue
            sections.append({"section_id": section_id, "title": title})
        if not sections:
            sections = [
                {"section_id": f"{chapter_id}.1", "title": "关键问题界定"},
                {"section_id": f"{chapter_id}.2", "title": "论证与证据展开"},
            ]
        normalized.append(
            {
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "chapter_goal": chapter_goal,
                "sections": sections,
            }
        )
    return normalized


def apply_outline_patch(current_outline: List[Dict[str, Any]], modifications: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not isinstance(modifications, list):
        return current_outline, []
    outline = list(current_outline)
    change_log: List[str] = []

    def chapter_index_by_id(target_id: str) -> int:
        for i, ch in enumerate(outline):
            if str(ch.get("chapter_id") or "").strip() == target_id:
                return i
        return -1

    for op in modifications:
        if not isinstance(op, dict):
            continue
        action = str(op.get("action") or "").strip()
        target_id = str(op.get("target_id") or "").strip()
        new_content = op.get("new_content") if isinstance(op.get("new_content"), dict) else {}

        if action == "update_chapter" and target_id:
            idx = chapter_index_by_id(target_id)
            if idx >= 0:
                outline[idx] = {**outline[idx], **new_content}
                change_log.append(f"更新第{target_id}章")
        elif action == "delete_chapter" and target_id:
            idx = chapter_index_by_id(target_id)
            if idx >= 0:
                outline.pop(idx)
                change_log.append(f"删除第{target_id}章")
        elif action == "add_chapter" and new_content:
            outline.append(new_content)
            change_log.append("新增章节")
    return normalize_outline_ast(outline), change_log


def ast_outline_stats(outline: Any) -> Tuple[int, int]:
    if not isinstance(outline, list):
        return 0, 0
    chapter_count = 0
    section_count = 0
    for ch in outline:
        if not isinstance(ch, dict):
            continue
        chapter_count += 1
        sections = ch.get("sections") if isinstance(ch.get("sections"), list) else []
        section_count += len([s for s in sections if isinstance(s, dict) and str(s.get("title") or "").strip()])
    return chapter_count, section_count


def auto_fill_report_slots(slots: Dict[str, str], fallback_topic: str = "") -> Dict[str, str]:
    filled = dict(slots)
    core_topic = str(filled.get("core_topic") or "").strip()
    if not core_topic:
        core_topic = fallback_topic if fallback_topic else REPORT_DEFAULTS["core_topic"]
    filled["core_topic"] = core_topic
    if not str(filled.get("focus_area") or "").strip():
        filled["focus_area"] = REPORT_DEFAULTS["focus_area"]
    if not str(filled.get("length_requirement") or "").strip():
        filled["length_requirement"] = REPORT_DEFAULTS["length_requirement"]
    if not str(filled.get("depth_level") or "").strip():
        filled["depth_level"] = REPORT_DEFAULTS["depth_level"]
    if not str(filled.get("format_style") or "").strip():
        filled["format_style"] = REPORT_DEFAULTS["format_style"]
    if not str(filled.get("dynamic_constraints") or "").strip():
        filled["dynamic_constraints"] = "无"
    return filled


def outline_scale_hint(length_requirement: str) -> Dict[str, Any]:
    lr = str(length_requirement or "").strip()
    if any(k in lr for k in ["简", "短"]):
        return {"chapter_min": 2, "chapter_max": 2, "sections_min": 2, "sections_max": 2, "label": "简短"}
    if any(k in lr for k in ["详", "长", "深"]):
        return {"chapter_min": 4, "chapter_max": 5, "sections_min": 3, "sections_max": 3, "label": "详尽"}
    return {"chapter_min": 3, "chapter_max": 4, "sections_min": 2, "sections_max": 3, "label": "常规"}
