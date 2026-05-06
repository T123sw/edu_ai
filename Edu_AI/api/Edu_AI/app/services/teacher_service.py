"""Teacher service layer — lesson plan, report, quiz, and question generation.

Contains business orchestration: document loading, prompt assembly, LLM calling,
JSON parsing, and storage. Does NOT depend on HTTP or FastAPI.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.schemas.lesson_plan import LessonPlanMeta, LessonPlanResponse
from app.schemas.question import KnowledgePointsResponse, QuestionGenerateRequest, QuestionGenerateResponse, QuestionItem
from app.schemas.quiz import QuizQuestion, QuizResponse
from app.schemas.report import ReportResponse
from core import Config, lesson_plan_storage
from app.integrations.rag_client import load_selected_rag_documents
from app.integrations.llm_client import remove_thinking_tags, clean_json_text, smart_json_parse


def _fix_data_format(obj):
    if isinstance(obj, dict):
        fixed = {}
        for key, value in obj.items():
            if key in ['summary', 'introduction', 'conclusions']:
                if isinstance(value, list):
                    fixed[key] = '\n'.join(str(v) for v in value)
                else:
                    fixed[key] = str(value) if value is not None else ""
            elif key == 'mainContent' and isinstance(value, list):
                fixed[key] = []
                for section in value:
                    fixed_section = section.copy()
                    if 'content' in fixed_section and isinstance(fixed_section['content'], list):
                        fixed_section['content'] = '\n'.join(str(v) for v in fixed_section['content'])
                    if 'subsections' in fixed_section and isinstance(fixed_section['subsections'], list):
                        fixed_subsections = []
                        for sub in fixed_section['subsections']:
                            fixed_sub = sub.copy()
                            if 'content' in fixed_sub and isinstance(fixed_sub['content'], list):
                                fixed_sub['content'] = '\n'.join(str(v) for v in fixed_sub['content'])
                            fixed_subsections.append(fixed_sub)
                        fixed_section['subsections'] = fixed_subsections
                    fixed[key].append(fixed_section)
            else:
                fixed[key] = _fix_data_format(value) if isinstance(value, (dict, list)) else value
        return fixed
    elif isinstance(obj, list):
        return [_fix_data_format(item) for item in obj]
    else:
        return obj


# ---------------------------------------------------------------------------
# service functions
# ---------------------------------------------------------------------------

def generate_lesson_plan(
    payload,
    documents_content: List[Dict[str, str]],
    username: str,
    rag_system: Any,
    model_config: dict,
) -> LessonPlanResponse:
    """Generate a lesson plan from selected documents and return the response with storage ID."""
    documents_section = ""
    for idx, doc_info in enumerate(documents_content, 1):
        documents_section += f"""
【文档 {idx}：{doc_info['file_name']}】
{doc_info['content']}

---
"""

    difficulty_map = {"low": "低", "medium": "中", "high": "高"}
    difficulty_cn = difficulty_map.get(payload.difficulty, "中")

    kp_list = [k for k in payload.knowledge_points if k] or []
    kp_text = "、".join(kp_list) if kp_list else "（由模型根据文档内容自行提取）"

    key_points_text = payload.key_points if payload.key_points else "（由模型根据文档内容自行确定）"
    hard_points_text = payload.hard_points if payload.hard_points else "（由模型根据文档内容自行确定）"

    prompt = f"""
你现在是一名经验丰富的「教学设计专家」，需要根据给定的教学主题和参考文档，生成一份**具体、详细、可直接使用**的课堂教案，帮助教师减轻教学负担。

【教学主题】
{payload.topic}

【教学配置】
- 课时长度：约 {payload.duration} 分钟
- 教学难度：{difficulty_cn}
- 教师指定的知识点：{kp_text}
- 教师指定的教学重点：{key_points_text}
- 教师指定的教学难点：{hard_points_text}

【参考文档】
以下是教师选中的参考文档的完整内容，请仔细阅读这些文档，基于文档内容设计教案：

{documents_section}

【任务要求】
1. **必须基于上述参考文档的内容**来设计教案，确保教案内容与文档内容一致、准确。
2. 设计一节完整、实用的课堂教学活动，内容要**有细节、有步骤、可落地执行**。
3. 每个环节要写清楚：
   - 教师的具体活动（讲解内容、提问设计、板书要点、演示操作等）
   - 学生的具体活动（思考、讨论、练习、展示等）
   - 时间分配要合理
   - 教学方法和手段要具体
4. 教案要能真正帮助教师：
   - 提供具体的教学步骤和操作指导
   - 包含可用的提问、案例、练习等（可以从文档中提取）
   - 考虑学生的认知规律和学习难点
   - 提供教学建议和注意事项
5. **教案内容必须与参考文档内容紧密结合**，不要脱离文档内容空泛设计。
6. 注意：我们会用程序解析你的输出，因此必须返回合法 JSON，不能包含任何多余文字、注释或解释。

【输出要求（非常重要）】
1. 只输出一个 JSON 对象，不要输出任何 JSON 之外的文字。
2. JSON 的字段必须严格是下面这些，字段名不能更改，不能新增或缺少字段：

{{
  "title": "课程标题（简短，建议 10~20 字）",
  "objectives": [
    "教学目标 1（用 1~2 句话写清楚学生通过本课具体能做到什么）",
    "教学目标 2（1~2 句话）",
    "教学目标 3（可选，1~2 句话）"
  ],
  "keyPoints": [
    "教学重点 1（不超过 12 字，突出核心知识或能力）",
    "教学重点 2",
    "教学重点 3（可选）"
  ],
  "hardPoints": [
    "教学难点 1（不超过 12 字）",
    "教学难点 2（可选）"
  ],
  "process": [
    {{"step": "导入", "content": "用 5~8 句话详细写出导入环节...", "duration": "5-8分钟"}},
    {{"step": "新授", "content": "用 8~12 句话分步骤写出新授环节...", "duration": "20-30分钟"}},
    {{"step": "巩固练习", "content": "用 6~10 句话说明巩固环节...", "duration": "10-15分钟"}},
    {{"step": "小结", "content": "用 4~6 句话写出小结环节...", "duration": "3-5分钟"}},
    {{"step": "作业布置", "content": "用 3~5 句话说明作业环节...", "duration": "2-3分钟"}}
  ],
  "homework": "用 2~4 句话整体描述本节课的课后作业或思考任务，要求具体明确，可操作。"
}}

3. 所有文本内容必须是中文。
4. 各环节的 duration 总时长与给定课时长度大致匹配即可，无需完全相等。

【请开始输出】
现在请根据上述要求，直接输出唯一一个 JSON 对象，不要添加任何额外说明。
"""

    raw = rag_system._call_llm(prompt, llm_config=model_config)

    try:
        print("[lesson_plan_raw]", str(raw)[:2000])
    except Exception:
        pass

    cleaned_raw = remove_thinking_tags(raw)

    try:
        data = json.loads(cleaned_raw)
    except json.JSONDecodeError:
        cleaned = cleaned_raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.lstrip("`")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[1]
            if "```" in cleaned:
                cleaned = cleaned.rsplit("```", 1)[0]
        if "{" in cleaned and "}" in cleaned:
            cleaned = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]
        try:
            print("[lesson_plan_cleaned]", cleaned[:2000])
        except Exception:
            pass
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc2:
            partial = cleaned[: exc2.pos]
            data = json.loads(partial)

    plan = LessonPlanResponse(**data)

    plan_record = lesson_plan_storage.add_plan(
        title=plan.title, topic=payload.topic, difficulty=payload.difficulty,
        knowledge_points=payload.knowledge_points, plan=plan.model_dump(),
    )

    print(f"[LessonPlan] 检查course_id: {payload.course_id}")
    if payload.course_id:
        try:
            from core.course_storage import CourseStorageManager
            storage_manager = CourseStorageManager()
            material_data = {
                "id": plan_record["id"], "title": plan.title, "topic": payload.topic,
                "duration": payload.duration, "difficulty": payload.difficulty,
                "knowledge_points": payload.knowledge_points,
                "key_points": payload.key_points, "hard_points": payload.hard_points,
                "selected_doc_ids": payload.selected_doc_ids,
                "documents_used": [doc["file_name"] for doc in documents_content],
                "plan": plan.model_dump(), "created_at": plan_record["created_at"],
                "created_by": username, "material_type": "lesson_plan",
            }
            print(f"[LessonPlan] 准备保存教案到课程: {payload.course_id}, 教案ID: {plan_record['id']}")
            success = storage_manager.save_generated_material(
                course_id=payload.course_id, material_type="lesson_plan",
                material_id=plan_record["id"], material_data=material_data,
            )
            if success:
                print(f"[LessonPlan] ✅ 教案已保存到课程教学资源: {payload.course_id}, 教案ID: {plan_record['id']}")
            else:
                print(f"[LessonPlan] ⚠️ 警告：保存到课程教学资源失败")
        except Exception as e:
            print(f"[LessonPlan] ❌ 保存到课程教学资源时出错: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[LessonPlan] ⚠️ 警告：未提供course_id，教案不会保存到课程教学资源")

    plan_dict = plan.model_dump()
    plan_dict["id"] = plan_record["id"]
    return LessonPlanResponse(**plan_dict)


def generate_report(
    payload,
    documents_content: List[Dict[str, str]],
    username: str,
    rag_system: Any,
    model_config: dict,
) -> ReportResponse:
    """Generate an analysis report from selected documents."""
    documents_section = ""
    for idx, doc_info in enumerate(documents_content, 1):
        documents_section += f"""
【文档 {idx}：{doc_info['file_name']}】
{doc_info['content']}

---
"""

    focus_areas_text = ""
    if payload.focus_areas and len(payload.focus_areas) > 0:
        focus_areas_text = f"""
【重点关注领域】
请特别关注以下领域，在报告中详细展开：
{chr(10).join([f"- {area}" for area in payload.focus_areas])}

"""

    prompt = f"""
你现在是一名专业的「文档分析专家」，需要根据给定的参考文档，生成一份**结构清晰、内容详细、完整全面**的分析报告。

【参考文档】
以下是用户选中的参考文档的完整内容，请仔细阅读这些文档，基于文档内容生成报告：

{documents_section}

{focus_areas_text}【任务要求】
1. **必须完整总结所有文档的内容**，不能遗漏重要信息。
2. 报告要**结构清晰、层次分明**，使用合理的章节划分。
3. 内容要**非常详细**，对每个重要概念、知识点、方法都要进行深入分析和说明。
4. 报告要**逻辑严密**，各部分之间要有清晰的关联。
5. 对于复杂的概念或方法，要提供详细的解释和说明。
6. **关键：输出必须是完整、有效的JSON格式，所有字符串必须正确闭合，所有括号必须匹配。**

【输出要求（非常重要）】
1. **只输出一个完整的JSON对象，不要输出任何JSON之外的文字、注释或解释。**
2. **确保JSON格式完全正确：所有字符串用双引号闭合，所有括号匹配，所有逗号正确放置。**
3. **控制内容长度：每个content字段建议控制在300-500字以内，避免过长导致JSON截断。**
4. JSON的字段必须严格是下面这些：

{{
  "title": "报告标题（15~30字）",
  "summary": "执行摘要（8~12句话，字符串，控制在200字以内）",
  "introduction": "引言（6~10句话，字符串，控制在200字以内）",
  "mainContent": [
    {{
      "title": "第一章标题",
      "content": "第一章内容（15~20句话，字符串，控制在400字以内）",
      "subsections": [
        {{
          "title": "1.1 子章节标题",
          "content": "子章节内容（8~12句话，字符串，控制在250字以内）"
        }}
      ]
    }},
    {{
      "title": "第二章标题",
      "content": "第二章内容（15~20句话，字符串，控制在400字以内）",
      "subsections": null
    }}
  ],
  "keyFindings": ["发现1", "发现2", "发现3"],
  "conclusions": "结论（10~15句话，字符串，控制在300字以内）",
  "recommendations": ["建议1", "建议2"] 或 null
}}

5. **重要约束：**
   - 所有文本字段（summary、introduction、content、conclusions）必须是字符串，不能是数组
   - mainContent建议3~5个章节，每个章节1~3个子章节
   - keyFindings建议5~8条
   - 每个content字段不要超过500字，避免JSON过长被截断
   - 确保JSON完整输出，不要中途截断

【请开始输出】
直接输出JSON对象，确保格式正确且完整。
"""

    print(f"[Report] 开始调用LLM生成报告...")
    raw = rag_system._call_llm(prompt, llm_config=model_config)
    print(f"[Report] LLM调用成功，返回内容长度: {len(raw) if raw else 0}")
    if not raw:
        raise ValueError("大模型返回内容为空")

    cleaned_raw = clean_json_text(raw)
    try:
        print(f"[Report] 清理后的内容（前2000字符）: {cleaned_raw[:2000]}")
    except Exception:
        pass

    data = smart_json_parse(cleaned_raw)
    if data is None:
        print(f"[Report] ❌ 所有JSON解析策略都失败")
        raise ValueError("无法解析模型返回的JSON内容。请重试或检查模型配置。")

    print(f"[Report] ✅ JSON解析成功")

    try:
        data = _fix_data_format(data)
        print(f"[Report] 数据格式修复完成")
    except Exception as fix_error:
        print(f"[Report] 数据格式修复失败: {fix_error}")

    required_fields = {
        'title': '报告', 'summary': '报告摘要', 'introduction': '报告引言',
        'mainContent': [], 'keyFindings': [], 'conclusions': '报告结论',
    }
    for field, default_value in required_fields.items():
        if field not in data or data[field] is None:
            data[field] = default_value
            print(f"[Report] 警告：字段 {field} 缺失，已使用默认值")

    if 'keyFindings' in data and not isinstance(data['keyFindings'], list):
        data['keyFindings'] = [data['keyFindings']] if isinstance(data['keyFindings'], str) and data['keyFindings'] else []

    if 'mainContent' in data and not isinstance(data['mainContent'], list):
        data['mainContent'] = []

    if isinstance(data.get('mainContent'), list):
        for section in data['mainContent']:
            if not isinstance(section, dict):
                continue
            section.setdefault('title', '章节')
            section.setdefault('content', '内容')
            section.setdefault('subsections', None)

    if 'recommendations' in data and data['recommendations'] is not None:
        if not isinstance(data['recommendations'], list):
            data['recommendations'] = [data['recommendations']] if isinstance(data['recommendations'], str) and data['recommendations'] else None

    report = ReportResponse(**data)
    print(f"[Report] 数据结构验证成功")

    report_id = str(uuid.uuid4())

    print(f"[Report] 检查course_id: {payload.course_id}")
    if payload.course_id:
        try:
            from core.course_storage import CourseStorageManager
            storage_manager = CourseStorageManager()
            material_data = {
                "id": report_id, "title": report.title,
                "selected_doc_ids": payload.selected_doc_ids,
                "documents_used": [doc["file_name"] for doc in documents_content],
                "focus_areas": payload.focus_areas, "report": report.model_dump(),
                "created_at": datetime.now().isoformat(), "created_by": username,
                "material_type": "report",
            }
            print(f"[Report] 准备保存报告到课程: {payload.course_id}, 报告ID: {report_id}")
            success = storage_manager.save_generated_material(
                course_id=payload.course_id, material_type="report",
                material_id=report_id, material_data=material_data,
            )
            if success:
                print(f"[Report] ✅ 报告已保存到课程教学资源: {payload.course_id}, 报告ID: {report_id}")
            else:
                print(f"[Report] ⚠️ 警告：保存到课程教学资源失败")
        except Exception as e:
            print(f"[Report] ❌ 保存到课程教学资源时出错: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[Report] ⚠️ 警告：未提供course_id，报告不会保存到课程教学资源")

    report_dict = report.model_dump()
    report_dict["id"] = report_id
    return ReportResponse(**report_dict)


def generate_quiz(
    payload,
    documents_content: List[Dict[str, str]],
    username: str,
    rag_system: Any,
    model_config: dict,
) -> QuizResponse:
    """Generate a quiz from selected documents. Delegates question generation internally."""
    question_type_map = {"choice": ["choice"], "blank": ["blank"], "mixed": ["choice", "blank"]}
    difficulty_map = {"easy": "low", "medium": "medium", "hard": "high"}

    knowledge_points: List[str] = []
    for doc in documents_content:
        content = doc.get("content", "")
        if content:
            knowledge_points.append(f"【{doc.get('file_name', '文档')}】\n{content[:4000]}")

    question_payload = QuestionGenerateRequest(
        knowledge_points=knowledge_points,
        types=question_type_map[payload.question_type],
        difficulty=difficulty_map[payload.difficulty],
        count=payload.count,
    )

    generated = generate_questions(question_payload, rag_system, model_config)

    mapped_questions: List[QuizQuestion] = []
    for idx, q in enumerate(generated.questions, start=1):
        qtype_raw = str(q.type).strip()
        normalized_type = "choice" if "选择" in qtype_raw or qtype_raw.lower() == "choice" else "blank"
        if normalized_type == "blank" and payload.question_type == "choice":
            continue
        if normalized_type == "choice" and payload.question_type == "blank":
            continue
        mapped_questions.append(
            QuizQuestion(
                id=str(idx), type=normalized_type, stem=q.content,
                options=q.options if normalized_type == "choice" else None,
                answer=q.answer or "", explanation=q.analysis or "",
            )
        )

    if not mapped_questions:
        raise ValueError("未生成有效测验题目，请稍后重试")

    if len(mapped_questions) > payload.count:
        mapped_questions = mapped_questions[: payload.count]

    quiz_id = f"quiz_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    quiz_title = payload.title or f"测验-{datetime.now().strftime('%Y-%m-%d')}"

    if payload.course_id:
        try:
            from core.course_storage import CourseStorageManager
            storage_manager = CourseStorageManager()
            material_data = {
                "id": quiz_id, "title": quiz_title, "question_type": payload.question_type,
                "difficulty": payload.difficulty, "count": len(mapped_questions),
                "selected_doc_ids": payload.selected_doc_ids,
                "documents_used": [doc["file_name"] for doc in documents_content],
                "questions": [q.model_dump() for q in mapped_questions],
                "created_at": datetime.now().isoformat(), "created_by": username,
                "material_type": "quiz",
            }
            storage_manager.save_generated_material(
                course_id=payload.course_id, material_type="quiz",
                material_id=quiz_id, material_data=material_data,
            )
        except Exception as e:
            print(f"[Quiz] 保存课程资源失败: {e}")

    return QuizResponse(
        id=quiz_id, title=quiz_title, difficulty=payload.difficulty,
        question_type=payload.question_type, questions=mapped_questions,
    )


def generate_questions(
    payload: QuestionGenerateRequest,
    rag_system: Any,
    model_config: dict,
) -> QuestionGenerateResponse:
    """Generate assessment questions."""
    difficulty_map = {"low": "低", "medium": "中", "high": "高"}
    diff_cn = difficulty_map.get(payload.difficulty, "中")

    kp_text = "、".join(payload.knowledge_points) if payload.knowledge_points else "（教师未特别指定）"
    type_map = {"choice": "选择题", "blank": "填空题", "short": "简答题"}
    type_labels = [type_map.get(t, t) for t in payload.types] or ["选择题", "填空题", "简答题"]

    prompt = f"""
你是一名资深教学测评专家，需要根据教师提供的参数，设计一批严谨、可直接用于课堂或线上练习的题目。请严格遵守以下约束：

【出题范围】
- 知识点：{kp_text}（若为"（教师未特别指定）"则你需自行选取与课程主题强相关的典型知识点）
- 允许的题目类型（非常重要）：{"、".join(type_labels)}
- 目标题量：约 {payload.count} 道题
- 整体难度定位：{diff_cn}（对应 low=低、medium=中、high=高）

【题型规则】
1. 只允许生成上面列出的题型，严禁出现其它类型。若只允许 1 种题型，则所有题目必须完全一致。
2. 各题型的格式要求：
   - 选择题：必须给出 4 个选项 A/B/C/D，选项文字不能过短，每个选项应互斥；`answer` 中只写正确选项字母；`analysis` 用 2~4 句话说明解题思路或易错点。
   - 填空题：题干中用"____"表示空格，如有多个空需编号；`answer` 需按顺序给出所有空的标准答案；`analysis` 说明考察点与参考理由。
   - 简答题：题干一般以"请简要说明/分析/比较…"开头；`answer` 用 3~5 句话给出要点；`analysis` 补充评分要点或拓展思考。
3. 每道题必须注明 `difficulty`，只能写"低/中/高"之一，可根据题目实际情况微调，但整体分布需契合 {diff_cn}。

【内容质量要求】
1. 题干需自洽完整，不能引用"上文/下文"之类的上下文。
2. 题目要紧扣所给知识点，避免泛泛而谈。
3. 题目之间不要重复或仅做数值替换，要体现多样化的考察角度。
4. `analysis` 一定要有教学价值：指出解题关键、常见误区或拓展提醒。
5. 所有文本必须是简体中文，避免英语或拼音混杂。

【输出格式（务必严格遵守）】
只输出一个 JSON 对象，结构固定为：
{{
  "questions": [
    {{
      "id": 1,
      "type": "选择题 | 填空题 | 简答题",
      "difficulty": "低 | 中 | 高",
      "content": "题干内容……",
      "options": ["A. …", "B. …", "C. …", "D. …"],
      "answer": "……",
      "analysis": "……"
    }}
  ]
}}
- 字段名不可增删。
- 不属于允许题型的问题必须丢弃，不得出现在数组里。
- 若你多写了说明文字、Markdown 等，视为不合格。

现在请根据上述要求，直接输出唯一一个 JSON 对象。
"""

    raw = rag_system._call_llm(prompt, llm_config=model_config)
    cleaned_raw = remove_thinking_tags(raw)

    try:
        data = json.loads(cleaned_raw)
    except json.JSONDecodeError:
        cleaned = cleaned_raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.lstrip("`")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[1]
            if "```" in cleaned:
                cleaned = cleaned.rsplit("```", 1)[0]
        if "{" in cleaned and "}" in cleaned:
            cleaned = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]
        data = json.loads(cleaned)

    questions_raw = data.get("questions")
    if not isinstance(questions_raw, list):
        raise ValueError("模型返回数据结构不符合预期（缺少 questions 数组）")

    items: List[QuestionItem] = []
    for idx, q in enumerate(questions_raw, start=1):
        if not isinstance(q, dict):
            continue
        try:
            item = QuestionItem(
                id=int(q.get("id") or idx),
                type=str(q.get("type") or "题目"),
                difficulty=str(q.get("difficulty") or diff_cn),
                content=str(q.get("content") or ""),
                options=q.get("options") or None,
                answer=q.get("answer") or None,
                analysis=q.get("analysis") or None,
            )
            if item.content.strip():
                items.append(item)
        except Exception:
            continue

    if not items:
        raise ValueError("模型未返回有效题目，请稍后重试")

    return QuestionGenerateResponse(questions=items)


def suggest_knowledge_points(
    course_name: str,
    rag_system: Any,
    model_config: dict,
) -> KnowledgePointsResponse:
    """Suggest knowledge points for a course name."""
    prompt = f"""你是一名教学设计专家，请围绕下面的课程名称，联想出该课可能涉及的核心知识点列表。
课程名称：{course_name}

请按以下要求返回：
1. 仅输出一个 JSON 对象，字段名为 "knowledge_points"。
2. "knowledge_points" 的值是一个字符串数组，每个元素是 2-6 个字的简短中文知识点。
3. 列出 5-10 个知识点，按教学逻辑大致从基础到进阶排序。
示例：
{{"knowledge_points": ["概念定义", "基本性质", "典型应用", "常见误区"]}}

现在请针对上述课程名称，返回对应的 JSON："""

    raw = rag_system._call_llm(prompt, llm_config=model_config)
    cleaned_raw = remove_thinking_tags(raw)

    data = json.loads(cleaned_raw)

    points = data.get("knowledge_points")
    if not isinstance(points, list):
        raise ValueError("模型返回数据结构不符合预期（缺少 knowledge_points 数组）")

    clean = [str(p).strip() for p in points if str(p).strip()]
    return KnowledgePointsResponse(knowledge_points=clean)


def list_lesson_plans() -> dict:
    """List all lesson plan metadata."""
    data = lesson_plan_storage.list_plans()
    return data


def get_lesson_plan_detail(plan_id: str) -> dict:
    """Get a single lesson plan by ID."""
    record = lesson_plan_storage.get_plan(plan_id)
    return record


def delete_lesson_plan(plan_id: str, course_id: Optional[str] = None) -> None:
    """Delete a lesson plan and optionally its course material."""
    lesson_plan_storage.delete_plan(plan_id)
    if course_id:
        try:
            from core.course_storage import CourseStorageManager
            CourseStorageManager().delete_generated_material(
                course_id=course_id, material_type="lesson_plan", material_id=plan_id,
            )
            print(f"[LessonPlan] 已从课程资源删除: {course_id}/{plan_id}")
        except Exception as e:
            print(f"[LessonPlan] 从课程资源删除时出错: {e}")


def delete_report(report_id: str, course_id: str) -> None:
    """Delete a report from course materials."""
    if not course_id:
        raise ValueError("必须提供course_id")
    from core.course_storage import CourseStorageManager
    CourseStorageManager().delete_generated_material(
        course_id=course_id, material_type="report", material_id=report_id,
    )
    print(f"[Report] 已从课程资源删除: {course_id}/{report_id}")


def delete_quiz(quiz_id: str, course_id: str) -> None:
    """Delete a quiz from course materials."""
    if not course_id:
        raise ValueError("必须提供course_id")
    from core.course_storage import CourseStorageManager
    ok = CourseStorageManager().delete_generated_material(
        course_id=course_id, material_type="quiz", material_id=quiz_id,
    )
    if not ok:
        raise KeyError("测验不存在或删除失败")
    print(f"[Quiz] 已从课程资源删除: {course_id}/{quiz_id}")


def get_course_materials(course_id: str, material_type: Optional[str] = None) -> list:
    """List generated materials for a course."""
    from core.course_storage import CourseStorageManager
    storage_manager = CourseStorageManager()
    materials = storage_manager.list_generated_materials(course_id, material_type)
    print(f"[CourseMaterials] 从存储加载了 {len(materials)} 个资料")

    result = []
    for material in materials:
        material_id = material.get("material_id") or material.get("id")
        material_type_key = material.get("material_type") or material_type or "unknown"
        print(f"[CourseMaterials] 处理资料: id={material_id}, type={material_type_key}, title={material.get('title', 'N/A')}")

        content = None
        if material_type_key == "lesson_plan":
            content = material.get("plan")
        elif material_type_key == "report":
            content = material.get("report")
        else:
            content = material

        result.append({
            "id": material_id,
            "name": material.get("title") or material.get("name", "未命名"),
            "type": material_type_key,
            "addedAt": material.get("created_at") or material.get("addedAt", ""),
            "courseId": course_id,
            "content": content,
        })
        print(f"[CourseMaterials] 添加资料到结果: {result[-1]['name']} ({result[-1]['type']})")

    print(f"[CourseMaterials] 返回 {len(result)} 个资料给前端")
    return result
