# 教案生成工作流设计：承接对话上下文、准备态总结、先大纲确认后生成正文

## 1. 设计目标

本次改造的目标不是继续增强旧的 `/teacher/lesson_plan` 一次性直出接口，而是把教案生成接入现有 chat v2 工作流体系，形成与报告生成一致的主链路：

`对话上下文 -> 准备态总结 -> 信息充分性判断 -> 教案大纲 -> 用户确认/修改 -> 教案正文`

核心目标有五个：

1. 教案生成能够直接承接当前会话沉淀的上下文，而不是重新全量扫描历史消息。
2. 教案生成与报告生成共用同一类 workflow 骨架，只替换教案特有的槽位、准备态结构和 artifact 结构。
3. 教案流程采用“先大纲、后正文”的双阶段 HITL 模式，支持教师先确认教学设计方向，再生成完整教案。
4. 教案大纲和正文都要贴近教师日常使用，优先支持“标准备课型”而不是纯目录或过度展开的授课逐字稿。
5. 兼容现有前端和存储侧已有的教案基础结构，避免一次性引入过大破坏面。

## 2. 当前现状与问题

当前仓库中与教案生成相关的实现分成两块：

1. chat v2 路由层已经识别 `generate.lesson_plan`，但没有真正的 `lesson_plan workflow runtime`。
2. `/teacher/lesson_plan` 仍然是旧式接口：读取选中文档全文，调用模型一次性生成 JSON，然后直接持久化。

这带来三个问题：

1. 教案生成无法复用 chat v2 已经具备的会话上下文承接、记忆沉淀、artifact 恢复、workflow 恢复能力。
2. 教案与报告/PPT 的生成体验不一致，无法统一到“工作流 + artifact”的产品模型中。
3. 旧接口虽然能生成结果，但不支持对话式补槽、软确认、大纲修改、正文续生成等后续能力。

因此，本次设计选择以 chat v2 workflow 为主线，把旧教案接口视为历史兼容路径，而不是继续作为核心实现。

## 3. 目标用户体验

目标体验如下：

1. 教师在对话中先聊教学主题、学情、教学目标、课时、重难点等内容。
2. 当教师说“帮我生成教案”或点击教案入口卡后，系统承接当前会话上下文，自动整理出一份“教案准备态”。
3. 如果主题缺失，系统只追问最小关键缺口；如果主题明确且上下文足够，系统直接给出一版教案大纲。
4. 教师可以针对大纲做日常语言修改，例如“导入压缩到 5 分钟”“加一个分组讨论环节”“作业换成分层作业”。
5. 系统根据已确认的大纲生成完整正文教案，并保存为结构化 artifact，后续可展示、编辑、沉淀为课程资源。

## 4. 总体架构

整体沿用 report workflow 的主骨架，新增 lesson plan 对应实现：

`GenerationContext`
-> `LessonPlanAssembler`
-> `LessonPlanContextOrganizer`
-> `LessonPlanReadinessJudge`
-> `LessonPlanWorkflowRuntime`

其中：

1. `GenerationContext` 继续由现有 conversation memory / summary / recent relevant messages / artifacts / docs 组装而来。
2. `LessonPlanAssembler` 负责从通用上下文中抽出教案相关提示字段，构建工作流输入 payload。
3. `LessonPlanContextOrganizer` 负责做“教案准备态总结”，生成结构化的 `LessonPlanPreparationResult`。
4. `LessonPlanReadinessJudge` 负责判断当前是否应该追问、先输出软确认、还是直接生成大纲。
5. `LessonPlanWorkflowRuntime` 负责 workflow phase 管理、调用引擎、大纲 artifact 和正文 artifact 的输出适配。

## 5. 教案槽位设计

### 5.1 设计原则

教案槽位不能只是沿用旧接口里的少量表单字段，而要更接近教师备课时自然会表达的信息。

同时，教案 workflow 不应该因为教师没有一次性提供所有字段就被卡住。系统应优先：

1. 把会话里已有的教学信息整理出来。
2. 用模型补全可合理推断的草案字段。
3. 仅在关键缺口存在时追问。

### 5.2 核心必需槽位

以下槽位被视为教案 workflow 的核心必需输入：

- `topic`：课题/章节主题
- `audience`：授课对象，如七年级、高一、大学一年级
- `objective`：本课核心教学目标
- `duration`：课时长度
- `lesson_type`：课型，如新授课、复习课、习题课、实验课、研讨课

其中：

1. `topic` 是唯一严格硬缺口，缺失时必须追问。
2. `audience` / `objective` / `duration` / `lesson_type` 优先从上下文推断；推断失败时进入大纲草案默认值或轻量追问。

### 5.3 增强槽位

以下槽位用于提升教案质量，但不默认阻断大纲生成：

- `knowledge_points`
- `key_points`
- `hard_points`
- `teaching_methods`
- `class_profile`
- `assessment_method`
- `homework_preference`
- `resource_constraints`
- `style_constraints`

这些字段允许来源于：

1. 用户直接表达
2. 对话记忆中的已确认事实与约束
3. 模型从 summary / confirmed facts / student signals / selected docs 中整理出的草案值

## 6. 教案准备态结构

### 6.1 目标

报告 workflow 当前使用 `ReportPreparationResult` 作为准备态主结构。教案需要平行定义自己的准备态结构，而不是强行复用报告字段。

### 6.2 建议结构

```ts
type LessonPlanContextSummary = {
  topic_summary: string
  learner_summary: string
  objective_summary: string
  key_points: string[]
  hard_points: string[]
  constraints: Record<string, unknown>
  source_scope: string[]
}

type LessonPlanPreparationResult = {
  lesson_plan_intent: "generate_lesson_plan" | "unclear"
  topic?: string
  audience?: string
  objective?: string
  duration?: string
  lesson_type?: string

  preparation_source: string
  preparation_model: string

  lesson_plan_context_summary: LessonPlanContextSummary

  knowledge_points: string[]
  key_points: string[]
  hard_points: string[]
  teaching_methods: string[]
  class_profile: string[]
  assessment_method?: string
  homework_preference?: string
  resource_constraints: string[]
  style_constraints: string[]

  source_scope: {
    from_conversation: boolean
    from_docs: boolean
    from_course: boolean
    from_artifacts: boolean
  }

  open_questions: string[]
  missing_critical_fields: string[]
  confidence: "low" | "medium" | "high"

  soft_confirm_message: string
  followup_candidates: string[]
}
```

### 6.3 字段分层

真正的硬关键项建议只保留：

- `lesson_plan_intent`
- `topic`

以下字段为半关键项，缺失时不阻断大纲草案，但会影响大纲质量：

- `audience`
- `objective`
- `duration`
- `lesson_type`

以下字段为增强项，不默认阻断：

- `knowledge_points`
- `key_points`
- `hard_points`
- `teaching_methods`
- `class_profile`
- `assessment_method`
- `homework_preference`
- `resource_constraints`
- `style_constraints`

## 7. 信息充分性判断

### 7.1 判断目标

新的教案 readiness 判断，不是检查所有表单槽位是否填满，而是判断：

**当前是否已经足够生成一版可供教师确认的标准备课型大纲。**

### 7.2 建议判定规则

当满足以下条件时，允许进入大纲阶段：

1. `lesson_plan_intent = generate_lesson_plan`
2. `topic` 存在
3. 满足以下任一条件：
   - `objective` 存在
   - `audience` 与 `duration` 同时存在
   - `knowledge_points` 至少 2 条
   - `key_points` 或 `hard_points` 任一存在
   - `lesson_plan_context_summary` 足够形成一版综合型备课提纲

只在以下情形触发追问：

1. `topic` 缺失
2. intent 不清晰，无法确定用户是在咨询还是要求生成教案
3. 上下文过于稀薄，无法组织出哪怕一版可确认大纲

### 7.3 交互策略

建议继续沿用 report workflow 的“soft confirm”思路：

1. 按钮入口触发时可使用更弱的确认文案，先说明将基于当前信息生成一版教案大纲。
2. 对话中明确表达“生成教案”时，可使用更强的确认文案或直接进入大纲阶段。

## 8. 教案大纲设计

### 8.1 设计目标

教案大纲不能只是纯目录，否则教师在确认阶段难以判断这节课是否可用。

大纲应该是一份“备课提纲卡”，让教师能够快速判断：

1. 目标是否对
2. 课时分配是否合理
3. 环节设置是否符合课堂习惯
4. 是否需要插入讨论、演示、练习、作业等具体环节

### 8.2 大纲 artifact 结构

建议 `lesson_plan_outline` 使用如下结构：

```ts
type LessonPlanOutlineArtifact = {
  basic_info: {
    topic: string
    audience: string
    duration: string
    lesson_type: string
  }
  teaching_objectives: string[]
  key_and_hard_points: {
    key_points: string[]
    hard_points: string[]
    breakthrough_ideas: string[]
  }
  lesson_flow: Array<{
    step: string
    goal: string
    duration: string
    notes: string
  }>
  teaching_support: {
    teaching_methods: string[]
    teaching_resources: string[]
    assessment_method: string
  }
}
```

### 8.3 lesson_flow 默认环节

默认建议包含五段：

1. 导入
2. 新授/探究
3. 练习巩固
4. 总结提升
5. 作业布置

这五段不是强制固定模板，允许在以下情况下调整：

1. 复习课可替换为“知识回顾 -> 典型例题 -> 变式训练 -> 总结”
2. 实验课可包含“实验说明 -> 分组操作 -> 现象记录 -> 归纳讨论”
3. 研讨课可包含“问题抛出 -> 小组讨论 -> 汇报交流 -> 教师总结”

## 9. 教案正文 artifact 结构

### 9.1 设计目标

正文结构应与现有旧教案接口大体兼容，但增强为更适合日常备课的标准结构。

### 9.2 建议正文结构

```ts
type LessonPlanArtifact = {
  title: string
  basicInfo: {
    audience: string
    duration: string
    lessonType: string
  }
  objectives: string[]
  keyPoints: string[]
  hardPoints: string[]
  teachingMethods: string[]
  teachingAids: string[]
  process: Array<{
    step: string
    goal: string
    teacherActivities: string[]
    studentActivities: string[]
    duration: string
    assessment: string
  }>
  boardPlan: string[]
  homework: string
  reflectionTips: string[]
}
```

### 9.3 与旧结构的兼容策略

旧接口当前返回：

- `title`
- `objectives`
- `keyPoints`
- `hardPoints`
- `process`
- `homework`

兼容策略建议如下：

1. 新 workflow artifact 仍保留上述字段名称，确保旧前端读取主内容时不立即失效。
2. 新增的 `basicInfo` / `teachingMethods` / `teachingAids` / `boardPlan` / `reflectionTips` 作为增量字段，由前端按需渐进展示。
3. 若旧展示组件暂时不识别新字段，也不影响基础教案展示。

## 10. workflow phase 设计

建议 lesson plan workflow phase 与 report workflow 对齐，但采用教案语义命名：

1. `preparing`
   - 整理上下文，生成 `LessonPlanPreparationResult`
2. `soft_confirm`
   - 告知用户将基于当前信息生成一版教案大纲
3. `outlining`
   - 生成或修改 `lesson_plan_outline`
4. `awaiting_outline_confirm`
   - 等待用户确认或提出修改
5. `generating`
   - 根据确认后的大纲生成 `lesson_plan`
6. `completed`
   - 正文 artifact 完成并持久化

恢复逻辑建议与 report 一致：

1. 若当前 workflow_state 存在且未被中断，则继续当前 phase。
2. 若 active context 指向 `lesson_plan` 且用户输入是“大纲确认/继续生成类”回复，则恢复 `lesson_plan workflow`。

## 11. 用户修改语义

教案 workflow 要重点支持教师对大纲阶段的自然语言修改，常见模式包括：

1. 调整时间
   - “导入压缩到 5 分钟”
2. 调整环节
   - “加一个分组讨论环节”
3. 调整风格
   - “别太理论化，更偏实用”
4. 调整作业
   - “作业改成分层作业”
5. 调整对象
   - “这是给高一的，不是初中”

这意味着大纲修改阶段不能只支持“确认/不确认”二元状态，而需要支持：

1. 覆盖局部字段
2. 局部重生成大纲
3. 保留已确认部分继续迭代

第一版可先实现“全文重生成大纲但保留用户修改指令注入”的策略，后续再做细粒度 patch。

## 12. 后端模块设计

建议新增或修改的模块如下：

### 12.1 新增 domain

- `app/chat/domain/lesson_plan_preparation.py`
  - 定义 `LessonPlanContextSummary`
  - 定义 `LessonPlanPreparationResult`

### 12.2 新增 workflow 目录

- `app/chat/workflows/lesson_plan/__init__.py`
- `app/chat/workflows/lesson_plan/assembler.py`
- `app/chat/workflows/lesson_plan/runtime.py`

### 12.3 新增 orchestrator 组件

- `app/chat/orchestrator/lesson_plan_context_organizer.py`
- `app/chat/orchestrator/lesson_plan_readiness_judge.py`

### 12.4 修改现有组件

- `app/chat/application/route_chat_service.py`
  - 注册 `lesson_plan` workflow
- `app/chat/orchestrator/route_rules.py`
  - 增加 `lesson_plan` follow-up 恢复判定
- `app/chat/slot_definitions.py`
  - 扩充 `LessonPlanSlots` 字段定义
- 状态持久化 / artifact 写回相关模块
  - 增加 `lesson_plan_outline` 与 `lesson_plan` artifact 的 active_context 对齐

## 13. 持久化策略

### 13.1 对话态持久化

需要在 conversation state 中写回：

- `workflow_state.workflow_type = lesson_plan`
- `workflow_state.stage = outlining / generating / ...`
- `artifacts`
- `active_context.active_workflow_type = lesson_plan`
- `active_context.active_artifact_type = lesson_plan_outline | lesson_plan`

### 13.2 课程资源持久化

当最终 `lesson_plan` artifact 生成完成后，写入课程资源。

建议沿用现有 `material_type = "lesson_plan"`，同时将结构化正文整体保存到 `plan` 或新的 `content` 字段中，但第一版应兼容旧有 `plan` 读法。

## 14. 与旧 `/teacher/lesson_plan` 接口的关系

第一版推荐策略：

1. chat v2 的教案生成走新 workflow。
2. 旧 `/teacher/lesson_plan` 暂时保留，作为历史兼容入口。
3. 不在本次改造中强行把旧接口重写成 workflow 入口，以控制范围。

后续若需要统一实现，再考虑：

1. 让旧接口调用新的 lesson plan generation service
2. 或将旧接口逐步下线，只保留 workflow 入口

## 15. 测试策略

建议测试覆盖以下层级：

### 15.1 组织器

- `LessonPlanContextOrganizer`
  - 能从上下文中整理出 topic / audience / duration / objective 草案
  - topic 缺失时返回关键缺口
  - 对“生成教案”意图识别稳定

### 15.2 readiness judge

- topic 明确时允许进入大纲阶段
- topic 缺失时触发追问
- 上下文稀薄但仍能形成草案时允许 soft confirm

### 15.3 runtime

- 能包装引擎输出为 `workflow + action + artifacts`
- 能从 outline confirm 回复继续到正文生成
- 能从 active context 恢复 workflow

### 15.4 route 规则

- `generate.lesson_plan` 进入 workflow
- 教案大纲确认类 follow-up 能恢复 lesson plan workflow

### 15.5 持久化

- `lesson_plan_outline` artifact 写回 conversation state
- `lesson_plan` artifact 完成后写回课程资源

## 16. 非目标

本次不纳入范围：

1. 教案局部片段级 patch 编辑
2. 教案转 PPT 的自动串联
3. 多版本教案 diff 展示
4. 旧 `/teacher/lesson_plan` 全量迁移到新 workflow 内核

这些能力可以在 lesson plan workflow 稳定后再继续追加。

## 17. 推荐落地顺序

推荐按以下顺序实施：

1. 定义 `LessonPlanPreparationResult`
2. 补齐 `LessonPlanSlots`
3. 实现 `LessonPlanContextOrganizer`
4. 实现 `LessonPlanReadinessJudge`
5. 实现 `LessonPlanWorkflowRuntime`
6. 注册到 `RouteChatService`
7. 增加 `route_rules` 的 follow-up 恢复能力
8. 增加 artifact 持久化与课程资源写回
9. 跑通 focused tests

## 18. 结论

本次教案功能应采用“报告工作流平移”的方式接入 chat v2，而不是继续扩展旧式直出接口。

最终形态是：

1. 教案 workflow 与报告 workflow 共享同类骨架
2. 教案独立拥有自己的准备态结构、槽位设计和 artifact schema
3. 教师先确认一版贴近日常备课的提纲，再生成标准备课型正文
4. 新结构向后兼容旧教案主要字段，并为后续局部编辑、转 PPT、资源沉淀留出扩展空间
