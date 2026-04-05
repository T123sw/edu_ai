# Edu_AI 系统架构升级 — 任务清单

> 基于 PLAN.md v1.0 | 创建日期：2026-03-26 | 状态追踪文档

---

## Phase 1: 基础设施重构（优先级：最高）

- [ ] **1.1 新增二级路由器 `resource_type_router.py`**
  - 文件：`app/chat/resource_type_router.py`
  - 内容：
    - 定义 `RESOURCE_TYPES` 列表（report / lesson_plan / quiz / flashcard / blog / ppt / video / podcast）
    - 实现 `RESOURCE_TYPE_ROUTER_PROMPT`（LLM 分类提示词，输出 JSON `{"resource_type": "..."}`）
    - 实现 `RESOURCE_TYPE_KEYWORDS` 关键词兜底映射表
    - 实现 `classify()` 方法：先 LLM 分类，失败时走关键词匹配
  - 依赖：无

- [ ] **1.2 新增统一槽位定义 `slot_definitions.py`**
  - 文件：`app/chat/slot_definitions.py`
  - 内容：
    - `BaseSlots(BaseModel)`：共享基础字段（topic / audience / objective）
    - `ReportSlots(BaseSlots)`：focus_area / length_requirement / depth_level / format_style / dynamic_constraints + SlotMeta
    - `LessonPlanSlots(BaseSlots)`：duration / teaching_method / key_points / assessment_method + SlotMeta
    - `QuizSlots(BaseSlots)`：difficulty / question_count / question_types / include_answers + SlotMeta
    - `FlashcardSlots(BaseSlots)`：card_count / card_style + SlotMeta
    - `BlogSlots(BaseSlots)`：blog_length / writing_tone / include_tables + SlotMeta
    - `PPTSlots(BaseSlots)`：slide_count / template_style / include_notes / visual_preference + SlotMeta
    - `VideoSlots(BaseSlots)`：video_duration / video_type / narration_style + SlotMeta
    - `PodcastSlots(BaseSlots)`：podcast_duration / podcast_format / tone + SlotMeta
    - `SLOT_REGISTRY` 注册表：资源类型 → 槽位类映射
  - 依赖：无

- [ ] **1.3 重构 GraphState**
  - 文件：`app/chat/graph_state.py`
  - 内容：
    - 精简现有 102 个字段，去除重复声明（need_type / user_role_mode）
    - 新增字段：`resource_type` / `slots`（通用槽位容器）/ `slot_meta` / `missing_slots` / `slot_collection_phase`
    - 新增字段：`outline` / `outline_confirmed` / `generated_content` / `generation_checkpoint`
    - 新增字段：`search_context_hint` / `memory_context`
    - 扩展 `response_type`：增加 `text_generate` / `multimodal_generate`
  - 依赖：1.2（需要了解槽位结构）
  - 风险：旧会话状态兼容性，需做迁移适配

- [ ] **1.4 重构 supervisor 节点（两步路由）**
  - 文件：`app/chat/agents/supervisor_agent.py` + `app/chat/service.py`
  - 内容：
    - Step 1 保持一级路由不变（chat / generate / research）
    - Step 2 当 `intent == "generate"` 时调用 `resource_type_router.classify()` 获取二级类型
    - 写入 `state["resource_type"]` 和 `state["response_type"]`
    - 实现 `_route_after_supervisor()` 条件路由：chat → chat_agent / research → research_agent / text_generate → text_gen_engine / ppt/video/podcast → 对应引擎
  - 依赖：1.1、1.3

- [ ] **1.5 废弃 `service_core.py`**
  - 文件：`app/chat/service_core.py`
  - 内容：
    - 确认 service_core.py 与 service.py 的功能重叠部分
    - 将 service_core.py 中独有逻辑迁移到 service.py
    - 删除 service_core.py 并清理所有引用
  - 依赖：1.4（supervisor 重构完成后再合并）

---

## Phase 2: 文本统一引擎（优先级：高）

- [ ] **2.1 抽取插件基类 `plugin_base.py`**
  - 文件：`app/chat/engines/plugin_base.py`
  - 内容：
    - 定义 `GenPlugin(ABC)` 抽象基类
    - 抽象属性：`resource_type` / `slot_class`
    - 抽象方法：`needs_outline_review()` / `build_outline()` / `generate_content()`
    - 可选覆写方法：`post_process()`
  - 依赖：Phase 1 完成

- [ ] **2.2 构建 TextGenEngine**
  - 文件：`app/chat/engines/text_gen_engine.py`
  - 内容：
    - 基于 `universal_report_engine.py` 的 Plan-Execute-Analyze 框架泛化
    - 重构 `ReportState` 为 `TextGenState`，增加 `resource_type` 字段
    - 实现 LangGraph 子图节点：slot_collector → planner → validator → executor → analyzer
    - 实现状态机：collecting → planning → executing → reviewing → finished/replanning/awaiting_human
    - 通过 `PLUGIN_REGISTRY` 动态加载对应插件
  - 依赖：2.1

- [ ] **2.3 实现 ReportPlugin**
  - 文件：`app/chat/engines/plugins/report_plugin.py`
  - 内容：
    - 迁移现有 report_agent 核心逻辑到插件形式
    - `needs_outline_review() → True`
    - `build_outline()`：大纲确认 → 逐章生成 → 合并
    - `generate_content()`：Markdown 长文输出
    - 通过对比测试确保与原有 report 功能输出一致
  - 依赖：2.2
  - 风险高：必须先通过测试再切换路由

- [ ] **2.4 实现 LessonPlanPlugin**
  - 文件：`app/chat/engines/plugins/lesson_plan_plugin.py`
  - 内容：
    - `needs_outline_review() → True`
    - 教案框架确认 → 各环节展开
    - 输出格式：结构化 Markdown（教学目标 / 导入 / 新授 / 练习 / 小结）
  - 依赖：2.2

- [ ] **2.5 实现 QuizPlugin**
  - 文件：`app/chat/engines/plugins/quiz_plugin.py`
  - 内容：
    - `needs_outline_review() → False`
    - 提取知识点 → 批量生成题目
    - 输出格式：JSON + Markdown（题目 + 答案 + 解析）
  - 依赖：2.2

- [ ] **2.6 实现 FlashcardPlugin**
  - 文件：`app/chat/engines/plugins/flashcard_plugin.py`
  - 内容：
    - `needs_outline_review() → False`
    - 提取知识点 → 批量生成卡片
    - 输出格式：JSON 数组（front / back）
  - 依赖：2.2

- [ ] **2.7 实现 BlogPlugin**
  - 文件：`app/chat/engines/plugins/blog_plugin.py`
  - 内容：
    - 迁移 `blog_agent/` 中的博客生成逻辑
    - `needs_outline_review() → True`
    - 大纲确认 → 段落生成 → 合并
    - 输出格式：Markdown 文章
    - 保留两阶段 HITL 能力（章节审查 + 大纲审查）
  - 依赖：2.2

- [ ] **2.8 统一槽位收集器**
  - 文件：`app/chat/engines/slot_collector.py`
  - 内容：
    - 实现 `SlotCollector` 类
    - Phase 1 核心槽位：逐个追问（一次一个）
    - Phase 2 次要槽位：批量追问（一次 2-3 个，可跳过用默认值）
    - 实现 `get_next_question()` 方法
    - 实现 `_build_question()` / `_build_batch_question()` 追问话术生成
    - 实现 `check_impatient()` 不耐烦检测（关键词匹配 → 默认值填充）
    - `IMPATIENT_KEYWORDS`：直接生成 / 别问了 / 不用问 / 快点 / 够了 / 行了 / 默认就好
  - 依赖：1.2（槽位定义）

---

## Phase 3: 搜索工具增强（优先级：高）

- [ ] **3.1 增强工具描述**
  - 文件：`app/chat/tools/agent_tools.py`
  - 内容：
    - 重写 `RAG_TOOL_DESCRIPTION`：明确调用时机（知识点 / 概念 / 术语查询）和不应调用场景
    - 重写 `WEB_SEARCH_TOOL_DESCRIPTION`：明确调用时机（RAG 不足 / 最新信息 / 前沿内容）和不应调用场景
    - 让 LLM 能自主判断何时调用搜索，不再依赖用户显式指令

- [ ] **3.2 搜索上下文注入**
  - 文件：`app/chat/service.py`
  - 内容：
    - 实现 `_build_search_context_hint(state)` 方法
    - 根据 `selected_doc_ids` / `course_id` / `deepsearch_done` 生成 RAG 可用性信号
    - 在每次 LLM 调用前注入到系统提示中

- [ ] **3.3 降级策略**
  - 文件：`app/chat/tools/agent_tools.py`
  - 内容：
    - 实现搜索降级链：RAG → Web → 仅已有上下文
    - 对 EduAgent 外部模块设置超时（默认 30s）
    - 超时/异常时返回 `ok=False`，触发 planner replanning
    - 最终降级为 RAG 结果 + LLM 自身知识

- [ ] **3.4 生成阶段搜索能力**
  - 文件：`app/chat/engines/text_gen_engine.py`
  - 内容：
    - 在 executor 节点中允许 planner 规划搜索步骤
    - 支持步骤序列：rag_search → web_search（补充）→ submit_outline → generate_content
    - 搜索结果合并到生成上下文中

---

## Phase 4: 记忆系统（优先级：中）

- [ ] **4.1 用户画像 Schema**
  - 文件：`core/user_profile_storage.py`
  - 内容：
    - 重构为 Pydantic `UserProfile(BaseModel)`
    - 基本信息：subject / grade_level / teaching_experience
    - 偏好：preferred_style / preferred_depth / preferred_language
    - 使用统计：generation_history / frequent_topics / total_generations / total_conversations
    - 交互偏好（行为学习）：patience_level / detail_preference

- [ ] **4.2 实现 MemoryManager**
  - 文件：`app/chat/memory_manager.py`
  - 内容：
    - 双存储架构：结构化存储（JSON）+ 向量化存储（ChromaDB）
    - `write_memory(user_id, type, content)`：向量化写入 + 结构化画像更新
    - `recall_memory(user_id, query, top_k)`：语义检索相关记忆
    - memory_type 分类：conversation / generation / preference

- [ ] **4.3 记忆向量集合**
  - 文件：ChromaDB collection 配置
  - 内容：
    - 创建 `user_memories` collection
    - 元数据 schema：user_id / type / timestamp
    - 与现有 RAG ChromaDB 实例集成

- [ ] **4.4 记忆注入**
  - 文件：`app/chat/service.py`
  - 内容：
    - 在 supervisor 节点实现 `_inject_memory_context(state)`
    - 注入用户画像（科目 / 受众 / 风格偏好）
    - 注入相关历史记忆（top 3 语义匹配）
    - 写入 `state["memory_context"]`

- [ ] **4.5 遗忘/压缩机制**
  - 文件：`app/chat/memory_manager.py`
  - 内容：
    - `summarize_and_compress()`：保留最近 50 条详细记录
    - 老记忆按时间排序 → LLM 生成摘要 → 删除原始记录 → 写入压缩摘要
    - 控制每用户记忆上限

- [ ] **4.6 画像自动更新**
  - 文件：`app/chat/service.py`
  - 内容：
    - 每次交互后自动更新用户画像
    - 更新 frequent_topics / total_conversations / total_generations
    - 从行为中学习 patience_level / detail_preference

---

## Phase 5: 多模态引擎（优先级：低）

- [ ] **5.1 PPT 引擎**
  - 文件：`app/chat/engines_multimodal/ppt_engine.py`
  - 内容：
    - 独立 LangGraph 子图
    - 流程：槽位收集（PPTSlots）→ 大纲生成（幻灯片结构）→ 用户确认 → 逐页内容生成 → 模板渲染（python-pptx / reveal.js）→ 输出文件
    - 输出：标题 + 要点 + 演讲备注

- [ ] **5.2 视频脚本引擎**
  - 文件：`app/chat/engines_multimodal/video_engine.py`
  - 内容：
    - 独立 LangGraph 子图
    - 流程：槽位收集（VideoSlots）→ 脚本大纲（分镜/段落结构）→ 用户确认 → 逐段脚本生成（旁白 + 画面描述 + 时间轴）→ 输出脚本文档

- [ ] **5.3 播客脚本引擎**
  - 文件：`app/chat/engines_multimodal/podcast_engine.py`
  - 内容：
    - 独立 LangGraph 子图
    - 流程：槽位收集（PodcastSlots）→ 节目大纲（开场/主题段/互动/结尾）→ 用户确认 → 逐段脚本生成（口语化文本 + 音效提示）→ 输出脚本文档

---

## Phase 6: 清理与迁移（优先级：低）

- [ ] **6.1 废弃 `/teacher/*` 路由**
  - 内容：所有生成功能统一走 `/api/chat` + LangGraph，清理旧路由

- [ ] **6.2 废弃独立 `blog_agent/`**
  - 内容：确认 BlogPlugin 完全替代后，删除 `blog_agent/` 目录及相关引用

- [ ] **6.3 修复 GraphState 重复字段**
  - 内容：清理 `need_type` 和 `user_role_mode` 的重复声明

- [ ] **6.4 修复 `schemas.py` 重复字段**
  - 内容：修复 `ChatRequest` 中 `course_id` 定义了两次的问题

---

## 依赖关系总览

```
Phase 1 ──┬──▶ Phase 2 ──▶ Phase 3（3.4 依赖 2.2）
          │
          ├──▶ Phase 3（3.1-3.3 可与 Phase 2 并行）
          │
          ├──▶ Phase 4（可与 Phase 2/3 并行）
          │
          └──▶ Phase 5（可与 Phase 2/3/4 并行）

Phase 2 + Phase 6.2（BlogPlugin 完成后废弃 blog_agent）
Phase 1.3 + Phase 6.3（GraphState 重构时一并修复）
Phase 1.5 + Phase 6.4（合并 service_core 时一并修复 schemas）

Phase 6 在所有功能稳定后执行
```

---

## 风险检查点

| 检查点 | 触发条件 | 动作 |
|--------|---------|------|
| ReportPlugin 回归测试 | 2.3 完成后 | 对比原有 report 输出，确保无功能回退 |
| 二级路由准确率验证 | 1.1 完成后 | 准备测试用例覆盖各类型，验证 LLM + 关键词双保险 |
| GraphState 兼容性 | 1.3 完成后 | 测试旧会话状态的反序列化，确保不崩溃 |
| EduAgent 降级测试 | 3.3 完成后 | 模拟超时/异常，验证降级链正常工作 |
| 集成测试 | 每个 Phase 完成后 | 端到端测试主图路由 + 子图执行 |
