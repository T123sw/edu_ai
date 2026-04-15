from __future__ import annotations

import json
import re
from typing import Any

from app.chat.agents.report_generation import get_fallback_llm


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _coerce_list(values: Any) -> list[str]:
    if isinstance(values, list):
        items = values
    elif values in (None, ""):
        items = []
    else:
        items = [values]
    normalized: list[str] = []
    for item in items:
        text = _clean(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _extract_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = _clean(item.get("text"))
            else:
                text = _clean(item)
            if text:
                chunks.append(text)
        return "\n".join(chunks).strip()
    return _clean(content)


def _strip_noise(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{") or candidate.startswith("["):
                cleaned = candidate
                break
    return cleaned.strip()


def _extract_json_payload(text: str) -> Any | None:
    cleaned = _strip_noise(text)
    if not cleaned:
        return None
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start >= 0 and end > start:
            snippet = cleaned[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                continue
    try:
        return json.loads(cleaned)
    except Exception:
        return None


def _artifact_title(topic: str, *, suffix: str) -> str:
    base = _clean(topic) or "教案"
    return f"{base}-{suffix}.json"


def _normalize_outline_payload(payload: Any, *, topic: str, audience: str, duration: str, lesson_type: str) -> dict[str, Any]:
    if isinstance(payload, dict):
        normalized = dict(payload)
    else:
        normalized = {}

    basic_info = dict(normalized.get("basic_info") or {})
    basic_info.setdefault("topic", topic)
    basic_info.setdefault("audience", audience)
    basic_info.setdefault("duration", duration)
    basic_info.setdefault("lesson_type", lesson_type)

    key_and_hard_points = dict(normalized.get("key_and_hard_points") or {})
    key_and_hard_points["key_points"] = _coerce_list(key_and_hard_points.get("key_points"))
    key_and_hard_points["hard_points"] = _coerce_list(key_and_hard_points.get("hard_points"))
    key_and_hard_points.setdefault("breakthrough_strategy", "")

    lesson_flow: list[dict[str, Any]] = []
    for item in list(normalized.get("lesson_flow") or []):
        if not isinstance(item, dict):
            continue
        lesson_flow.append(
            {
                "step": _clean(item.get("step")),
                "goal": _clean(item.get("goal")),
                "duration": _clean(item.get("duration")),
                "teacher_activities": _coerce_list(item.get("teacher_activities")),
                "student_activities": _coerce_list(item.get("student_activities")),
                "assessment": _clean(item.get("assessment")),
            }
        )

    teaching_support = dict(normalized.get("teaching_support") or {})
    teaching_support["teaching_methods"] = _coerce_list(teaching_support.get("teaching_methods"))
    teaching_support["teaching_aids"] = _coerce_list(teaching_support.get("teaching_aids"))
    teaching_support["board_plan"] = _coerce_list(teaching_support.get("board_plan"))
    teaching_support.setdefault("assessment_method", "")
    teaching_support.setdefault("homework_preview", "")

    return {
        "basic_info": basic_info,
        "teaching_objectives": _coerce_list(normalized.get("teaching_objectives")),
        "key_and_hard_points": key_and_hard_points,
        "lesson_flow": lesson_flow,
        "teaching_support": teaching_support,
    }


def _fallback_outline(*, slots: dict[str, Any], preparation: dict[str, Any], gathered_context: dict[str, Any]) -> dict[str, Any]:
    topic = _clean(slots.get("topic") or preparation.get("topic") or gathered_context.get("summary")) or "本课主题"
    audience = _clean(slots.get("audience") or preparation.get("audience"))
    duration = _clean(slots.get("duration") or preparation.get("duration")) or "40分钟"
    lesson_type = _clean(slots.get("lesson_type") or preparation.get("lesson_type")) or "新授课"
    objective = _clean(slots.get("objective") or preparation.get("objective")) or f"围绕{topic}完成本课教学"
    key_points = _coerce_list(preparation.get("key_points") or preparation.get("knowledge_points"))[:3]
    hard_points = _coerce_list(preparation.get("hard_points"))[:2]
    teaching_methods = _coerce_list(preparation.get("teaching_methods")) or ["讲授", "提问", "练习"]
    board_plan = key_points or [topic]
    homework_preview = _clean(preparation.get("homework_preference")) or f"围绕{topic}完成课后巩固练习"
    lesson_flow = [
        {
            "step": "导入",
            "goal": "激活旧知并导入主题",
            "duration": "5分钟",
            "teacher_activities": [f"创设与{topic}相关的情境并提出核心问题"],
            "student_activities": ["联系已有经验回答问题"],
            "assessment": "口头提问",
        },
        {
            "step": "新授/探究",
            "goal": "建构核心知识并突破重点难点",
            "duration": "25分钟",
            "teacher_activities": ["分步讲解关键概念", "组织示例分析与探究活动"],
            "student_activities": ["观察、讨论并完成课堂任务"],
            "assessment": "追问与当堂检查",
        },
        {
            "step": "练习巩固",
            "goal": "通过练习检验理解程度",
            "duration": "10分钟",
            "teacher_activities": ["布置分层练习并巡视指导"],
            "student_activities": ["独立或合作完成练习"],
            "assessment": "即时讲评",
        },
        {
            "step": "总结与作业",
            "goal": "回顾本课要点并布置课后任务",
            "duration": "5分钟",
            "teacher_activities": ["引导学生归纳重点", "说明作业要求"],
            "student_activities": ["口头总结并记录作业"],
            "assessment": "总结反馈",
        },
    ]
    return {
        "basic_info": {
            "topic": topic,
            "audience": audience,
            "duration": duration,
            "lesson_type": lesson_type,
        },
        "teaching_objectives": [objective] + [f"围绕{point}完成课堂理解与表达" for point in key_points[:2]],
        "key_and_hard_points": {
            "key_points": key_points,
            "hard_points": hard_points,
            "breakthrough_strategy": "通过情境示例、板书梳理和当堂练习逐步突破难点",
        },
        "lesson_flow": lesson_flow,
        "teaching_support": {
            "teaching_methods": teaching_methods,
            "teaching_aids": ["课件", "板书"],
            "board_plan": board_plan,
            "assessment_method": _clean(preparation.get("assessment_method")) or "课堂提问与练习反馈",
            "homework_preview": homework_preview,
        },
    }


def _normalize_content_payload(payload: Any, *, outline: Any, slots: dict[str, Any], preparation: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        normalized = dict(payload)
    else:
        normalized = {}

    outline_dict = outline if isinstance(outline, dict) else {}
    basic_info_from_outline = _outline_basic_info(outline)
    support = dict(outline_dict.get("teaching_support") or {}) if isinstance(outline_dict, dict) else {}
    key_and_hard = dict(outline_dict.get("key_and_hard_points") or {}) if isinstance(outline_dict, dict) else {}

    topic = _clean(
        normalized.get("title")
        or basic_info_from_outline.get("topic")
        or slots.get("topic")
        or preparation.get("topic")
    ) or "教案"

    basic_info = dict(normalized.get("basicInfo") or {})
    basic_info.setdefault("audience", _clean(basic_info_from_outline.get("audience") or slots.get("audience") or preparation.get("audience")))
    basic_info.setdefault("duration", _clean(basic_info_from_outline.get("duration") or slots.get("duration") or preparation.get("duration")))
    basic_info.setdefault("lessonType", _clean(basic_info_from_outline.get("lesson_type") or slots.get("lesson_type") or preparation.get("lesson_type")))

    process: list[dict[str, Any]] = []
    for item in list(normalized.get("process") or []):
        if not isinstance(item, dict):
            continue
        process.append(
            {
                "step": _clean(item.get("step")),
                "goal": _clean(item.get("goal")),
                "teacherActivities": _coerce_list(item.get("teacherActivities")),
                "studentActivities": _coerce_list(item.get("studentActivities")),
                "duration": _clean(item.get("duration")),
                "assessment": _clean(item.get("assessment")),
            }
        )

    return {
        "title": topic,
        "basicInfo": basic_info,
        "objectives": _coerce_list(normalized.get("objectives")),
        "keyPoints": _coerce_list(normalized.get("keyPoints") or key_and_hard.get("key_points")),
        "hardPoints": _coerce_list(normalized.get("hardPoints") or key_and_hard.get("hard_points")),
        "teachingMethods": _coerce_list(normalized.get("teachingMethods") or support.get("teaching_methods")),
        "teachingAids": _coerce_list(normalized.get("teachingAids") or support.get("teaching_aids")),
        "process": process,
        "boardPlan": _coerce_list(normalized.get("boardPlan") or support.get("board_plan")),
        "homework": _clean(normalized.get("homework") or support.get("homework_preview")),
        "reflectionTips": _coerce_list(normalized.get("reflectionTips")),
    }


def _outline_basic_info(outline: Any) -> dict[str, Any]:
    if not isinstance(outline, dict):
        return {}
    basic_info = outline.get("basic_info")
    if isinstance(basic_info, dict):
        return dict(basic_info)
    return {}


def _outline_flow_items(outline: Any) -> list[dict[str, Any]]:
    if isinstance(outline, dict):
        return [item for item in list(outline.get("lesson_flow") or []) if isinstance(item, dict)]
    if isinstance(outline, list):
        return [item for item in outline if isinstance(item, dict)]
    return []


def _outline_to_process(outline: Any) -> list[dict[str, Any]]:
    process: list[dict[str, Any]] = []
    for item in _outline_flow_items(outline):
        process.append(
            {
                "step": _clean(item.get("step") or item.get("title") or item.get("chapter_title")),
                "goal": _clean(item.get("goal") or item.get("summary") or item.get("chapter_goal")),
                "teacherActivities": _coerce_list(item.get("teacher_activities") or item.get("teacherActivities")),
                "studentActivities": _coerce_list(item.get("student_activities") or item.get("studentActivities")),
                "duration": _clean(item.get("duration") or item.get("minutes")),
                "assessment": _clean(item.get("assessment")),
            }
        )
    return process


def _build_default_process_actions(*, step: str, goal: str, topic: str) -> tuple[list[str], list[str], str]:
    step_text = _clean(step)
    goal_text = _clean(goal)
    topic_text = _clean(topic) or "本课主题"

    if any(token in step_text for token in ("导入", "热身", "情境")):
        return (
            [
                f"出示与{topic_text}相关的情境材料或图片，快速唤醒学生已有经验",
                f"围绕“{goal_text or topic_text}”抛出核心问题，让学生先做初步判断",
            ],
            [
                "结合已有认知口头回答教师提出的问题",
                "记录本节课需要重点解决的核心疑问",
            ],
            "通过口头回应判断学生是否进入学习情境",
        )

    if any(token in step_text for token in ("新授", "探究", "讲授", "分析")):
        return (
            [
                f"出示与{topic_text}直接相关的关键材料或案例，要求学生圈画有效信息",
                "按照问题链分步追问，督促学生用材料证据支撑自己的结论",
                "把核心概念、评价维度或因果关系同步板书出来，帮助学生形成结构",
            ],
            [
                "阅读材料并圈画关键证据，完成教师提供的表格或任务单",
                "结合问题链进行同桌或小组讨论，形成阶段性判断",
                "用口头汇报、板演或表格整理的方式呈现本组结论",
            ],
            "根据学生的证据提取、结论表达和汇报质量进行即时评价",
        )

    if any(token in step_text for token in ("练习", "巩固", "应用", "迁移")):
        return (
            [
                "布置分层练习或任务单，提醒学生先独立完成再进行同伴核对",
                "巡视作答过程，针对共性错误进行点拨和纠偏",
            ],
            [
                "独立完成练习并标注自己的疑问点",
                "与同伴互相核对答案，修正不完整或不准确的表达",
            ],
            "通过练习完成度和典型错误暴露情况判断是否真正掌握",
        )

    if any(token in step_text for token in ("总结", "作业", "提升", "反思")):
        return (
            [
                "引导学生回顾本节课解决了哪些关键问题，并归纳课堂方法",
                "说明必做与选做任务的要求和完成标准，提醒课后继续追踪的问题",
            ],
            [
                "用自己的话概括本节课的核心收获",
                "记录作业要求，并明确课后需要继续思考的方向",
            ],
            "通过学生复述和作业要求反馈判断课堂目标的达成度",
        )

    return (
        [
            f"围绕“{goal_text or topic_text}”组织课堂任务，明确步骤和时间要求",
            "根据学生反馈及时追问和点拨，帮助其完成阶段任务",
        ],
        [
            "按教师要求完成阅读、讨论或表达任务",
            "输出阶段性学习结果，并根据反馈及时修正",
        ],
        "根据学生的任务完成情况和表达质量进行即时评价",
    )


def _enrich_process_items(process: list[dict[str, Any]], *, topic: str) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in process:
        if not isinstance(item, dict):
            continue
        step = _clean(item.get("step"))
        goal = _clean(item.get("goal"))
        teacher_activities = _coerce_list(item.get("teacherActivities"))
        student_activities = _coerce_list(item.get("studentActivities"))
        assessment = _clean(item.get("assessment"))
        default_teacher, default_student, default_assessment = _build_default_process_actions(
            step=step,
            goal=goal,
            topic=topic,
        )
        enriched.append(
            {
                "step": step,
                "goal": goal,
                "teacherActivities": teacher_activities or default_teacher,
                "studentActivities": student_activities or default_student,
                "duration": _clean(item.get("duration")),
                "assessment": assessment or default_assessment,
            }
        )
    return enriched


def _build_homework_text(*, topic: str, preview: str, preference: str) -> str:
    preview_text = _clean(preview)
    preference_text = _clean(preference)
    if preview_text and ("必做" in preview_text or "选做" in preview_text):
        return preview_text
    if "分层" in preview_text or "分层" in preference_text:
        return (
            f"必做：整理{topic}的课堂笔记，完成基础巩固练习，并用 100-150 字写出本课最重要的一点认识。\n"
            f"选做：结合补充资料完成一段基于证据的分析短评，说明你如何评价{topic}中的关键问题。"
        )
    if preview_text:
        return f"必做：{preview_text}\n选做：结合课堂内容补充一个与本课主题相关的延伸分析。"
    return (
        f"必做：梳理{topic}的课堂笔记，完成基础练习，并用简短文字总结本课核心结论。\n"
        f"选做：围绕{topic}查找一则补充材料，尝试用课堂方法做进一步分析。"
    )


def _build_reflection_tips(*, key_and_hard: dict[str, Any], preparation: dict[str, Any]) -> list[str]:
    class_profile = _coerce_list(preparation.get("class_profile"))
    hard_points = _coerce_list(key_and_hard.get("hard_points") or preparation.get("hard_points"))
    breakthrough_strategy = _clean(key_and_hard.get("breakthrough_strategy"))
    result: list[str] = []

    for item in class_profile[:2]:
        result.append(f"留意学情风险：{item}")
    for item in hard_points[:2]:
        result.append(f"重点观察学生是否真正突破难点：{item}")
    if breakthrough_strategy:
        result.append(f"建议优先使用这一突破路径：{breakthrough_strategy}")
    if not result:
        result.append("留意学生是否能用证据支撑结论，而不是停留在空泛表态。")
        result.append("关注课堂讨论是否真正围绕核心问题推进，避免只热闹不落点。")
    return result


def _fallback_content(*, outline: Any, slots: dict[str, Any], preparation: dict[str, Any]) -> dict[str, Any]:
    outline_dict = outline if isinstance(outline, dict) else {}
    basic_info = _outline_basic_info(outline)
    support = dict(outline_dict.get("teaching_support") or {})
    key_and_hard = dict(outline_dict.get("key_and_hard_points") or {})
    topic = _clean(basic_info.get("topic") or slots.get("topic") or preparation.get("topic")) or "教案"
    objectives = _coerce_list(outline_dict.get("teaching_objectives")) or [
        _clean(slots.get("objective") or preparation.get("objective") or f"完成{topic}相关教学目标")
    ]
    process = _enrich_process_items(_outline_to_process(outline), topic=topic)
    reflection_tips = _build_reflection_tips(key_and_hard=key_and_hard, preparation=preparation)
    breakthrough_strategy = _clean(key_and_hard.get("breakthrough_strategy"))
    if breakthrough_strategy:
        reflection_tips.append(breakthrough_strategy)
    if not reflection_tips:
        reflection_tips.append("关注学生是否真正理解核心概念，并根据课堂反馈调整节奏")
    return {
        "title": topic,
        "basicInfo": {
            "audience": _clean(basic_info.get("audience") or slots.get("audience") or preparation.get("audience")),
            "duration": _clean(basic_info.get("duration") or slots.get("duration") or preparation.get("duration")),
            "lessonType": _clean(basic_info.get("lesson_type") or slots.get("lesson_type") or preparation.get("lesson_type")),
        },
        "objectives": objectives,
        "keyPoints": _coerce_list(key_and_hard.get("key_points") or preparation.get("key_points")),
        "hardPoints": _coerce_list(key_and_hard.get("hard_points") or preparation.get("hard_points")),
        "teachingMethods": _coerce_list(support.get("teaching_methods") or preparation.get("teaching_methods")) or ["讲授", "提问", "练习"],
        "teachingAids": _coerce_list(support.get("teaching_aids")) or ["课件", "板书"],
        "process": process,
        "boardPlan": _coerce_list(support.get("board_plan")),
        "homework": _clean(support.get("homework_preview") or preparation.get("homework_preference")) or f"围绕{topic}完成课后巩固任务",
        "reflectionTips": reflection_tips,
    }


def _fallback_content(*, outline: Any, slots: dict[str, Any], preparation: dict[str, Any]) -> dict[str, Any]:
    outline_dict = outline if isinstance(outline, dict) else {}
    basic_info = _outline_basic_info(outline)
    support = dict(outline_dict.get("teaching_support") or {})
    key_and_hard = dict(outline_dict.get("key_and_hard_points") or {})
    topic = _clean(basic_info.get("topic") or slots.get("topic") or preparation.get("topic")) or "教案"
    objectives = _coerce_list(outline_dict.get("teaching_objectives")) or [
        _clean(slots.get("objective") or preparation.get("objective") or f"完成{topic}相关教学目标")
    ]
    process = _enrich_process_items(_outline_to_process(outline), topic=topic)
    reflection_tips = _build_reflection_tips(key_and_hard=key_and_hard, preparation=preparation)
    return {
        "title": topic,
        "basicInfo": {
            "audience": _clean(basic_info.get("audience") or slots.get("audience") or preparation.get("audience")),
            "duration": _clean(basic_info.get("duration") or slots.get("duration") or preparation.get("duration")),
            "lessonType": _clean(basic_info.get("lesson_type") or slots.get("lesson_type") or preparation.get("lesson_type")),
        },
        "objectives": objectives,
        "keyPoints": _coerce_list(key_and_hard.get("key_points") or preparation.get("key_points")),
        "hardPoints": _coerce_list(key_and_hard.get("hard_points") or preparation.get("hard_points")),
        "teachingMethods": _coerce_list(support.get("teaching_methods") or preparation.get("teaching_methods")) or ["讲授", "提问", "练习"],
        "teachingAids": _coerce_list(support.get("teaching_aids")) or ["课件", "板书"],
        "process": process,
        "boardPlan": _coerce_list(support.get("board_plan")),
        "homework": _build_homework_text(
            topic=topic,
            preview=_clean(support.get("homework_preview")),
            preference=_clean(preparation.get("homework_preference")),
        ),
        "reflectionTips": reflection_tips,
    }

def _is_outline_confirm(feedback: Any) -> bool:
    normalized = _clean(feedback).lower().strip("。！？?，；;: ")
    if not normalized:
        return False
    return normalized in {
        "可以",
        "继续",
        "确认",
        "确认并继续",
        "开始",
        "ok",
        "yes",
    }


def _revise_fallback_outline(*, outline: Any, feedback: str, slots: dict[str, Any], preparation: dict[str, Any], gathered_context: dict[str, Any]) -> dict[str, Any]:
    revised = _fallback_outline(
        slots=slots,
        preparation=preparation,
        gathered_context=gathered_context,
    )
    if isinstance(outline, dict):
        revised = _normalize_outline_payload(
            outline,
            topic=_clean(revised.get("basic_info", {}).get("topic")),
            audience=_clean(revised.get("basic_info", {}).get("audience")),
            duration=_clean(revised.get("basic_info", {}).get("duration")),
            lesson_type=_clean(revised.get("basic_info", {}).get("lesson_type")),
        )
    feedback_text = _clean(feedback)
    if feedback_text:
        revised.setdefault("teaching_support", {})
        methods = _coerce_list(revised["teaching_support"].get("teaching_methods"))
        if "小组讨论" in feedback_text and "小组讨论" not in methods:
            methods.append("小组讨论")
        revised["teaching_support"]["teaching_methods"] = methods
        if "讨论" in feedback_text:
            revised_flow = list(revised.get("lesson_flow") or [])
            if not any(_clean(item.get("step")) == "小组讨论" for item in revised_flow if isinstance(item, dict)):
                revised_flow.append(
                    {
                        "step": "小组讨论",
                        "goal": feedback_text,
                        "duration": "8分钟",
                        "teacher_activities": ["布置讨论任务", "巡视并追问"],
                        "student_activities": ["分组讨论并汇报观点"],
                        "assessment": "小组汇报",
                    }
                )
                revised["lesson_flow"] = revised_flow
    return revised


class LessonPlanGenerationEngine:
    def __init__(self, *, llm=None):
        self.llm = llm

    def _invoke_llm(self, *, system_prompt: str, user_prompt: str) -> Any | None:
        if self.llm is None:
            return None
        try:
            return self.llm.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception:
            return None

    def _build_outline_prompt(
        self,
        *,
        slots: dict[str, Any],
        preparation: dict[str, Any],
        gathered_context: dict[str, Any],
        existing_outline: Any = None,
        human_feedback: str = "",
    ) -> str:
        prompt = (
            "你是一名资深一线教师教研员，请根据当前上下文输出一份可供教师确认的结构化教案大纲。"
            "必须返回 JSON 对象，不要输出任何解释。\n\n"
            "输出 schema：\n"
            "{\n"
            '  "basic_info": {"topic": "", "audience": "", "duration": "", "lesson_type": ""},\n'
            '  "teaching_objectives": ["..."],\n'
            '  "key_and_hard_points": {"key_points": ["..."], "hard_points": ["..."], "breakthrough_strategy": ""},\n'
            '  "lesson_flow": [{"step": "", "goal": "", "duration": "", "teacher_activities": ["..."], "student_activities": ["..."], "assessment": ""}],\n'
            '  "teaching_support": {"teaching_methods": ["..."], "teaching_aids": ["..."], "board_plan": ["..."], "assessment_method": "", "homework_preview": ""}\n'
            "}\n\n"
            "要求：\n"
            "1. lesson_flow 至少包含导入、新授/探究、练习巩固、总结与作业四段。\n"
            "2. 语言贴近教师备课表达，避免空泛口号。\n"
            "3. 若信息不足，可做合理补足，但必须与已有上下文一致。\n\n"
            f"slots={json.dumps(slots, ensure_ascii=False)}\n"
            f"preparation={json.dumps(preparation, ensure_ascii=False)}\n"
            f"gathered_context={json.dumps(gathered_context, ensure_ascii=False)}"
        )
        if existing_outline is not None:
            prompt += f"\nexisting_outline={json.dumps(existing_outline, ensure_ascii=False)}"
        if _clean(human_feedback):
            prompt += f"\nhuman_feedback={json.dumps(_clean(human_feedback), ensure_ascii=False)}"
        return prompt

    def _build_content_prompt(self, *, outline: Any, slots: dict[str, Any], preparation: dict[str, Any]) -> str:
        return (
            "你是一名资深教师，请基于已确认的教案大纲输出完整结构化教案。"
            "必须返回 JSON 对象，不要输出任何解释。\n\n"
            "输出 schema：\n"
            "{\n"
            '  "title": "",\n'
            '  "basicInfo": {"audience": "", "duration": "", "lessonType": ""},\n'
            '  "objectives": ["..."],\n'
            '  "keyPoints": ["..."],\n'
            '  "hardPoints": ["..."],\n'
            '  "teachingMethods": ["..."],\n'
            '  "teachingAids": ["..."],\n'
            '  "process": [{"step": "", "goal": "", "teacherActivities": ["..."], "studentActivities": ["..."], "duration": "", "assessment": ""}],\n'
            '  "boardPlan": ["..."],\n'
            '  "homework": "",\n'
            '  "reflectionTips": ["..."]\n'
            "}\n\n"
            "要求：\n"
            "1. process 与大纲 lesson_flow 一一对应，写得具体可执行。\n"
            "2. teacherActivities 和 studentActivities 用短句数组，不要写成一整段。\n"
            "3. reflectionTips 给教师使用提醒，不要写成学生作业。\n\n"
            f"outline={json.dumps(outline, ensure_ascii=False)}\n"
            f"slots={json.dumps(slots, ensure_ascii=False)}\n"
            f"preparation={json.dumps(preparation, ensure_ascii=False)}"
        )

    def _build_content_prompt(self, *, outline: Any, slots: dict[str, Any], preparation: dict[str, Any]) -> str:
        return (
            "你是一名有真实带班经验的一线教师，请基于已确认的大纲，输出一份教师可以直接拿去上课的结构化教案。"
            "必须返回 JSON 对象，不要输出任何解释。\n\n"
            "输出 schema：\n"
            "{\n"
            '  "title": "",\n'
            '  "basicInfo": {"audience": "", "duration": "", "lessonType": ""},\n'
            '  "objectives": ["..."],\n'
            '  "keyPoints": ["..."],\n'
            '  "hardPoints": ["..."],\n'
            '  "teachingMethods": ["..."],\n'
            '  "teachingAids": ["..."],\n'
            '  "process": [{"step": "", "goal": "", "teacherActivities": ["..."], "studentActivities": ["..."], "duration": "", "assessment": ""}],\n'
            '  "boardPlan": ["..."],\n'
            '  "homework": "",\n'
            '  "reflectionTips": ["..."]\n'
            "}\n\n"
            "硬性要求：\n"
            "1. 不要写假大空的套话，不要只写“培养能力”“激发兴趣”“引导学生思考”这类空泛表达，必须写出教师实际怎么做。\n"
            "2. process 必须与大纲 lesson_flow 一一对应，且每个环节都要写到可执行：教师出示什么、追问什么、组织什么任务、板书落点是什么。\n"
            "3. teacherActivities 和 studentActivities 必须是短句数组，不要写成大段空话；每个环节至少要有 2 条教师动作、2 条学生活动。\n"
            "4. studentActivities 必须体现可观察的学生产出，例如圈画证据、填写表格、口头汇报、小组结论、板演、批注等。\n"
            "5. assessment 必须贴合该环节，写清教师依据什么判断学生是否学会，不能笼统写“课堂评价”。\n"
            "6. 优先写真实课堂中的问题链、材料使用方式、板书落点、课堂任务和易错点，不要只是把大纲换个说法重复一遍。\n"
            "7. homework 请尽量写成更贴近日常教学的结构，优先使用“必做 + 选做”或“基础 + 提升”，避免一句话带过。\n"
            "8. reflectionTips 是给授课教师的真实提醒，要写学情风险、常见误区、课堂易跑偏点，不要再写成目标口号。\n\n"
            f"outline={json.dumps(outline, ensure_ascii=False)}\n"
            f"slots={json.dumps(slots, ensure_ascii=False)}\n"
            f"preparation={json.dumps(preparation, ensure_ascii=False)}"
        )

    @staticmethod
    def _build_ask_response(state: dict[str, Any]) -> dict[str, Any]:
        readiness_decision = dict(state.get("readiness_decision") or {})
        question = _clean(readiness_decision.get("question"))
        if not question:
            if readiness_decision.get("action") == "ask_topic":
                question = "这节课准备讲哪个主题？我先据此整理教案。"
            else:
                question = "这节课希望学生学会什么，或者你想先按知识讲解/活动探究哪种方向出一版大纲？"
        return {
            "reply": question,
            "status": "awaiting_human",
            "phase": "asking",
            "sources": [],
            "artifacts": [],
        }

    def _generate_outline(self, *, state: dict[str, Any]) -> dict[str, Any]:
        slots = dict(state.get("lesson_plan_slots") or {})
        preparation = dict(state.get("lesson_plan_preparation_result") or {})
        gathered_context = dict(state.get("gathered_context") or {})
        existing_outline = state.get("lesson_plan_outline")
        human_feedback = _clean(state.get("human_feedback"))
        topic = _clean(slots.get("topic") or preparation.get("topic")) or "教案"

        if existing_outline is not None and human_feedback:
            outline_payload = _revise_fallback_outline(
                outline=existing_outline,
                feedback=human_feedback,
                slots=slots,
                preparation=preparation,
                gathered_context=gathered_context,
            )
        else:
            outline_payload = _fallback_outline(
                slots=slots,
                preparation=preparation,
                gathered_context=gathered_context,
            )
        response = self._invoke_llm(
            system_prompt="你擅长把教学需求整理成教师可确认的教案大纲。",
            user_prompt=self._build_outline_prompt(
                slots=slots,
                preparation=preparation,
                gathered_context=gathered_context,
                existing_outline=existing_outline,
                human_feedback=human_feedback,
            ),
        )
        parsed = _extract_json_payload(_extract_text(response)) if response is not None else None
        if parsed is not None:
            outline_payload = _normalize_outline_payload(
                parsed,
                topic=topic,
                audience=_clean(slots.get("audience") or preparation.get("audience")),
                duration=_clean(slots.get("duration") or preparation.get("duration")),
                lesson_type=_clean(slots.get("lesson_type") or preparation.get("lesson_type")),
            )

        conversation_id = _clean(state.get("conversation_id")) or "lesson-plan"
        reply = "我先整理了一版教案大纲，你确认后我继续生成完整正文。"
        if existing_outline is not None and human_feedback:
            reply = "我已按你的意见调整了教案大纲，你看这版是否可以？"
        return {
            "reply": reply,
            "status": "awaiting_human",
            "phase": "outlining",
            "lesson_plan_outline": outline_payload,
            "artifacts": [
                {
                    "artifact_id": f"{conversation_id}:outline",
                    "artifact_type": "lesson_plan_outline",
                    "title": _artifact_title(topic, suffix="教案大纲"),
                    "content": outline_payload,
                }
            ],
            "sources": [],
        }

    def _generate_content(self, *, state: dict[str, Any]) -> dict[str, Any]:
        slots = dict(state.get("lesson_plan_slots") or {})
        preparation = dict(state.get("lesson_plan_preparation_result") or {})
        outline = state.get("lesson_plan_outline")
        basic_info = _outline_basic_info(outline)
        topic = _clean(
            basic_info.get("topic")
        ) or _clean(slots.get("topic") or preparation.get("topic")) or "教案"

        content_payload = _fallback_content(
            outline=outline,
            slots=slots,
            preparation=preparation,
        )
        response = self._invoke_llm(
            system_prompt="你擅长把已确认的大纲扩写成贴近真实课堂、教师可直接使用的结构化教案，拒绝空话和套话。",
            user_prompt=self._build_content_prompt(
                outline=outline,
                slots=slots,
                preparation=preparation,
            ),
        )
        parsed = _extract_json_payload(_extract_text(response)) if response is not None else None
        if parsed is not None:
            content_payload = _normalize_content_payload(
                parsed,
                outline=outline,
                slots=slots,
                preparation=preparation,
            )

        conversation_id = _clean(state.get("conversation_id")) or "lesson-plan"
        return {
            "final_response": "已根据确认的大纲生成完整教案，请在右侧查看。",
            "status": "completed",
            "phase": "generating",
            "lesson_plan_content": content_payload,
            "artifacts": [
                {
                    "artifact_id": f"{conversation_id}:content",
                    "artifact_type": "lesson_plan",
                    "title": _artifact_title(topic, suffix="教案"),
                    "content": content_payload,
                }
            ],
            "sources": [],
        }

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        if not bool(state.get("generation_ready")):
            return self._build_ask_response(state)
        if state.get("lesson_plan_outline") is not None and not _is_outline_confirm(state.get("human_feedback")) and _clean(state.get("human_feedback")):
            return self._generate_outline(state=state)
        if state.get("lesson_plan_outline") is not None:
            return self._generate_content(state=state)
        return self._generate_outline(state=state)


def build_default_lesson_plan_engine(*, llm=None):
    return LessonPlanGenerationEngine(llm=llm or get_fallback_llm())
