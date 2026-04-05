                                                                                                                                                   
                                                                                                                                                                                         
  ---                                                                                                                                                                                      # PLAN.md — Edu_AI 系统架构升级设计文档
                                                                                                                                                                                         
  > 版本：v1.0 | 日期：2026-03-26 | 状态：设计稿（待实施）

  ---

  ## 一、项目现状概述

  ### 1.1 已完成模块

  | 模块 | 状态 | 入口 | 说明 |
  |------|------|------|------|
  | 对话 Agent（ChatAgent） | ✅ 已上线 | supervisor -> chat_agent 子图 | 支持 tool_calls 循环、RAG/视频检索 |
  | 报告生成 Agent（ReportAgent） | ✅ 已上线 | supervisor -> report_agent 子图 | 5 节点子图 + universal_report_engine（Plan-Execute-Analyze） |
  | 研究 Agent（ResearchAgent） | ✅ 已上线 | supervisor -> research_agent 子图 | 单节点，直接调用工具 |
  | 博客生成 Agent（BlogAgent） | ✅ 已上线 | 独立 LangGraph 工作流 | 两阶段 HITL（章节审查 + 大纲审查） |
  | RAG 检索工具 | ✅ 已上线 | rag_search_tool | ChromaDB + Gemini embedding-2 + BM25 混合检索 |
  | Web 搜索工具 | ✅ 已上线 | web_search_tool（deep_research_tool） | 依赖外部 EduAgent 模块做搜索+爬取 |
  | 用户画像存储 | ⚠️ 基础框架 | user_profile_storage | freeform dict，无固定 schema |
  | 对话记忆 | ⚠️ 基础框架 | conversation_storage | JSON 文件持久化，仅当前会话上下文 |

  ---
  以下是 1.2 和 1.3 部分：

  ---
  ### 1.2 当前架构（LangGraph 主图）

  用户输入
      │
      ▼
  ┌──────────┐   intent_category    ┌────────────┐
  │ supervisor│ ──── "chat" ──────▶ │ chat_agent  │ ──▶ END
  │ (路由器)  │ ──── "generate" ──▶ │report_agent │ ──▶ END
  │          │ ──── "research" ──▶ │research_agent│ ──▶ END
  └──────────┘                      └────────────┘

  ### 1.3 核心痛点

  1. **路由粗粒度**：intent_router 只分 3 类（chat/generate_content/research），无法区分"生成报告"还是"生成教案"
  2. **搜索工具靠用户指令触发**：agent 不能自主判断何时调 RAG、何时调 Web
  3. **槽位体系单一**：chat 有 3 个槽位、report 有 6 个槽位，其他资源类型无槽位定义
  4. **生成模块不可扩展**：report_agent 是硬编码子图，新增资源类型需要重写
  5. **记忆系统薄弱**：无长期记忆，无用户画像 schema，无跨会话偏好学习

  ---

  ## 二、目标架构设计

  ### 2.1 总体架构图

  用户输入
      │
      ▼
  ┌─────────────────────────────────────────────────┐
  │              Intent Router（两步路由）              │
  │                                                   │
  │  Step 1: 一级分类                                  │
  │  ┌─────────────────────────────────────────────┐  │
  │  │ chat | generate | research                   │  │
  │  └──────────────┬──────────────────────────────┘  │
  │                 │ (if generate)                     │
  │  Step 2: 二级分类（资源类型识别）                    │
  │  ┌─────────────────────────────────────────────┐  │
  │  │ report | lesson_plan | quiz | flashcard     │  │
  │  │ | blog | ppt | video | podcast              │  │
  │  └─────────────────────────────────────────────┘  │
  └─────────────────────┬───────────────────────────┘
                        │
          ┌─────────────┼──────────────┐
          ▼             ▼              ▼
     ChatAgent    TextGenEngine   MultimodalEngine
     (对话)     (文本类统一引擎)   (多模态引擎)
                      │                  │
                ┌─────┴─────┐      ┌────┴────┐
                ▼           ▼      ▼         ▼
            report      lesson   ppt      video
            quiz        plan     podcast
            flashcard   blog

  ### 2.2 模块分组

  | 引擎 | 资源类型 | 共性 |
  |------|---------|------|
  | TextGenEngine（文本统一引擎） | 报告、教案、习题、闪卡、教学博客 | 纯文本/Markdown 输出，可共享 plan-execute 框架 |
  | MultimodalEngine（多模态引擎） | PPT、视频、播客 | 需要模板/素材编排/多媒体处理，各自独立子图 |

  ---

  ## 三、重点设计方案

  ### 3.1 重点一：两步意图路由

  #### 3.1.1 一级路由（不变）

  保持现有 3 分类：`chat` / `generate` / `research`


  3.1.2 二级路由（新增）

  当一级路由结果为 generate 时，触发二级路由，精准识别资源类型。

  # 新增文件：app/chat/resource_type_router.py

  RESOURCE_TYPES = [
      "report",        # 报告/研报
      "lesson_plan",   # 教案/教学设计
      "quiz",          # 习题/试题/测验
      "flashcard",     # 闪卡/记忆卡片
      "blog",          # 教学博客/文章
      "ppt",           # PPT/课件/幻灯片
      "video",         # 视频/微课脚本
      "podcast",       # 播客/音频脚本
  ]

  RESOURCE_TYPE_ROUTER_PROMPT = """你是资源类型分类器。用户已明确要求生成教学内容。
  请判断用户想要生成哪种类型的资源。

  合法类型：
  - report：报告、研报、分析文档
  - lesson_plan：教案、教学设计、课程安排
  - quiz：习题、试题、测验、练习
  - flashcard：闪卡、记忆卡片、知识点卡
  - blog：教学博客、教学文章
  - ppt：PPT、课件、幻灯片
  - video：视频脚本、微课设计
  - podcast：播客脚本、音频内容

  仅输出 JSON：{"resource_type": "..."}
  """

  路由决策链：
  supervisor_node:
    1. intent = intent_router.classify(question)  # chat/generate/research
    2. if intent == "generate":
         resource_type = resource_type_router.classify(question)  # report/lesson_plan/...
         state["resource_type"] = resource_type
         if resource_type in TEXT_TYPES:
             state["response_type"] = "text_generate"
         else:
             state["response_type"] = "multimodal_generate"
    3. route to corresponding engine

  3.1.3 关键词兜底

  RESOURCE_TYPE_KEYWORDS = {
      "report":      ["报告", "研报", "分析报告", "调研"],
      "lesson_plan": ["教案", "教学设计", "课程设计", "授课计划"],
      "quiz":        ["习题", "试题", "测验", "练习题", "考题", "出题"],
      "flashcard":   ["闪卡", "记忆卡", "卡片", "知识点卡"],
      "blog":        ["博客", "文章", "教学文章"],
      "ppt":         ["ppt", "课件", "幻灯片", "演示文稿", "slides"],
      "video":       ["视频", "微课", "录课", "视频脚本"],
      "podcast":     ["播客", "音频", "podcast"],
  }

  ---
  3.2 重点二：RAG / Web 搜索自主决策

  3.2.1 现状问题

  当前搜索工具基本靠用户语义关键词触发（"帮我查找知识库""上网上查找"），agent 无法自主判断何时调用。

  3.2.2 设计方案：工具描述增强 + 上下文注入

  核心思路：不改变 LLM 自主调用 tool_calls 的机制（方案 a），但通过增强 tool description 和系统提示词，让 LLM 有足够的决策依据。

  Step 1：增强工具描述

  RAG_TOOL_DESCRIPTION = """本地知识库检索工具。
  调用时机（你必须主动判断，不要等用户明确要求）：
  - 用户提问涉及课程知识点、概念定义、教材内容时
  - 生成教学资源前，需要获取该知识点的权威定义和结构
  - 用户问题包含具体术语/概念名称，知识库可能有对应文档
  - 当你对某个知识点不够确定时，先查知识库再回答

  不应调用的场景：
  - 纯闲聊/问候
  - 用户明确要求搜索最新信息/网络内容
  - 知识库已查过且结果充分
  """

  WEB_SEARCH_TOOL_DESCRIPTION = """全网深度搜索工具。
  调用时机（你必须主动判断，不要等用户明确要求）：
  - 知识库检索结果不足或为空，需要补充外部资料
  - 用户需要最新信息（最新研究、最新政策、时事）
  - 知识库中未覆盖的跨学科或前沿内容
  - 生成资源时发现某个章节/知识点的资料不够深入

  不应调用的场景：
  - 知识库已有充分、准确的内容
  - 简单概念解释（知识库已覆盖）
  - 用户明确只想用本地资料
  """

  Step 2：上下文信号注入

  在每次 LLM 调用前，向系统提示注入 RAG 可用性信号：

  def _build_search_context_hint(state: GraphState) -> str:
      hints = []
      if state.get("selected_doc_ids"):
          hints.append(f"当前知识库已关联 {len(state['selected_doc_ids'])} 篇文档，可通过 rag_search_tool 检索")
      else:
          hints.append("当前知识库无关联文档，如需资料请使用 web_search_tool")

      if state.get("course_id"):
          hints.append(f"当前课程: {state['course_id']}，知识库可能包含该课程的教材和笔记")

      if state.get("deepsearch_done"):
          hints.append("本轮已执行过 web 搜索，优先使用已有结果")

      return "\n".join(hints)

  Step 3：生成阶段的搜索能力

  在 TextGenEngine 的 executor 节点中，允许 planner 规划搜索步骤：

  planner 可规划的步骤序列示例：
  1. rag_search_tool(query="红黑树插入操作") → 获取知识库资料
  2. web_search_tool(query="红黑树 最新教学方法") → 补充外部资料（如 RAG 结果不足）
  3. submit_outline_for_review(outline) → 提交大纲
  4. generate_long_report_content(slots, outline) → 生成正文

  3.2.3 降级策略

  搜索降级链：
  RAG 检索 → 结果充分? → 是 → 使用 RAG 结果
                        → 否 → Web 搜索 → 成功? → 是 → 合并结果
                                                 → 否 → 仅用已有上下文 + 提示用户资料有限

  对 EduAgent 外部模块的降级：
  - 设置 Web 搜索超时（默认 30s）
  - 超时或异常时，返回 ok=False 并在 planner 中触发 replanning
  - 最终降级为仅使用 RAG 结果 + LLM 自身知识

  ---
  3.3 重点三：槽位设计与对话收集工作流

  3.3.1 设计原则

  - 每种资源类型有独立的槽位定义（Pydantic model）
  - 所有类型共享一套基础字段（topic、audience、objective）
  - 各类型扩展专有字段
  - 槽位分为核心槽位（必填，逐个追问）和次要槽位（可选，批量追问或使用默认值）

  3.3.2 槽位定义总表

  # 新增文件：app/chat/slot_definitions.py

  from pydantic import BaseModel, Field
  from typing import Optional, List

  # ═══════════════════════════════════════════
  #  基础槽位（所有资源类型共享）
  # ═══════════════════════════════════════════

  class BaseSlots(BaseModel):
      """所有资源类型共享的基础槽位"""
      topic: Optional[str] = Field(None, description="主题/知识点")
      audience: Optional[str] = Field(None, description="目标受众/年级")
      objective: Optional[str] = Field(None, description="教学目标")

  # ═══════════════════════════════════════════
  #  报告槽位
  # ═══════════════════════════════════════════

  class ReportSlots(BaseSlots):
      """报告生成槽位"""
      focus_area: Optional[str] = Field(None, description="聚焦方向/切入角度")
      length_requirement: Optional[str] = Field(None, description="篇幅要求（如3-4章）")
      depth_level: Optional[str] = Field(None, description="深度级别（如标准研报级）")
      format_style: Optional[str] = Field(None, description="文风/格式风格")
      dynamic_constraints: Optional[str] = Field(None, description="动态约束")

      class SlotMeta:
          core_slots = ["topic", "focus_area"]          # 核心：逐个追问
          secondary_slots = ["length_requirement", "depth_level", "format_style"]  # 次要：批量追问
          defaults = {
              "length_requirement": "常规长度（约3-4章）",
              "depth_level": "标准研报级（逻辑严密、可读）",
              "format_style": "结构化分块论述",
          }

  # ═══════════════════════════════════════════
  #  教案槽位
  # ═══════════════════════════════════════════

  class LessonPlanSlots(BaseSlots):
      """教案生成槽位"""
      duration: Optional[str] = Field(None, description="课时时长（如45分钟、2课时）")
      teaching_method: Optional[str] = Field(None, description="教学方法（如讲授法、探究式、翻转课堂）")
      key_points: Optional[str] = Field(None, description="重点/难点")
      assessment_method: Optional[str] = Field(None, description="评价方式")

      class SlotMeta:
          core_slots = ["topic", "objective"]
          secondary_slots = ["audience", "duration", "teaching_method", "key_points"]
          defaults = {
              "duration": "45分钟（1课时）",
              "teaching_method": "讲授+互动",
          }

  # ═══════════════════════════════════════════
  #  习题槽位
  # ═══════════════════════════════════════════

  class QuizSlots(BaseSlots):
      """习题生成槽位"""
      difficulty: Optional[str] = Field(None, description="难度级别（基础/中等/进阶）")
      question_count: Optional[str] = Field(None, description="题目数量")
      question_types: Optional[str] = Field(None, description="题型（选择/填空/简答/综合）")
      include_answers: Optional[str] = Field(None, description="是否附带答案和解析")

      class SlotMeta:
          core_slots = ["topic", "difficulty"]
          secondary_slots = ["audience", "question_count", "question_types", "include_answers"]
          defaults = {
              "question_count": "10题",
              "question_types": "选择题+简答题混合",
              "include_answers": "附带答案和详细解析",
          }

  # ═══════════════════════════════════════════
  #  闪卡槽位
  # ═══════════════════════════════════════════

  class FlashcardSlots(BaseSlots):
      """闪卡生成槽位"""
      card_count: Optional[str] = Field(None, description="卡片数量")
      card_style: Optional[str] = Field(None, description="卡片风格（概念/公式/对比/案例）")

      class SlotMeta:
          core_slots = ["topic"]
          secondary_slots = ["audience", "card_count", "card_style"]
          defaults = {
              "card_count": "15张",
              "card_style": "概念+关键公式",
          }

  # ═══════════════════════════════════════════
  #  教学博客槽位
  # ═══════════════════════════════════════════

  class BlogSlots(BaseSlots):
      """教学博客生成槽位"""
      blog_length: Optional[str] = Field(None, description="篇幅（短文/中篇/长文）")
      writing_tone: Optional[str] = Field(None, description="语气风格（学术/通俗/故事化）")
      include_tables: Optional[str] = Field(None, description="是否包含表格")

      class SlotMeta:
          core_slots = ["topic", "objective"]
          secondary_slots = ["audience", "blog_length", "writing_tone"]
          defaults = {
              "blog_length": "中篇（2000-3000字）",
              "writing_tone": "通俗易懂",
              "include_tables": "根据内容自动判断",
          }

  # ═══════════════════════════════════════════
  #  PPT 槽位（多模态引擎）
  # ═══════════════════════════════════════════

  class PPTSlots(BaseSlots):
      """PPT 生成槽位"""
      slide_count: Optional[str] = Field(None, description="幻灯片页数")
      template_style: Optional[str] = Field(None, description="模板风格（简约/学术/活泼）")
      include_notes: Optional[str] = Field(None, description="是否包含演讲备注")
      visual_preference: Optional[str] = Field(None, description="视觉偏好（多图/多表/纯文字）")

      class SlotMeta:
          core_slots = ["topic", "objective"]
          secondary_slots = ["audience", "slide_count", "template_style", "visual_preference"]
          defaults = {
              "slide_count": "15-20页",
              "template_style": "简约学术",
              "include_notes": "包含演讲备注",
          }

  # ═══════════════════════════════════════════
  #  视频脚本槽位（多模态引擎）
  # ═══════════════════════════════════════════

  class VideoSlots(BaseSlots):
      """视频脚本生成槽位"""
      video_duration: Optional[str] = Field(None, description="视频时长")
      video_type: Optional[str] = Field(None, description="视频类型（微课/实验演示/知识讲解）")
      narration_style: Optional[str] = Field(None, description="解说风格")

      class SlotMeta:
          core_slots = ["topic", "video_type"]
          secondary_slots = ["audience", "video_duration", "narration_style"]
          defaults = {
              "video_duration": "10-15分钟",
              "video_type": "知识讲解微课",
              "narration_style": "清晰专业",
          }

  # ═══════════════════════════════════════════
  #  播客脚本槽位（多模态引擎）
  # ═══════════════════════════════════════════

  class PodcastSlots(BaseSlots):
      """播客脚本生成槽位"""
      podcast_duration: Optional[str] = Field(None, description="播客时长")
      podcast_format: Optional[str] = Field(None, description="形式（独白/对谈/访谈）")
      tone: Optional[str] = Field(None, description="语气风格（轻松/严谨/故事化）")

      class SlotMeta:
          core_slots = ["topic", "podcast_format"]
          secondary_slots = ["audience", "podcast_duration", "tone"]
          defaults = {
              "podcast_duration": "15-20分钟",
              "podcast_format": "独白讲解",
              "tone": "轻松专业",
          }

  # ═══════════════════════════════════════════
  #  注册表
  # ═══════════════════════════════════════════

  SLOT_REGISTRY = {
      "report": ReportSlots,
      "lesson_plan": LessonPlanSlots,
      "quiz": QuizSlots,
      "flashcard": FlashcardSlots,
      "blog": BlogSlots,
      "ppt": PPTSlots,
      "video": VideoSlots,
      "podcast": PodcastSlots,
  }

  3.3.3 对话收集策略：分级追问

  ┌─────────────────────────────────────────────────────┐
  │                 槽位收集状态机                         │
  │                                                       │
  │  用户首条消息                                          │
  │      │                                                │
  │      ▼                                                │
  │  ┌─────────┐                                          │
  │  │ 提取槽位 │ ← LLM 结构化输出 + 启发式规则            │
  │  └────┬────┘                                          │
  │       │                                                │
  │       ▼                                                │
  │  核心槽位是否完整？                                     │
  │       │                                                │
  │    否 │         是                                      │
  │       ▼          ▼                                     │
  │  ┌──────────┐  次要槽位是否完整？                       │
  │  │ 逐个追问  │      │                                   │
  │  │ 核心槽位  │   否  │       是                          │
  │  │（一次一个）│      ▼        ▼                          │
  │  └──────────┘  ┌──────────┐ ┌────────┐                │
  │                │ 批量追问  │ │ 进入生成 │                │
  │                │次要槽位   │ │  流程    │                │
  │                │或使用默认值│ └────────┘                 │
  │                └──────────┘                             │
  └─────────────────────────────────────────────────────┘

  追问规则：

  class SlotCollector:
      """统一槽位收集器"""

      def get_next_question(self, resource_type: str, current_slots: dict) -> Optional[dict]:
          slot_class = SLOT_REGISTRY[resource_type]
          meta = slot_class.SlotMeta

          # Phase 1: 核心槽位 — 一次问一个
          for slot_key in meta.core_slots:
              if not current_slots.get(slot_key):
                  return {
                      "mode": "single",        # 单个追问
                      "slot_key": slot_key,
                      "question": self._build_question(resource_type, slot_key),
                  }

          # Phase 2: 次要槽位 — 批量追问（一次问 2-3 个）
          missing_secondary = [k for k in meta.secondary_slots if not current_slots.get(k)]
          if missing_secondary:
              return {
                  "mode": "batch",             # 批量追问
                  "slot_keys": missing_secondary[:3],
                  "question": self._build_batch_question(resource_type, missing_secondary[:3]),
                  "can_skip": True,            # 用户可跳过，使用默认值
              }

          # 全部就绪
          return None

  追问话术示例（报告类型）：

  ┌──────────────┬────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │     阶段     │        槽位        │                                               追问话术                                                │
  ├──────────────┼────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 核心-1       │ topic              │ "好的，你想围绕哪个主题来写这份报告？"                                                                │
  ├──────────────┼────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 核心-2       │ focus_area         │ "'{topic}'这个主题很好。你想重点从哪个角度切入？比如原理分析、应用对比、还是发展趋势？"               │
  ├──────────────┼────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 次要（批量） │ length/depth/style │ "我默认按 3-4 章、标准研报级、结构化论述来写。你有特别的篇幅、深度或风格偏好吗？没有的话我直接开始。" │
  └──────────────┴────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────┘

  追问话术示例（习题类型）：

  ┌──────────────┬─────────────────────┬─────────────────────────────────────────────────────────────────────────────┐
  │     阶段     │        槽位         │                                  追问话术                                   │
  ├──────────────┼─────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
  │ 核心-1       │ topic               │ "你想出哪个知识点的习题？"                                                  │
  ├──────────────┼─────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
  │ 核心-2       │ difficulty          │ "明白了。这套题的难度定在什么级别？基础巩固、中等提升、还是进阶挑战？"      │
  ├──────────────┼─────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
  │ 次要（批量） │ count/types/answers │ "我默认出 10 题，选择+简答混合，附带解析。需要调整数量、题型或其他要求吗？" │
  └──────────────┴─────────────────────┴─────────────────────────────────────────────────────────────────────────────┘

  3.3.4 用户"不耐烦"检测

  保留并扩展现有的 REPORT_IMPATIENT_KEYWORDS 机制，适用于所有资源类型：

  IMPATIENT_KEYWORDS = ["直接生成", "别问了", "不用问", "快点", "够了", "行了", "默认就好"]

  def check_impatient(user_input: str, current_slots: dict, resource_type: str) -> bool:
      """检测用户是否不耐烦，如果是则用默认值填充所有未填槽位"""
      if any(kw in user_input for kw in IMPATIENT_KEYWORDS):
          meta = SLOT_REGISTRY[resource_type].SlotMeta
          for key, default in meta.defaults.items():
              if not current_slots.get(key):
                  current_slots[key] = default
          return True
      return False

  ---
  四、TextGenEngine（文本统一生成引擎）

  4.1 设计思路

  基于现有 universal_report_engine 的 Plan-Execute-Analyze 框架，将其泛化为支持所有文本类资源的统一引擎。每种资源类型注册自己的 Planner 插件 和 Executor 插件。

  4.2 引擎架构

  ┌─────────────────────────────────────────────────────────────┐
  │                  TextGenEngine (LangGraph)                    │
  │                                                               │
  │  ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌────────┐│
  │  │ slot_     │───▶│ planner   │───▶│ validator │───▶│executor││
  │  │ collector │    │           │    │          │    │        ││
  │  └──────────┘    └───────────┘    └──────────┘    └───┬────┘│
  │       ▲                ▲                               │     │
  │       │                │                               ▼     │
  │       │                │                         ┌──────────┐│
  │       │                └─────── replanning ◀─────│ analyzer ││
  │       │                                          └──────────┘│
  │       │                                               │      │
  │       └──────── awaiting_human ◀──────────────────────┘      │
  │                                                               │
  │  ┌─────────────────────────────────────────────────────────┐ │
  │  │              Plugin Registry（插件注册表）                 │ │
  │  │                                                           │ │
  │  │  report_plugin:      ReportPlanner + ReportExecutor       │ │
  │  │  lesson_plan_plugin: LessonPlanPlanner + LessonPlanExec   │ │
  │  │  quiz_plugin:        QuizPlanner + QuizExecutor           │ │
  │  │  flashcard_plugin:   FlashcardPlanner + FlashcardExec     │ │
  │  │  blog_plugin:        BlogPlanner + BlogExecutor           │ │
  │  └─────────────────────────────────────────────────────────┘ │
  └─────────────────────────────────────────────────────────────┘

  4.3 插件接口

  # 新增文件：app/chat/engines/plugin_base.py

  from abc import ABC, abstractmethod
  from typing import Any, Dict, List, Optional

  class GenPlugin(ABC):
      """文本生成插件基类"""

      @property
      @abstractmethod
      def resource_type(self) -> str:
          """返回资源类型标识，如 'report', 'lesson_plan'"""
          ...

      @property
      @abstractmethod
      def slot_class(self):
          """返回对应的槽位 Pydantic 类"""
          ...

      @abstractmethod
      def needs_outline_review(self) -> bool:
          """是否需要大纲确认环节"""
          ...

      @abstractmethod
      def build_outline(self, slots: Dict[str, str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
          """根据槽位生成大纲/结构"""
          ...

      @abstractmethod
      def generate_content(self, slots: Dict[str, str], outline: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
          """根据槽位+大纲生成最终内容"""
          ...

      def post_process(self, content: str) -> str:
          """可选：后处理（格式化、模板渲染等）"""
          return content

  4.4 各资源类型的插件实现概要

  ┌─────────────┬──────────────────────┬────────────────────────────┬─────────────────────────────────────────────────┐
  │  资源类型   │ needs_outline_review │          生成流程          │                  预计输出格式                   │
  ├─────────────┼──────────────────────┼────────────────────────────┼─────────────────────────────────────────────────┤
  │ report      │ ✅ 是                │ 大纲确认 → 逐章生成 → 合并 │ Markdown 长文                                   │
  ├─────────────┼──────────────────────┼────────────────────────────┼─────────────────────────────────────────────────┤
  │ lesson_plan │ ✅ 是                │ 教案框架确认 → 各环节展开  │ 结构化 Markdown（教学目标/导入/新授/练习/小结） │
  ├─────────────┼──────────────────────┼────────────────────────────┼─────────────────────────────────────────────────┤
  │ quiz        │ ❌ 否                │ 提取知识点 → 批量生成题目  │ JSON + Markdown（题目+答案）                    │
  ├─────────────┼──────────────────────┼────────────────────────────┼─────────────────────────────────────────────────┤
  │ flashcard   │ ❌ 否                │ 提取知识点 → 批量生成卡片  │ JSON 数组（front/back）                         │
  ├─────────────┼──────────────────────┼────────────────────────────┼─────────────────────────────────────────────────┤
  │ blog        │ ✅ 是                │ 大纲确认 → 段落生成 → 合并 │ Markdown 文章                                   │
  └─────────────┴──────────────────────┴────────────────────────────┴─────────────────────────────────────────────────┘

  4.5 统一引擎工作流状态机

                     ┌──────────────────────────────────┐
                     │                                    │
                     ▼                                    │
                ┌─────────┐                               │
                │collecting│ ← 槽位收集阶段                │
                └────┬────┘                               │
                     │ 槽位完整                             │
                     ▼                                    │
                ┌─────────┐     需要大纲确认?               │
                │ planning │ ──── 是 ──▶ 生成大纲           │
                └────┬────┘           ──▶ 提交用户审查      │
                     │ 否                    │              │
                     │              用户确认 ◀─── 用户修改 ──┘
                     ▼                    │
                ┌──────────┐              │
                │ executing │ ◀───────────┘
                └─────┬────┘
                      │
                      ▼
                ┌──────────┐
                │ reviewing │ ← analyzer 审查质量
                └─────┬────┘
                      │
              ┌───────┼──────────┐
              ▼       ▼          ▼
           finished  replanning  awaiting_human

  4.6 与现有代码的迁移路径

  1. 保留 universal_report_engine.py 中的 Plan-Execute-Analyze 核心循环
  2. 重构 ReportState 为泛化的 TextGenState，增加 resource_type 字段
  3. 抽取 现有 report 逻辑为 ReportPlugin
  4. 逐步新增 LessonPlanPlugin、QuizPlugin 等
  5. 废弃 service_core.py（与 service.py 重复的旧版本）
  6. 迁移 blog_agent/ 的博客生成逻辑到 BlogPlugin

  ---
  五、MultimodalEngine（多模态引擎）

  5.1 PPT 引擎

  PPT 生成流程：
  1. 槽位收集（PPTSlots）
  2. 大纲生成（幻灯片结构：标题页/目录/各节/总结）
  3. 用户确认大纲
  4. 逐页内容生成（标题 + 要点 + 演讲备注）
  5. 模板渲染（python-pptx 或 reveal.js）
  6. 输出文件

  5.2 视频脚本引擎

  视频生成流程：
  1. 槽位收集（VideoSlots）
  2. 脚本大纲生成（分镜/段落结构）
  3. 用户确认大纲
  4. 逐段脚本生成（旁白 + 画面描述 + 时间轴）
  5. 输出脚本文档

  5.3 播客脚本引擎

  播客生成流程：
  1. 槽位收集（PodcastSlots）
  2. 节目大纲生成（开场/主题段/互动/结尾）
  3. 用户确认大纲
  4. 逐段脚本生成（口语化文本 + 音效提示）
  5. 输出脚本文档

  ▎ 多模态引擎的各子引擎保持独立 LangGraph 子图，因为它们的节点逻辑和输出格式差异较大，不适合硬塞进文本统一引擎。

  ---
  六、记忆系统设计

  6.1 架构概览

  ┌──────────────────────────────────────────────────────┐
  │                   Memory System                        │
  │                                                        │
  │  ┌─────────────────┐     ┌──────────────────────────┐ │
  │  │ 短期记忆          │     │ 长期记忆                   │ │
  │  │ (Short-term)     │     │ (Long-term)               │ │
  │  │                  │     │                            │ │
  │  │ • 当前会话上下文   │     │ • 结构化存储（JSON）        │ │
  │  │ • 多轮对话历史     │     │   - 用户画像               │ │
  │  │ • 当前槽位状态     │     │   - 生成记录摘要           │ │
  │  │ • 工具调用结果     │     │   - 偏好设置               │ │
  │  │                  │     │                            │ │
  │  │ 存储：GraphState  │     │ • 向量化存储（ChromaDB）    │ │
  │  │ + conv_storage   │     │   - 历史对话摘要向量        │ │
  │  │                  │     │   - 生成内容摘要向量        │ │
  │  │                  │     │   - 用于语义检索相关记忆     │ │
  │  └─────────────────┘     └──────────────────────────┘ │
  │                                                        │
  │  ┌──────────────────────────────────────────────────┐ │
  │  │ 记忆管理器 (MemoryManager)                         │ │
  │  │                                                    │ │
  │  │ • write_memory(user_id, type, content)             │ │
  │  │ • recall_memory(user_id, query, top_k)             │ │
  │  │ • summarize_and_compress(user_id)                  │ │
  │  │ • update_user_profile(user_id, patch)              │ │
  │  └──────────────────────────────────────────────────┘ │
  └──────────────────────────────────────────────────────┘

  6.2 用户画像 Schema

  # 重构文件：core/user_profile_storage.py

  from pydantic import BaseModel, Field
  from typing import Optional, List, Dict
  from datetime import datetime

  class UserProfile(BaseModel):
      """用户画像结构化模型"""
      user_id: str
      created_at: datetime = Field(default_factory=datetime.now)
      updated_at: datetime = Field(default_factory=datetime.now)

      # 基本信息
      subject: Optional[str] = Field(None, description="任教科目")
      grade_level: Optional[str] = Field(None, description="主要面向的年级/受众")
      teaching_experience: Optional[str] = Field(None, description="教龄/经验")

      # 偏好
      preferred_style: Optional[str] = Field(None, description="偏好的内容风格")
      preferred_depth: Optional[str] = Field(None, description="偏好的内容深度")
      preferred_language: str = Field(default="zh-CN", description="语言偏好")

      # 使用统计
      generation_history: List[Dict] = Field(default_factory=list, description="生成记录摘要")
      # 结构: [{"type": "report", "topic": "...", "timestamp": "...", "quality_feedback": "..."}]

      frequent_topics: List[str] = Field(default_factory=list, description="常用主题/知识点")
      total_generations: int = Field(default=0, description="累计生成次数")
      total_conversations: int = Field(default=0, description="累计对话次数")

      # 交互偏好（从行为中学习）
      patience_level: str = Field(default="normal", description="耐心程度 low/normal/high")
      detail_preference: str = Field(default="normal", description="详细程度偏好 brief/normal/detailed")

  6.3 长期记忆向量化

  # 新增文件：app/chat/memory_manager.py

  class MemoryManager:
      """记忆管理器：结构化 + 向量化双存储"""

      def __init__(self, user_id: str):
          self.user_id = user_id
          self.profile_storage = user_profile_storage  # JSON 结构化存储
          self.vector_store = get_memory_vector_store()  # ChromaDB collection: "user_memories"

      def write_memory(self, memory_type: str, content: str, metadata: dict = None):
          """写入一条记忆"""
          # 1. 向量化存储（用于语义检索）
          self.vector_store.add(
              documents=[content],
              metadatas=[{
                  "user_id": self.user_id,
                  "type": memory_type,      # "conversation" | "generation" | "preference"
                  "timestamp": datetime.now().isoformat(),
                  **(metadata or {}),
              }],
              ids=[f"{self.user_id}_{memory_type}_{uuid4().hex[:8]}"],
          )

          # 2. 更新结构化画像
          if memory_type == "generation":
              self._update_generation_history(content, metadata)
          elif memory_type == "preference":
              self._update_preferences(content)

      def recall_memory(self, query: str, top_k: int = 5) -> List[dict]:
          """语义检索相关记忆"""
          results = self.vector_store.query(
              query_texts=[query],
              n_results=top_k,
              where={"user_id": self.user_id},
          )
          return results

      def summarize_and_compress(self):
          """遗忘/压缩机制：将早期记忆压缩为摘要"""
          # 获取所有记忆
          all_memories = self.vector_store.get(where={"user_id": self.user_id})

          # 保留最近 N 条详细记录
          KEEP_RECENT = 50
          if len(all_memories["ids"]) <= KEEP_RECENT:
              return

          # 按时间排序，将老记忆压缩
          sorted_memories = sorted(
              zip(all_memories["ids"], all_memories["documents"], all_memories["metadatas"]),
              key=lambda x: x[2].get("timestamp", ""),
          )

          old_memories = sorted_memories[:-KEEP_RECENT]

          # LLM 生成摘要
          old_texts = [m[1] for m in old_memories]
          summary = self._llm_summarize(old_texts)

          # 删除老记忆，写入摘要
          old_ids = [m[0] for m in old_memories]
          self.vector_store.delete(ids=old_ids)
          self.write_memory("summary", summary, {"compressed_count": len(old_ids)})

  6.4 记忆注入时机

  # 在 ChatService 的 supervisor 节点中注入用户画像和相关记忆

  def _inject_memory_context(self, state: GraphState) -> str:
      """构建记忆上下文注入到系统提示中"""
      user_id = state.get("conv_state", {}).get("user_id")
      if not user_id:
          return ""

      memory_mgr = MemoryManager(user_id)
      profile = memory_mgr.profile_storage.get_profile(user_id)
      related_memories = memory_mgr.recall_memory(state["question"], top_k=3)

      context_parts = []

      # 用户画像
      if profile:
          context_parts.append(f"【用户画像】科目:{profile.get('subject','未知')} "
                             f"受众:{profile.get('grade_level','未知')} "
                             f"风格偏好:{profile.get('preferred_style','无')}")

      # 相关历史
      if related_memories and related_memories.get("documents"):
          context_parts.append("【相关历史】" + " | ".join(related_memories["documents"][:3]))

      return "\n".join(context_parts)

  ---
  七、GraphState 重构

  7.1 问题

  当前 GraphState 有 102 个字段，存在重复声明（need_type、user_role_mode），且报告槽位硬编码在状态中。

  7.2 重构方案

  # 重构后的 graph_state.py

  class GraphState(TypedDict):
      # ─── 核心 ───
      question: str
      conversation_id: str
      model_id: Optional[str]
      gateway: ChatModelGateway
      history: List[Dict[str, Any]]
      conv_state: Dict[str, Any]
      user_profile: Dict[str, Any]

      # ─── 路由 ───
      intent_category: str                  # chat / generate / research
      resource_type: Optional[str]          # report / lesson_plan / quiz / ... (新增)
      response_type: str                    # chat / text_generate / multimodal_generate / research (扩展)

      # ─── 槽位（泛化） ───
      slots: Dict[str, str]                 # 通用槽位容器（取代硬编码的 report_slots）
      slot_meta: Dict[str, Any]             # 槽位元信息（core_slots, secondary_slots, defaults）
      missing_slots: List[str]
      slot_collection_phase: str            # "core" / "secondary" / "done"

      # ─── 生成状态 ───
      outline: List[Dict[str, Any]]         # 统一大纲字段
      outline_confirmed: bool
      generated_content: str                # 统一内容字段
      generation_checkpoint: Dict[str, Any]

      # ─── 工具与搜索 ───
      rag_tool_enabled: bool
      deepsearch_tool_enabled: bool
      search_context_hint: str              # 新增：搜索上下文提示
      video_hits: List[Dict[str, Any]]

      # ─── LLM ───
      llm: Optional[ChatOpenAI]
      llm_deep: Optional[ChatOpenAI]
      vlm: Optional[ChatOpenAI]

      # ─── 输出 ───
      final_answer: str
      final_answer_source: Optional[str]
      messages: List[Any]

      # ─── 记忆 ───
      memory_context: str                   # 新增：注入的记忆上下文

  ---
  八、主图重构

  8.1 新的 LangGraph 主图

  def _build_graph(self) -> CompiledGraph:
      graph = StateGraph(GraphState)

      # 节点
      graph.add_node("supervisor", self._supervisor_node)       # 两步路由
      graph.add_node("chat_agent", self._chat_agent.graph)      # 对话子图
      graph.add_node("research_agent", self._research_agent.graph)  # 研究子图
      graph.add_node("text_gen_engine", self._text_gen_engine.graph) # 文本统一引擎（新）
      graph.add_node("ppt_engine", self._ppt_engine.graph)      # PPT 引擎（新）
      graph.add_node("video_engine", self._video_engine.graph)   # 视频引擎（新）
      graph.add_node("podcast_engine", self._podcast_engine.graph) # 播客引擎（新）

      # 入口
      graph.set_entry_point("supervisor")

      # 路由
      graph.add_conditional_edges(
          "supervisor",
          self._route_after_supervisor,
          {
              "chat": "chat_agent",
              "research": "research_agent",
              "text_generate": "text_gen_engine",
              "ppt": "ppt_engine",
              "video": "video_engine",
              "podcast": "podcast_engine",
          },
      )

      # 终止
      for node in ["chat_agent", "research_agent", "text_gen_engine",
                   "ppt_engine", "video_engine", "podcast_engine"]:
          graph.add_edge(node, END)

      return graph.compile()


  def _route_after_supervisor(self, state: GraphState) -> str:
      rt = state.get("response_type", "chat")
      resource = state.get("resource_type")

      if rt == "chat":
          return "chat"
      if rt == "research":
          return "research"
      if rt in ("text_generate", "generate"):
          if resource in ("ppt",):
              return "ppt"
          if resource in ("video",):
              return "video"
          if resource in ("podcast",):
              return "podcast"
          return "text_generate"   # report/lesson_plan/quiz/flashcard/blog
      return "chat"

  ---
  九、实施路线图

  Phase 1: 基础设施重构（优先级：最高）

  ┌──────────────────────────────────┬──────────────────────────────────────────────────┬─────────────────────────────────────────────┐
  │               任务               │                     涉及文件                     │                    说明                     │
  ├──────────────────────────────────┼──────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ 1.1 新增 resource_type_router.py │ app/chat/resource_type_router.py                 │ 二级路由器                                  │
  ├──────────────────────────────────┼──────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ 1.2 新增 slot_definitions.py     │ app/chat/slot_definitions.py                     │ 所有资源类型的槽位定义                      │
  ├──────────────────────────────────┼──────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ 1.3 重构 GraphState              │ app/chat/graph_state.py                          │ 精简字段，增加 resource_type / slot_meta 等 │
  ├──────────────────────────────────┼──────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ 1.4 重构 supervisor 节点         │ app/chat/agents/supervisor_agent.py + service.py │ 两步路由逻辑                                │
  ├──────────────────────────────────┼──────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ 1.5 废弃 service_core.py         │ app/chat/service_core.py                         │ 与 service.py 合并                          │
  └──────────────────────────────────┴──────────────────────────────────────────────────┴─────────────────────────────────────────────┘

  Phase 2: 文本统一引擎（优先级：高）

  ┌───────────────────────────┬────────────────────────────────────────────────┬───────────────────────────────────┐
  │           任务            │                    涉及文件                    │               说明                │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.1 抽取插件基类          │ app/chat/engines/plugin_base.py                │ GenPlugin ABC                     │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.2 构建 TextGenEngine    │ app/chat/engines/text_gen_engine.py            │ 基于 universal_report_engine 泛化 │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.3 实现 ReportPlugin     │ app/chat/engines/plugins/report_plugin.py      │ 迁移现有 report 逻辑              │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.4 实现 LessonPlanPlugin │ app/chat/engines/plugins/lesson_plan_plugin.py │ 教案生成                          │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.5 实现 QuizPlugin       │ app/chat/engines/plugins/quiz_plugin.py        │ 习题生成                          │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.6 实现 FlashcardPlugin  │ app/chat/engines/plugins/flashcard_plugin.py   │ 闪卡生成                          │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.7 实现 BlogPlugin       │ app/chat/engines/plugins/blog_plugin.py        │ 迁移 blog_agent 逻辑              │
  ├───────────────────────────┼────────────────────────────────────────────────┼───────────────────────────────────┤
  │ 2.8 统一槽位收集器        │ app/chat/engines/slot_collector.py             │ 分级追问逻辑                      │
  └───────────────────────────┴────────────────────────────────────────────────┴───────────────────────────────────┘

  Phase 3: 搜索工具增强（优先级：高）

  ┌──────────────────────┬─────────────────────────────────────┬───────────────────────────┐
  │         任务         │              涉及文件               │           说明            │
  ├──────────────────────┼─────────────────────────────────────┼───────────────────────────┤
  │ 3.1 增强工具描述     │ app/chat/tools/agent_tools.py       │ 详细的调用时机说明        │
  ├──────────────────────┼─────────────────────────────────────┼───────────────────────────┤
  │ 3.2 搜索上下文注入   │ app/chat/service.py 中的节点逻辑    │ build_search_context_hint │
  ├──────────────────────┼─────────────────────────────────────┼───────────────────────────┤
  │ 3.3 降级策略         │ app/chat/tools/agent_tools.py       │ Web 搜索超时+降级         │
  ├──────────────────────┼─────────────────────────────────────┼───────────────────────────┤
  │ 3.4 生成阶段搜索能力 │ app/chat/engines/text_gen_engine.py │ planner 可规划搜索步骤    │
  └──────────────────────┴─────────────────────────────────────┴───────────────────────────┘

  Phase 4: 记忆系统（优先级：中）

  ┌─────────────────────┬────────────────────────────────────┬────────────────────────┐
  │        任务         │              涉及文件              │          说明          │
  ├─────────────────────┼────────────────────────────────────┼────────────────────────┤
  │ 4.1 用户画像 Schema │ core/user_profile_storage.py       │ Pydantic 模型化        │
  ├─────────────────────┼────────────────────────────────────┼────────────────────────┤
  │ 4.2 MemoryManager   │ app/chat/memory_manager.py         │ 双存储架构             │
  ├─────────────────────┼────────────────────────────────────┼────────────────────────┤
  │ 4.3 记忆向量集合    │ ChromaDB collection: user_memories │ 语义检索               │
  ├─────────────────────┼────────────────────────────────────┼────────────────────────┤
  │ 4.4 记忆注入        │ app/chat/service.py                │ supervisor 节点注入    │
  ├─────────────────────┼────────────────────────────────────┼────────────────────────┤
  │ 4.5 遗忘/压缩机制   │ app/chat/memory_manager.py         │ summarize_and_compress │
  ├─────────────────────┼────────────────────────────────────┼────────────────────────┤
  │ 4.6 画像自动更新    │ app/chat/service.py                │ 每次交互后更新         │
  └─────────────────────┴────────────────────────────────────┴────────────────────────┘

  Phase 5: 多模态引擎（优先级：低）

  ┌──────────────────┬────────────────────────────────────┬──────────┐
  │       任务       │              涉及文件              │   说明   │
  ├──────────────────┼────────────────────────────────────┼──────────┤
  │ 5.1 PPT 引擎     │ app/chat/engines/ppt_engine.py     │ 独立子图 │
  ├──────────────────┼────────────────────────────────────┼──────────┤
  │ 5.2 视频脚本引擎 │ app/chat/engines/video_engine.py   │ 独立子图 │
  ├──────────────────┼────────────────────────────────────┼──────────┤
  │ 5.3 播客脚本引擎 │ app/chat/engines/podcast_engine.py │ 独立子图 │
  └──────────────────┴────────────────────────────────────┴──────────┘

  Phase 6: 清理与迁移（优先级：低）

  ┌──────────────────────────────────────┬──────────────────────────────────────────┐
  │                 任务                 │                   说明                   │
  ├──────────────────────────────────────┼──────────────────────────────────────────┤
  │ 6.1 废弃 /teacher/* 路由             │ 所有生成功能统一走 /api/chat + LangGraph │
  ├──────────────────────────────────────┼──────────────────────────────────────────┤
  │ 6.2 废弃独立 blog_agent/             │ 迁移到 BlogPlugin 后删除                 │
  ├──────────────────────────────────────┼──────────────────────────────────────────┤
  │ 6.3 修复 GraphState 重复字段         │ need_type 和 user_role_mode 的重复声明   │
  ├──────────────────────────────────────┼──────────────────────────────────────────┤
  │ 6.4 schemas.py 中 course_id 重复字段 │ ChatRequest 中定义了两次                 │
  └──────────────────────────────────────┴──────────────────────────────────────────┘

  ---
  十、风险与注意事项

  ┌──────────────────────────────────┬──────┬────────────────────────────────────────────┐
  │               风险               │ 影响 │                  缓解措施                  │
  ├──────────────────────────────────┼──────┼────────────────────────────────────────────┤
  │ 统一引擎重构导致 report 功能回退 │ 高   │ 先实现 ReportPlugin 并通过测试，再切换路由 │
  ├──────────────────────────────────┼──────┼────────────────────────────────────────────┤
  │ 二级路由识别准确率               │ 中   │ LLM 分类 + 关键词兜底双保险                │
  ├──────────────────────────────────┼──────┼────────────────────────────────────────────┤
  │ 记忆向量存储增长                 │ 低   │ 压缩机制 + 限制每用户记忆上限              │
  ├──────────────────────────────────┼──────┼────────────────────────────────────────────┤
  │ EduAgent 外部依赖不稳定          │ 中   │ 搜索降级链 + 超时机制                      │
  ├──────────────────────────────────┼──────┼────────────────────────────────────────────┤
  │ GraphState 字段变动影响序列化    │ 高   │ 做好旧会话状态的兼容性迁移                 │
  └──────────────────────────────────┴──────┴────────────────────────────────────────────┘

  ---
  十一、目录结构规划（新增/变更文件）

  app/chat/
  ├── resource_type_router.py          # 新增：二级路由器
  ├── slot_definitions.py              # 新增：统一槽位定义
  ├── memory_manager.py                # 新增：记忆管理器
  ├── graph_state.py                   # 重构：精简字段
  ├── intent_router.py                 # 微调：优化提示词
  ├── engines/                         # 新增目录
  │   ├── __init__.py
  │   ├── plugin_base.py               # 插件基类
  │   ├── text_gen_engine.py           # 文本统一引擎
  │   ├── slot_collector.py            # 统一槽位收集器
  │   └── plugins/
  │       ├── __init__.py
  │       ├── report_plugin.py         # 报告插件
  │       ├── lesson_plan_plugin.py    # 教案插件
  │       ├── quiz_plugin.py           # 习题插件
  │       ├── flashcard_plugin.py      # 闪卡插件
  │       └── blog_plugin.py           # 博客插件
  ├── engines_multimodal/              # 新增目录
  │   ├── __init__.py
  │   ├── ppt_engine.py               # PPT 引擎
  │   ├── video_engine.py             # 视频引擎
  │   └── podcast_engine.py           # 播客引擎
  ├── tools/
  │   ├── agent_tools.py              # 修改：增强工具描述
  │   └── search_tools.py             # 修改：上下文注入
  core/
  ├── user_profile_storage.py          # 重构：Pydantic Schema

  ---
  ▎ 下一步：确认此设计文档后，从 Phase 1 开始逐步实施。每个 Phase 完成后进行集成测试，确保不引入回退。
