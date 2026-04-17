"""FastAPI 主入口，仅保留认证与新 RAG 接口"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import router as auth_router, get_current_user
from app.pipeline import router as pipeline_router
from app.courses import router as courses_router
from app.blog_agent import router as blog_agent_router
from app.deepsearch import router as deepsearch_router
from app.chat import router as chat_router
from app.chat.api.routes_v2 import router as chat_v2_router
from app.speech.routes import router as speech_router
from app.teaching_video_bridge import get_ai_lecturer_process_manager
from app.video_routes import router as video_router
from core import Config, conversation_storage, lesson_plan_storage
from rag_v2.api import router as rag_router, get_rag_system
from rag_v2.document_resolver import load_rag_document_content


class ChatRequest(BaseModel):
    """聊天请求（复用前端接口，内部使用 rag_v2 系统）"""

    question: str = Field(..., description="用户问题")
    conversation_id: Optional[str] = Field(default=None, description="对话ID")
    top_k: int = Field(default=5, ge=1, le=20, description="检索文档数量")
    model_id: Optional[str] = Field(
        default=None, description="模型ID（Config中注册的模型）"
    )
    use_rag: Optional[bool] = Field(default=True, description="是否使用RAG检索")
    selected_doc_ids: Optional[List[str]] = Field(
        default=None, 
        description="用户选中的文档ID列表（file_path），如果提供，则只在这些文档中检索"
    )


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: List[Dict[str, Any]]
    title: Optional[str] = None
    model_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    message: str
    knowledge_base_ready: bool
    document_count: int


class ModelInfo(BaseModel):
    id: str
    name: str
    model_name: Optional[str]


class LessonPlanRequest(BaseModel):
    """教案生成请求"""

    topic: str = Field(..., description="教学主题/章节（必填）")
    course_id: Optional[str] = Field(None, description="课程ID，用于保存到教学资源")
    selected_doc_ids: List[str] = Field(
        ..., description="选中的文档ID列表（必填，至少选择一个文档）"
    )
    duration: int = Field(45, description="课时长度（分钟），默认45分钟")
    difficulty: str = Field("medium", description="教学难度：low/medium/high，默认medium")
    knowledge_points: List[str] = Field(
        default_factory=list, description="知识点标签列表（可选）"
    )
    key_points: Optional[str] = Field(None, description="教学重点（可选）")
    hard_points: Optional[str] = Field(None, description="教学难点（可选）")


class LessonPlanStep(BaseModel):
    step: str
    content: str
    duration: str


class LessonPlanResponse(BaseModel):
    id: Optional[str] = None  # 教案ID（生成后返回）
    title: str
    objectives: List[str]
    keyPoints: List[str]
    hardPoints: List[str]
    process: List[LessonPlanStep]
    homework: str


class ReportRequest(BaseModel):
    title: Optional[str] = Field(None, description="报告标题（可选，不填则自动生成）")
    course_id: Optional[str] = Field(None, description="课程ID")
    selected_doc_ids: List[str] = Field(..., description="选中的文档ID列表（必填）")
    focus_areas: Optional[List[str]] = Field(None, description="重点关注领域（可选）")


class ReportSection(BaseModel):
    title: str
    content: str
    subsections: Optional[List[Dict[str, str]]] = None  # 子章节，格式: [{"title": "...", "content": "..."}]


class ReportResponse(BaseModel):
    id: Optional[str] = None  # 报告ID（生成后返回）
    title: str
    summary: str  # 执行摘要
    introduction: str  # 引言
    mainContent: List[ReportSection]  # 主要内容章节
    keyFindings: List[str]  # 关键发现
    conclusions: str  # 结论
    recommendations: Optional[List[str]] = None  # 建议（可选）


class QuizRequest(BaseModel):
    title: Optional[str] = Field(None, description="测验标题（可选）")
    course_id: Optional[str] = Field(None, description="课程ID")
    selected_doc_ids: List[str] = Field(..., description="选中的文档ID列表（必填）")
    question_type: str = Field("mixed", description="题目类型：choice/blank/mixed")
    count: int = Field(10, ge=5, le=20, description="题目数量（5-20）")
    difficulty: str = Field("medium", description="难度：easy/medium/hard")


class QuizQuestion(BaseModel):
    id: str
    type: str  # choice | blank
    stem: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str


class QuizResponse(BaseModel):
    id: Optional[str] = None
    title: str
    difficulty: str  # easy | medium | hard
    question_type: str  # choice | blank | mixed
    questions: List[QuizQuestion]


class KnowledgePointsRequest(BaseModel):
    course_name: str = Field(..., description="课程名称")


class KnowledgePointsResponse(BaseModel):
    knowledge_points: List[str]


class LessonPlanMeta(BaseModel):
  id: str
  title: str
  topic: str
  difficulty: str
  knowledge_points: List[str]
  created_at: str
  updated_at: str


class LessonPlanListResponse(BaseModel):
  plans: List[LessonPlanMeta]
  count: int


class QuestionItem(BaseModel):
    id: int
    type: str
    difficulty: str
    content: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None


class QuestionGenerateRequest(BaseModel):
    knowledge_points: List[str] = Field(
        default_factory=list, description="知识点列表，用于约束出题范围"
    )
    types: List[str] = Field(
        default_factory=list,
        description="题目类型列表：choice(选择题)/blank(填空题)/short(简答题)",
    )
    difficulty: str = Field(
        "medium", description="题目整体难度：low/medium/high，对应 低/中/高"
    )
    count: int = Field(10, ge=1, le=100, description="题目数量")


class QuestionGenerateResponse(BaseModel):
    questions: List[QuestionItem]


def _load_selected_rag_documents(
    rag_system: Any,
    selected_doc_ids: List[str],
    *,
    owner: str,
    log_prefix: str,
) -> List[Dict[str, str]]:
    documents_content: List[Dict[str, str]] = []
    print(f"[{log_prefix}] 开始通过 rag_v2 resolver 处理 {len(selected_doc_ids)} 个选中文档")

    for doc_id in selected_doc_ids:
        try:
            loaded_document = load_rag_document_content(rag_system, doc_id, owner=owner)
            if loaded_document is None:
                print(f"[{log_prefix}] 文档未通过 rag_v2 resolver 加载: {doc_id}")
                continue

            documents_content.append(
                {
                    "file_name": loaded_document.file_name,
                    "content": loaded_document.content,
                }
            )
            print(
                f"[{log_prefix}] rag_v2 resolver 已加载文档 {loaded_document.file_name}，"
                f"内容长度: {len(loaded_document.content)} 字符"
            )
        except Exception as exc:
            print(f"[{log_prefix}] 通过 rag_v2 resolver 获取文档 {doc_id} 内容失败: {exc}")
            continue

    return documents_content


app = FastAPI(title=Config.APP_NAME, version="1.0.0")

# 注册路由
app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(chat_v2_router)
app.include_router(speech_router)
app.include_router(video_router)
app.include_router(pipeline_router, prefix="/api/pipeline")
app.include_router(blog_agent_router, prefix="/api/blog")
app.include_router(deepsearch_router)  # 深度搜索路由

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOW_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_ai_lecturer_bridge() -> None:
    try:
        get_ai_lecturer_process_manager().ensure_started()
    except Exception as exc:
        print(f"[AI Lecturer] startup skipped: {exc}")


@app.on_event("shutdown")
def _shutdown_ai_lecturer_bridge() -> None:
    try:
        get_ai_lecturer_process_manager().shutdown()
    except Exception as exc:
        print(f"[AI Lecturer] shutdown skipped: {exc}")


@app.post("/teacher/lesson_plan", response_model=LessonPlanResponse)
async def generate_lesson_plan(
    payload: LessonPlanRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    教案生成接口：基于用户选中的文档完整内容生成教案，并自动保存到教学资源。
    要求：必须至少选择一个文档，教案将基于这些文档的完整内容生成。
    """
    try:
        rag_system = get_rag_system()
        model_config = Config.get_deep_model()
        username = current_user.get("username", "teacher")

        # 验证必须选择文档
        if not payload.selected_doc_ids or len(payload.selected_doc_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="必须至少选择一个文档才能生成教案"
            )

        documents_content = _load_selected_rag_documents(
            rag_system,
            payload.selected_doc_ids,
            owner=username,
            log_prefix="LessonPlan",
        )
        
        if not documents_content:
            raise HTTPException(
                status_code=400,
                detail="无法获取选中文档的内容，请检查文档是否存在且可访问"
            )

        # 拼接所有文档内容
        documents_section = ""
        for idx, doc_info in enumerate(documents_content, 1):
            documents_section += f"""
【文档 {idx}：{doc_info['file_name']}】
{doc_info['content']}

---
"""

        # 构建教学配置信息
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
    {{"step": "导入", "content": "用 5~8 句话详细写出导入环节：1) 教师如何创设情境（具体场景、案例、问题等）；2) 如何提出问题或任务；3) 如何引导学生回顾旧知或激发兴趣；4) 学生的可能反应和参与方式；5) 如何自然过渡到新课。要求具体可操作，不要泛泛而谈。", "duration": "5-8分钟"}},
    {{"step": "新授", "content": "用 8~12 句话分步骤写出新授环节：1) 教师讲解的核心内容（具体知识点、概念、原理等）；2) 板书要点（列出关键板书内容）；3) 使用的教学材料或多媒体（具体展示什么、如何展示）；4) 提问设计（具体的问题、提问时机、预期回答）；5) 学生活动（思考、讨论、回答、操作等具体任务）；6) 重点难点的突破方法；7) 互动环节的组织方式。要求详细具体，能直接指导教学。", "duration": "20-30分钟"}},
    {{"step": "巩固练习", "content": "用 6~10 句话说明巩固环节：1) 练习的具体形式（选择题、计算题、案例分析、小组讨论、实践操作等）；2) 练习的具体内容或题目示例；3) 教师如何组织（分组方式、时间安排、巡视要点）；4) 教师如何点拨和指导（常见错误、关键提示）；5) 学生如何展示和反馈（展示方式、评价标准）；6) 如何总结练习结果。要求提供可用的练习内容和组织方法。", "duration": "10-15分钟"}},
    {{"step": "小结", "content": "用 4~6 句话写出小结环节：1) 教师如何引导学生归纳（提问方式、总结框架）；2) 要归纳的核心知识要点（列出具体要点）；3) 要强调的方法或思想；4) 如何鼓励学生用自己的话总结；5) 如何与下节课内容衔接。要求具体明确，不是简单说\"总结\"。", "duration": "3-5分钟"}},
    {{"step": "作业布置", "content": "用 3~5 句话说明作业环节：1) 作业的具体内容（题目、任务、阅读材料等）；2) 作业的要求和标准（字数、格式、完成时间等）；3) 作业的目的和意义；4) 如何检查或评价作业。要求作业具体可操作，有明确要求。", "duration": "2-3分钟"}}
  ],
  "homework": "用 2~4 句话整体描述本节课的课后作业或思考任务，要求具体明确，可操作。"
}}

3. 所有文本内容必须是中文。
4. 各环节的 duration 总时长与给定课时长度大致匹配即可，无需完全相等。

【请开始输出】
现在请根据上述要求，直接输出唯一一个 JSON 对象，不要添加任何额外说明。
"""

        raw = rag_system._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]

        import json

        # 为了方便排查问题，打印一份模型原始输出（只截取前 2k 字符）
        try:
            print("[lesson_plan_raw]", str(raw)[:2000])
        except Exception:
            # 打印失败忽略
            pass

        # 移除思考过程标签
        import re
        def remove_thinking_tags(text: str) -> str:
            """移除各种思考过程标签"""
            patterns = [
                r'<think>.*?</think>',
                r'<thinking>.*?</thinking>',
                r'<thought>.*?</thought>',
            ]
            cleaned = text
            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            return cleaned.strip()

        # 清理思考过程
        cleaned_raw = remove_thinking_tags(raw)

        try:
            # 先直接按严格 JSON 解析
            data = json.loads(cleaned_raw)
        except json.JSONDecodeError:
            # 如果直接解析失败，再做一轮“宽松模式”的清洗与解析
            cleaned = cleaned_raw.strip()

            # 去掉 Markdown 代码块包裹（``` / ```json 等）
            if cleaned.startswith("```"):
                cleaned = cleaned.lstrip("`")
                if "\n" in cleaned:
                    cleaned = cleaned.split("\n", 1)[1]
                if "```" in cleaned:
                    cleaned = cleaned.rsplit("```", 1)[0]

            # 只保留最外层的大括号内容
            if "{" in cleaned and "}" in cleaned:
                cleaned = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]

            # 再打印一次清洗后的内容，方便定位问题
            try:
                print("[lesson_plan_cleaned]", cleaned[:2000])
            except Exception:
                pass

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as exc2:
                # 如果是 Extra data 之类错误，尝试截取到首个合法 JSON 位置
                try:
                    partial = cleaned[: exc2.pos]
                    data = json.loads(partial)
                except Exception as exc3:
                    raise HTTPException(
                        status_code=500,
                        detail=f"模型返回内容解析失败，请稍后重试: {exc3}",
                    )
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"模型返回内容解析失败，请稍后重试: {exc}",
                )

        try:
            plan = LessonPlanResponse(**data)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"模型返回数据结构不符合预期: {exc}",
            )

        # 保存到教案存储
        plan_record = lesson_plan_storage.add_plan(
            title=plan.title,
            topic=payload.topic,
            difficulty=payload.difficulty,
            knowledge_points=payload.knowledge_points,
            plan=plan.model_dump(),
        )

        # 如果提供了course_id，自动保存到课程教学资源
        print(f"[LessonPlan] 检查course_id: {payload.course_id}")
        if payload.course_id:
            try:
                from core.course_storage import CourseStorageManager
                storage_manager = CourseStorageManager()
                
                # 准备教案数据
                material_data = {
                    "id": plan_record["id"],
                    "title": plan.title,
                    "topic": payload.topic,
                    "duration": payload.duration,
                    "difficulty": payload.difficulty,
                    "knowledge_points": payload.knowledge_points,
                    "key_points": payload.key_points,
                    "hard_points": payload.hard_points,
                    "selected_doc_ids": payload.selected_doc_ids,
                    "documents_used": [doc["file_name"] for doc in documents_content],
                    "plan": plan.model_dump(),
                    "created_at": plan_record["created_at"],
                    "created_by": username,
                    "material_type": "lesson_plan",  # 添加material_type字段，便于后续识别
                }
                
                print(f"[LessonPlan] 准备保存教案到课程: {payload.course_id}, 教案ID: {plan_record['id']}")
                
                # 保存到课程教学资源
                success = storage_manager.save_generated_material(
                    course_id=payload.course_id,
                    material_type="lesson_plan",
                    material_id=plan_record["id"],
                    material_data=material_data
                )
                
                if success:
                    print(f"[LessonPlan] ✅ 教案已保存到课程教学资源: {payload.course_id}, 教案ID: {plan_record['id']}")
                else:
                    print(f"[LessonPlan] ⚠️ 警告：保存到课程教学资源失败，course_id: {payload.course_id}, 教案ID: {plan_record['id']}")
            except Exception as e:
                print(f"[LessonPlan] ❌ 保存到课程教学资源时出错: {e}")
                import traceback
                traceback.print_exc()
                # 不抛出异常，因为教案已经保存到lesson_plan_storage
        else:
            print(f"[LessonPlan] ⚠️ 警告：未提供course_id，教案不会保存到课程教学资源")

        # 返回教案响应，包含ID以便前端使用
        plan_dict = plan.model_dump()
        plan_dict["id"] = plan_record["id"]
        return LessonPlanResponse(**plan_dict)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成教案失败: {exc}") from exc


@app.post("/teacher/report", response_model=ReportResponse)
async def generate_report(
    payload: ReportRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    报告生成接口：基于用户选中的文档完整内容生成详细报告，并自动保存到教学资源。
    要求：必须至少选择一个文档，报告将完整总结这些文档的内容，结构清晰且非常详细。
    """
    try:
        rag_system = get_rag_system()
        model_config = Config.get_deep_model()
        username = current_user.get("username", "teacher")

        # 验证必须选择文档
        if not payload.selected_doc_ids or len(payload.selected_doc_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="必须至少选择一个文档才能生成报告"
            )

        documents_content = _load_selected_rag_documents(
            rag_system,
            payload.selected_doc_ids,
            owner=username,
            log_prefix="Report",
        )
        
        if not documents_content:
            raise HTTPException(
                status_code=400,
                detail="无法获取选中文档的内容，请检查文档是否存在且可访问"
            )

        # 拼接所有文档内容
        documents_section = ""
        for idx, doc_info in enumerate(documents_content, 1):
            documents_section += f"""
【文档 {idx}：{doc_info['file_name']}】
{doc_info['content']}

---
"""

        # 构建重点关注领域文本
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

        try:
            print(f"[Report] 开始调用LLM生成报告...")
            raw = rag_system._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]
            print(f"[Report] LLM调用成功，返回内容长度: {len(raw) if raw else 0}")
            if not raw:
                raise HTTPException(
                    status_code=500,
                    detail="大模型返回内容为空",
                )
        except HTTPException:
            raise
        except Exception as llm_error:
            print(f"[Report] LLM调用失败: {llm_error}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"调用大模型失败: {str(llm_error)}",
            )

        import json
        import re

        # 清理思考过程标签和代码块标记
        def clean_json_text(text: str) -> str:
            """清理JSON文本，移除代码块标记和思考过程标签"""
            cleaned = text.strip()
            
            # 移除思考过程标签
            patterns = [
                r'<think>.*?</think>',
                r'<thinking>.*?</thinking>',
                r'<thought>.*?</thought>',
                r'<think>.*?</think>',
            ]
            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            
            # 移除代码块标记（```json 或 ```）
            if cleaned.startswith("```"):
                # 移除开头的 ```json 或 ```
                lines = cleaned.split("\n", 1)
                if len(lines) > 1:
                    cleaned = lines[1]
                else:
                    # 如果只有一行，直接移除 ```
                    cleaned = cleaned.lstrip("`")
            
            if cleaned.endswith("```"):
                # 移除结尾的 ```
                cleaned = cleaned.rsplit("```", 1)[0]
            
            cleaned = cleaned.strip()
            
            # 找到JSON部分（从第一个 { 开始）
            if "{" in cleaned:
                first_brace = cleaned.find("{")
                cleaned = cleaned[first_brace:]
            
            return cleaned

        cleaned_raw = clean_json_text(raw)
        
        # 打印清理后的内容（前2000字符）用于调试
        try:
            print(f"[Report] 清理后的内容（前2000字符）: {cleaned_raw[:2000]}")
        except Exception:
            pass

        # 智能JSON解析函数
        def smart_json_parse(text: str) -> Optional[dict]:
            """智能JSON解析，使用多种策略尝试解析"""
            import re
            
            # 策略1：直接解析
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
            
            # 策略2：找到最后一个完整的JSON对象（通过括号匹配）
            try:
                brace_count = 0
                last_valid_pos = -1
                for i, char in enumerate(text):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            last_valid_pos = i
                
                if last_valid_pos > 0:
                    truncated = text[:last_valid_pos + 1]
                    return json.loads(truncated)
            except (json.JSONDecodeError, IndexError):
                pass
            
            # 策略3：修复未闭合的字符串（从最后一个字段开始）
            try:
                fixed = text
                # 找到最后一个 "field": " 模式
                field_pattern = r'"(\w+)":\s*"'
                matches = list(re.finditer(field_pattern, fixed))
                
                if matches:
                    last_field = matches[-1]
                    field_start = last_field.end()
                    remaining = fixed[field_start:]
                    
                    # 检查字符串是否闭合
                    quote_pos = -1
                    i = 0
                    while i < len(remaining):
                        if remaining[i] == '"':
                            # 检查转义
                            backslash_count = 0
                            j = i - 1
                            while j >= 0 and remaining[j] == '\\':
                                backslash_count += 1
                                j -= 1
                            if backslash_count % 2 == 0:
                                quote_pos = field_start + i
                                break
                        i += 1
                    
                    if quote_pos == -1:
                        # 字符串未闭合，找到应该结束的位置
                        end_pos = len(fixed)
                        for i in range(field_start, len(fixed)):
                            if fixed[i] == '\n':
                                after = fixed[i+1:].lstrip()
                                if after and after[0] in ['}', ']', ',']:
                                    end_pos = i
                                    break
                        
                        # 在end_pos位置插入闭合引号
                        before = fixed[:end_pos].rstrip()
                        after = fixed[end_pos:].lstrip()
                        
                        if after and after[0] in ['}', ']']:
                            fixed = before + '"' + after
                        elif after and after[0] == ',':
                            fixed = before + '"' + after
                        else:
                            fixed = before + '"' + (after if after else '}')
                        
                        # 补全括号
                        open_braces = fixed.count('{')
                        close_braces = fixed.count('}')
                        missing = open_braces - close_braces
                        if missing > 0:
                            fixed += '}' * missing
                        
                        return json.loads(fixed)
            except (json.JSONDecodeError, Exception) as e:
                print(f"[Report] 字符串修复策略失败: {e}")
            
            # 策略4：容错模式 - 使用正则表达式提取关键字段（即使JSON不完整也能提取部分信息）
            try:
                result = {}
                
                # 提取title（简单字符串，不包含转义）
                title_match = re.search(r'"title"\s*:\s*"([^"]*)"', text)
                if title_match:
                    result['title'] = title_match.group(1)
                
                # 提取summary（支持转义字符，但限制长度避免过长）
                summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
                if summary_match:
                    summary_text = summary_match.group(1)
                    # 处理转义字符
                    summary_text = summary_text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                    result['summary'] = summary_text[:500]  # 限制长度
                
                # 提取introduction
                intro_match = re.search(r'"introduction"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
                if intro_match:
                    intro_text = intro_match.group(1)
                    intro_text = intro_text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                    result['introduction'] = intro_text[:500]
                
                # 提取conclusions
                concl_match = re.search(r'"conclusions"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
                if concl_match:
                    concl_text = concl_match.group(1)
                    concl_text = concl_text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                    result['conclusions'] = concl_text[:500]
                
                # 提取keyFindings（数组）
                findings_match = re.search(r'"keyFindings"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                if findings_match:
                    findings_text = findings_match.group(1)
                    findings = re.findall(r'"((?:[^"\\]|\\.)*)"', findings_text)
                    result['keyFindings'] = [f.replace('\\"', '"').replace('\\n', '\n') for f in findings[:10]]
                else:
                    result['keyFindings'] = []
                
                # 提取mainContent（简化版，只提取title和content）
                main_match = re.search(r'"mainContent"\s*:\s*\[(.*)\]', text, re.DOTALL)
                if main_match:
                    content_text = main_match.group(1)
                    sections = []
                    # 提取每个章节（简化：只提取title和content，忽略subsections）
                    # 使用更宽松的模式，允许content可能未闭合
                    section_pattern = r'\{\s*"title"\s*:\s*"([^"]*)"\s*,\s*"content"\s*:\s*"((?:[^"\\]|\\.)*)"'
                    section_matches = re.finditer(section_pattern, content_text, re.DOTALL)
                    for match in section_matches:
                        content = match.group(2).replace('\\"', '"').replace('\\n', '\n')[:400]
                        sections.append({
                            'title': match.group(1),
                            'content': content,
                            'subsections': None
                        })
                    if sections:
                        result['mainContent'] = sections[:5]
                    else:
                        result['mainContent'] = []
                else:
                    result['mainContent'] = []
                
                # 提取recommendations（可选）
                rec_match = re.search(r'"recommendations"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                if rec_match:
                    rec_text = rec_match.group(1)
                    recommendations = re.findall(r'"((?:[^"\\]|\\.)*)"', rec_text)
                    result['recommendations'] = [r.replace('\\"', '"') for r in recommendations[:5]]
                else:
                    # 检查是否为null
                    if r'"recommendations"\s*:\s*null' in text or '"recommendations"' in text and 'null' in text:
                        result['recommendations'] = None
                    else:
                        result['recommendations'] = None
                
                # 如果至少提取到了title和summary，认为部分成功
                if result.get('title') and result.get('summary'):
                    print(f"[Report] ⚠️ 使用容错模式提取部分数据（title: {result.get('title')}, mainContent: {len(result.get('mainContent', []))}个章节）")
                    return result
            except Exception as e:
                print(f"[Report] 容错提取也失败: {e}")
                import traceback
                traceback.print_exc()
            
            return None
        
        # 使用智能解析
        data = smart_json_parse(cleaned_raw)
        
        if data is None:
            print(f"[Report] ❌ 所有JSON解析策略都失败")
            print(f"[Report] 清理后的内容长度: {len(cleaned_raw)}")
            print(f"[Report] 清理后的内容（完整）: {cleaned_raw}")
            raise HTTPException(
                status_code=500,
                detail="无法解析模型返回的JSON内容。请重试或检查模型配置。",
            )
        
        print(f"[Report] ✅ JSON解析成功")

        # 修复可能的格式问题：将数组转换为字符串
        def fix_data_format(obj):
            """递归修复数据格式，将数组字段转换为字符串"""
            if isinstance(obj, dict):
                fixed = {}
                for key, value in obj.items():
                    if key in ['summary', 'introduction', 'conclusions']:
                        # 这些字段必须是字符串
                        if isinstance(value, list):
                            fixed[key] = '\n'.join(str(v) for v in value)
                        else:
                            fixed[key] = str(value) if value is not None else ""
                    elif key == 'mainContent' and isinstance(value, list):
                        # 修复mainContent中的content字段
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
                        fixed[key] = fix_data_format(value) if isinstance(value, (dict, list)) else value
                return fixed
            elif isinstance(obj, list):
                return [fix_data_format(item) for item in obj]
            else:
                return obj
        
        # 修复数据格式
        try:
            data = fix_data_format(data)
            print(f"[Report] 数据格式修复完成")
        except Exception as fix_error:
            print(f"[Report] 数据格式修复失败: {fix_error}")
            # 继续尝试，可能不需要修复
        
        # 确保所有必需字段存在，缺失则提供默认值
        required_fields = {
            'title': '报告',
            'summary': '报告摘要',
            'introduction': '报告引言',
            'mainContent': [],
            'keyFindings': [],
            'conclusions': '报告结论',
        }
        
        for field, default_value in required_fields.items():
            if field not in data or data[field] is None:
                data[field] = default_value
                print(f"[Report] 警告：字段 {field} 缺失，已使用默认值")
        
        # 确保keyFindings是列表
        if 'keyFindings' in data and not isinstance(data['keyFindings'], list):
            if isinstance(data['keyFindings'], str):
                data['keyFindings'] = [data['keyFindings']] if data['keyFindings'] else []
            else:
                data['keyFindings'] = []
        
        # 确保mainContent是列表
        if 'mainContent' in data and not isinstance(data['mainContent'], list):
            data['mainContent'] = []
        
        # 确保mainContent中的每个section都有必需的字段
        if isinstance(data.get('mainContent'), list):
            for section in data['mainContent']:
                if not isinstance(section, dict):
                    continue
                if 'title' not in section:
                    section['title'] = '章节'
                if 'content' not in section:
                    section['content'] = '内容'
                if 'subsections' not in section:
                    section['subsections'] = None
        
        # 确保recommendations是列表或None
        if 'recommendations' in data and data['recommendations'] is not None:
            if not isinstance(data['recommendations'], list):
                if isinstance(data['recommendations'], str):
                    data['recommendations'] = [data['recommendations']] if data['recommendations'] else None
                else:
                    data['recommendations'] = None

        try:
            report = ReportResponse(**data)
            print(f"[Report] 数据结构验证成功")
        except Exception as exc:
            print(f"[Report] 数据结构验证失败: {exc}")
            print(f"[Report] 数据内容: {str(data)[:500]}")
            print(f"[Report] 数据字段: {list(data.keys())}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"模型返回数据结构不符合预期: {exc}",
            )

        # 生成报告ID
        import uuid
        report_id = str(uuid.uuid4())

        # 如果提供了course_id，自动保存到课程教学资源
        print(f"[Report] 检查course_id: {payload.course_id}")
        if payload.course_id:
            try:
                from core.course_storage import CourseStorageManager
                storage_manager = CourseStorageManager()
                
                # 准备报告数据
                material_data = {
                    "id": report_id,
                    "title": report.title,
                    "selected_doc_ids": payload.selected_doc_ids,
                    "documents_used": [doc["file_name"] for doc in documents_content],
                    "focus_areas": payload.focus_areas,
                    "report": report.model_dump(),
                    "created_at": datetime.now().isoformat(),
                    "created_by": username,
                    "material_type": "report",  # 添加material_type字段，便于后续识别
                }
                
                print(f"[Report] 准备保存报告到课程: {payload.course_id}, 报告ID: {report_id}")
                
                # 保存到课程教学资源
                success = storage_manager.save_generated_material(
                    course_id=payload.course_id,
                    material_type="report",
                    material_id=report_id,
                    material_data=material_data
                )
                
                if success:
                    print(f"[Report] ✅ 报告已保存到课程教学资源: {payload.course_id}, 报告ID: {report_id}")
                else:
                    print(f"[Report] ⚠️ 警告：保存到课程教学资源失败，course_id: {payload.course_id}, report_id: {report_id}")
                    # 保存失败时记录更详细的错误信息
            except Exception as e:
                print(f"[Report] ❌ 保存到课程教学资源时出错: {e}")
                import traceback
                traceback.print_exc()
                # 不抛出异常，因为报告已经生成成功，只是保存到课程资源失败
        else:
            print(f"[Report] ⚠️ 警告：未提供course_id，报告不会保存到课程教学资源")

        # 返回报告响应，包含ID
        report_dict = report.model_dump()
        report_dict["id"] = report_id
        return ReportResponse(**report_dict)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {exc}") from exc


@app.post("/teacher/quiz", response_model=QuizResponse)
async def generate_quiz(
    payload: QuizRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    测验生成接口：根据选中文档和配置生成测验，并自动保存到课程资源。
    """
    try:
        rag_system = get_rag_system()
        model_config = Config.get_deep_model()
        username = current_user.get("username", "teacher")

        if not payload.selected_doc_ids or len(payload.selected_doc_ids) == 0:
            raise HTTPException(status_code=400, detail="必须至少选择一个文档才能生成测验")

        question_type_map = {
            "choice": ["choice"],
            "blank": ["blank"],
            "mixed": ["choice", "blank"],
        }
        if payload.question_type not in question_type_map:
            raise HTTPException(status_code=400, detail="question_type 仅支持 choice/blank/mixed")

        difficulty_map = {
            "easy": "low",
            "medium": "medium",
            "hard": "high",
        }
        if payload.difficulty not in difficulty_map:
            raise HTTPException(status_code=400, detail="difficulty 仅支持 easy/medium/hard")

        documents_content = _load_selected_rag_documents(
            rag_system,
            payload.selected_doc_ids,
            owner=username,
            log_prefix="Quiz",
        )

        if not documents_content:
            raise HTTPException(status_code=400, detail="无法获取选中文档内容，请检查文档状态")

        knowledge_points: List[str] = []
        for doc in documents_content:
            content = doc.get("content", "")
            if content:
                snippet = content[:4000]
                knowledge_points.append(f"【{doc.get('file_name', '文档')}】\n{snippet}")

        question_payload = QuestionGenerateRequest(
            knowledge_points=knowledge_points,
            types=question_type_map[payload.question_type],
            difficulty=difficulty_map[payload.difficulty],
            count=payload.count,
        )

        generated = await generate_questions(question_payload)

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
                    id=str(idx),
                    type=normalized_type,
                    stem=q.content,
                    options=q.options if normalized_type == "choice" else None,
                    answer=q.answer or "",
                    explanation=q.analysis or "",
                )
            )

        if not mapped_questions:
            raise HTTPException(status_code=500, detail="未生成有效测验题目，请稍后重试")

        if len(mapped_questions) > payload.count:
            mapped_questions = mapped_questions[: payload.count]

        quiz_id = f"quiz_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        quiz_title = payload.title or f"测验-{datetime.now().strftime('%Y-%m-%d')}"

        if payload.course_id:
            try:
                from core.course_storage import CourseStorageManager
                storage_manager = CourseStorageManager()
                material_data = {
                    "id": quiz_id,
                    "title": quiz_title,
                    "question_type": payload.question_type,
                    "difficulty": payload.difficulty,
                    "count": len(mapped_questions),
                    "selected_doc_ids": payload.selected_doc_ids,
                    "documents_used": [doc["file_name"] for doc in documents_content],
                    "questions": [q.model_dump() for q in mapped_questions],
                    "created_at": datetime.now().isoformat(),
                    "created_by": username,
                    "material_type": "quiz",
                }
                storage_manager.save_generated_material(
                    course_id=payload.course_id,
                    material_type="quiz",
                    material_id=quiz_id,
                    material_data=material_data,
                )
            except Exception as e:
                print(f"[Quiz] 保存课程资源失败: {e}")

        return QuizResponse(
            id=quiz_id,
            title=quiz_title,
            difficulty=payload.difficulty,
            question_type=payload.question_type,
            questions=mapped_questions,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成测验失败: {exc}") from exc


@app.post("/teacher/knowledge_points", response_model=KnowledgePointsResponse)
async def suggest_knowledge_points(payload: KnowledgePointsRequest):
    """
    根据课程名称智能联想知识点列表
    """
    try:
        rag_system = get_rag_system()
        model_config = Config.get_deep_model()

        prompt = f"""你是一名教学设计专家，请围绕下面的课程名称，联想出该课可能涉及的核心知识点列表。
课程名称：{payload.course_name}

请按以下要求返回：
1. 仅输出一个 JSON 对象，字段名为 "knowledge_points"。
2. "knowledge_points" 的值是一个字符串数组，每个元素是 2-6 个字的简短中文知识点。
3. 列出 5-10 个知识点，按教学逻辑大致从基础到进阶排序。
示例：
{{"knowledge_points": ["概念定义", "基本性质", "典型应用", "常见误区"]}}

现在请针对上述课程名称，返回对应的 JSON："""

        raw = rag_system._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]

        import json
        import re

        # 移除思考过程标签
        def remove_thinking_tags(text: str) -> str:
            """移除各种思考过程标签"""
            patterns = [
                r'<think>.*?</think>',
                r'<thinking>.*?</thinking>',
                r'<thought>.*?</thought>',
            ]
            cleaned = text
            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            return cleaned.strip()

        # 清理思考过程
        cleaned_raw = remove_thinking_tags(raw)

        try:
            data = json.loads(cleaned_raw)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"模型返回内容解析失败，请稍后重试: {exc}",
            )

        points = data.get("knowledge_points")
        if not isinstance(points, list):
            raise HTTPException(
                status_code=500,
                detail="模型返回数据结构不符合预期（缺少 knowledge_points 数组）",
            )

        clean = [str(p).strip() for p in points if str(p).strip()]
        return KnowledgePointsResponse(knowledge_points=clean)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成知识点失败: {exc}") from exc


@app.get("/teacher/lesson_plans", response_model=LessonPlanListResponse)
async def list_lesson_plans():
    """
    教案列表：仅返回元数据，便于前端列表展示
    """
    try:
        data = lesson_plan_storage.list_plans()
        plans = [
            LessonPlanMeta(
                id=item["id"],
                title=item.get("title") or "",
                topic=item.get("topic") or "",
                difficulty=item.get("difficulty") or "",
                knowledge_points=item.get("knowledge_points") or [],
                created_at=item.get("created_at") or "",
                updated_at=item.get("updated_at") or "",
            )
            for item in data.get("plans", [])
        ]
        return LessonPlanListResponse(plans=plans, count=len(plans))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取教案列表失败: {exc}") from exc


@app.get("/teacher/lesson_plans/{plan_id}", response_model=LessonPlanResponse)
async def get_lesson_plan_detail(plan_id: str):
    """
    教案详情：返回完整教案内容
    """
    try:
        record = lesson_plan_storage.get_plan(plan_id)
        plan_data = record.get("plan") or {}
        return LessonPlanResponse(**plan_data)
    except KeyError:
        raise HTTPException(status_code=404, detail="教案不存在")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取教案详情失败: {exc}") from exc


@app.delete("/teacher/lesson_plans/{plan_id}")
async def delete_lesson_plan(
    plan_id: str,
    course_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    删除教案
    """
    try:
        # 删除教案存储
        lesson_plan_storage.delete_plan(plan_id)
        
        # 如果提供了course_id，同时从课程教学资源中删除
        if course_id:
            try:
                from core.course_storage import CourseStorageManager
                storage_manager = CourseStorageManager()
                storage_manager.delete_generated_material(
                    course_id=course_id,
                    material_type="lesson_plan",
                    material_id=plan_id
                )
                print(f"[LessonPlan] 已从课程资源删除: {course_id}/{plan_id}")
            except Exception as e:
                print(f"[LessonPlan] 从课程资源删除时出错: {e}")
                # 不抛出异常，因为教案已经删除
        
        return {"message": "教案已删除"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除教案失败: {exc}") from exc


@app.delete("/teacher/reports/{report_id}")
async def delete_report(
    report_id: str,
    course_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    删除报告
    """
    try:
        # 从课程资源中删除
        if course_id:
            try:
                from core.course_storage import CourseStorageManager
                storage_manager = CourseStorageManager()
                storage_manager.delete_generated_material(
                    course_id=course_id,
                    material_type="report",
                    material_id=report_id
                )
                print(f"[Report] 已从课程资源删除: {course_id}/{report_id}")
            except Exception as e:
                print(f"[Report] 从课程资源删除时出错: {e}")
                raise HTTPException(status_code=500, detail=f"删除报告失败: {e}")
        else:
            raise HTTPException(status_code=400, detail="必须提供course_id")
        
        return {"message": "报告已删除"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除报告失败: {exc}") from exc


@app.delete("/teacher/quizzes/{quiz_id}")
async def delete_quiz(
    quiz_id: str,
    course_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    删除测验
    """
    try:
        if not course_id:
            raise HTTPException(status_code=400, detail="必须提供course_id")

        from core.course_storage import CourseStorageManager
        storage_manager = CourseStorageManager()
        ok = storage_manager.delete_generated_material(
            course_id=course_id,
            material_type="quiz",
            material_id=quiz_id,
        )

        if not ok:
            raise HTTPException(status_code=404, detail="测验不存在或删除失败")

        print(f"[Quiz] 已从课程资源删除: {course_id}/{quiz_id}")
        return {"message": "测验已删除"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除测验失败: {exc}") from exc


@app.get("/api/courses/{course_id}/materials")
async def get_course_materials(
    course_id: str,
    material_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    获取课程的教学资源列表
    """
    try:
        from core.course_storage import CourseStorageManager
        storage_manager = CourseStorageManager()
        
        materials = storage_manager.list_generated_materials(course_id, material_type)
        
        print(f"[CourseMaterials] 从存储加载了 {len(materials)} 个资料")
        
        # 转换格式以匹配前端期望
        result = []
        for material in materials:
            material_id = material.get("material_id") or material.get("id")
            # 优先使用material中的material_type，如果没有则从文件路径推断或使用参数
            material_type_key = material.get("material_type")
            
            # 如果material中没有material_type，尝试从文件路径推断
            if not material_type_key:
                # 从material_id对应的文件路径推断类型
                # 但更简单的方法是使用传入的material_type参数
                material_type_key = material_type or "unknown"
            
            print(f"[CourseMaterials] 处理资料: id={material_id}, type={material_type_key}, title={material.get('title', 'N/A')}")
            
            # 根据类型构建前端需要的格式
            # 对于教案，content应该是plan字段
            # 对于报告，content应该是report字段
            # 对于其他类型，content是整个material
            content = None
            if material_type_key == "lesson_plan":
                content = material.get("plan")
                if not content:
                    print(f"[CourseMaterials] ⚠️ 警告：教案 {material_id} 缺少plan字段")
            elif material_type_key == "report":
                content = material.get("report")
                if not content:
                    print(f"[CourseMaterials] ⚠️ 警告：报告 {material_id} 缺少report字段")
            else:
                content = material
            
            result_item = {
                "id": material_id,
                "name": material.get("title") or material.get("name", "未命名"),
                "type": material_type_key,
                "addedAt": material.get("created_at") or material.get("addedAt", ""),
                "courseId": course_id,
                "content": content,  # 使用提取的content
            }
            result.append(result_item)
            print(f"[CourseMaterials] 添加资料到结果: {result_item['name']} ({result_item['type']})")
        
        print(f"[CourseMaterials] 返回 {len(result)} 个资料给前端")
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取课程资源失败: {exc}") from exc


@app.post("/teacher/questions", response_model=QuestionGenerateResponse)
async def generate_questions(payload: QuestionGenerateRequest):
    """
    题目生成接口：根据知识点、题型和难度生成题目列表
    """
    try:
        rag_system = get_rag_system()
        model_config = Config.get_deep_model()

        difficulty_map = {"low": "低", "medium": "中", "high": "高"}
        diff_cn = difficulty_map.get(payload.difficulty, "中")

        kp_text = "、".join(payload.knowledge_points) if payload.knowledge_points else "（教师未特别指定）"
        type_map = {
            "choice": "选择题",
            "blank": "填空题",
            "short": "简答题",
        }
        type_labels = [type_map.get(t, t) for t in payload.types] or ["选择题", "填空题", "简答题"]

        prompt = f"""
你是一名资深教学测评专家，需要根据教师提供的参数，设计一批严谨、可直接用于课堂或线上练习的题目。请严格遵守以下约束：

【出题范围】
- 知识点：{kp_text}（若为“（教师未特别指定）”则你需自行选取与课程主题强相关的典型知识点）
- 允许的题目类型（非常重要）：{ "、".join(type_labels) }
- 目标题量：约 {payload.count} 道题
- 整体难度定位：{diff_cn}（对应 low=低、medium=中、high=高）

【题型规则】
1. 只允许生成上面列出的题型，严禁出现其它类型。若只允许 1 种题型，则所有题目必须完全一致。
2. 各题型的格式要求：
   - 选择题：必须给出 4 个选项 A/B/C/D，选项文字不能过短，每个选项应互斥；`answer` 中只写正确选项字母；`analysis` 用 2~4 句话说明解题思路或易错点。
   - 填空题：题干中用“____”表示空格，如有多个空需编号；`answer` 需按顺序给出所有空的标准答案；`analysis` 说明考察点与参考理由。
   - 简答题：题干一般以“请简要说明/分析/比较…”开头；`answer` 用 3~5 句话给出要点；`analysis` 补充评分要点或拓展思考。
3. 每道题必须注明 `difficulty`，只能写“低/中/高”之一，可根据题目实际情况微调，但整体分布需契合 {diff_cn}。

【内容质量要求】
1. 题干需自洽完整，不能引用“上文/下文”之类的上下文。
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
      "options": ["A. …", "B. …", "C. …", "D. …"],   // 仅选择题必填，其它题型设为 null
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

        raw = rag_system._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]

        import json
        import re

        # 移除思考过程标签
        def remove_thinking_tags(text: str) -> str:
            """移除各种思考过程标签"""
            patterns = [
                r'<think>.*?</think>',
                r'<thinking>.*?</thinking>',
                r'<thought>.*?</thought>',
            ]
            cleaned = text
            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            return cleaned.strip()

        # 清理思考过程
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
                data = json.loads(cleaned)
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"模型返回内容解析失败，请稍后重试: {exc}",
                )

        questions_raw = data.get("questions")
        if not isinstance(questions_raw, list):
            raise HTTPException(
                status_code=500,
                detail="模型返回数据结构不符合预期（缺少 questions 数组）",
            )

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
            raise HTTPException(
                status_code=500,
                detail="模型未返回有效题目，请稍后重试",
            )

        return QuestionGenerateResponse(questions=items)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成题目失败: {exc}") from exc

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查：返回 RAG 向量库状态"""
    rag_system = get_rag_system()
    stats = rag_system.get_stats()
    kb_ready = stats.get("document_count", 0) > 0
    return HealthResponse(
        status="ok",
        message="服务运行正常",
        knowledge_base_ready=kb_ready,
        document_count=stats.get("document_count", 0),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """聊天接口：支持RAG模式和自由对话模式"""
    try:
        conversation_id = request.conversation_id or f"conv_{datetime.now().timestamp()}"
        # 确保对话存在，并使用首条提问自动生成标题
        conversation_storage.ensure_conversation(conversation_id, request.question)

        # 获取近期对话历史用于上下文
        history_for_context = conversation_storage.get_messages(
            conversation_id, limit=Config.CHAT_HISTORY_WINDOW * 2
        )

        model_config = Config.get_llm_model(request.model_id or Config.DEFAULT_LLM_MODEL_ID)
        rag_system = get_rag_system()
        
        # 根据use_rag参数决定是否使用RAG检索
        use_rag = request.use_rag if request.use_rag is not None else True
        
        result = rag_system.query(
            request.question,
            top_k=request.top_k,
            conversation_history=history_for_context,
            llm_config=model_config,
            use_rag=use_rag,  # 传递RAG开关参数
            selected_doc_ids=request.selected_doc_ids,  # 传递选中的文档列表
            owner=current_user.get("username"),  # 传递用户信息，确保只检索该用户的文档
        )

        sources = []
        for idx, source in enumerate(result.get("sources", []), start=1):
            sources.append(
                {
                    "index": str(idx),
                    "source": str(source.get("source", "unknown")),  # 文档名称
                    "source_path": source.get("source_path", ""),  # 文档路径（用于高亮定位）
                    "page": str(source.get("page", "N/A")),
                    "content": source.get("content", "")[:500],
                }
            )

        # 保存本轮对话消息
        conversation_storage.append_message(
            conversation_id,
            role="user",
            content=request.question,
            timestamp=datetime.now().isoformat(),
        )
        conversation_storage.append_message(
            conversation_id,
            role="assistant",
            content=result.get("answer", ""),
            sources=result.get("sources"),
            timestamp=datetime.now().isoformat(),
        )

        conversation_meta = conversation_storage.get_conversation(conversation_id)

        return ChatResponse(
            answer=result.get("answer", ""),
            conversation_id=conversation_id,
            sources=sources,
            title=conversation_meta.get("title"),
            model_id=model_config.get("id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {exc}") from exc


@app.get("/conversations/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    try:
        return conversation_storage.get_conversation(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conversation_storage.delete_conversation(conversation_id)
    return {"message": "对话历史已删除"}


@app.post("/conversations/{conversation_id}/truncate")
async def truncate_conversation(conversation_id: str, keep_count: int):
    """截断对话，只保留前 keep_count 条消息（用于重发功能）"""
    try:
        conversation_storage.truncate_messages(conversation_id, keep_count)
        return {"message": f"对话已截断，保留前 {keep_count} 条消息"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"截断对话失败: {exc}") from exc


@app.delete("/conversations/{conversation_id}/messages/{message_index}")
async def delete_message_pair(conversation_id: str, message_index: int):
    """删除指定索引的消息对"""
    try:
        conversation_storage.delete_message_pair(conversation_id, message_index)
        return {"message": "消息已删除"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除消息失败: {exc}") from exc


@app.get("/conversations")
async def list_conversations():
    return conversation_storage.list_conversations()


@app.get("/models", response_model=List[ModelInfo])
async def list_models():
    return Config.get_public_llm_models()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
