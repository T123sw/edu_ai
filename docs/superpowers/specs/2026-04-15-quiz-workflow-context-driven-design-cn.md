# 习题生成工作流设计：承接对话上下文、信息充分性判断、软确认后直接生成

## 1. 设计目标

本次设计的目标不是继续扩展旧的 `/teacher/quiz` 或 `/teacher/questions` 表单式接口，而是把“习题生成”正式接入现有 chat v2 工作流体系，形成与报告生成一致的对话承接链路。

目标链路为：

`对话上下文 -> QuizPreparationResult -> 信息充分性判断 -> 最小追问或软确认 -> 直接生成习题`

与报告生成不同的是：

- 习题 workflow **不需要大纲阶段**
- 软确认通过后，直接生成最终习题 artifact
- v1 只做 **对话链路**
- 按钮入口、显式工作台入口、非对话触发链路留到后续迭代

本次设计有五个核心目标：

1. 习题生成能够像报告生成一样承接当前会话沉淀，而不是重新从零理解整段历史消息。
2. 习题生成复用现有 `GenerationContext` 和 chat v2 workflow 骨架，保持与报告 workflow 的产品体验和工程分层一致。
3. 系统应先整理和判断信息是否充分；信息不足时只追问最小关键缺口，而不是把所有配置一次性都问完。
4. 当信息足够时，系统先做软确认；用户确认后直接生成最终习题，不引入大纲确认阶段。
5. 生成结果应进入现有 artifact / workflow_state / 课程资源沉淀体系，为后续按钮链路和 artifact 引用能力打基础。

## 2. 当前现状与问题

当前仓库中，习题相关能力主要有两条实现路径：

1. `chat v2` 已经在资源类型和路由语义层面识别 `quiz`，也已有 `generate.quiz` 的整体规划痕迹。
2. 现有真正可用的题目生成实现仍主要是旧接口：
   - `/teacher/quiz`
   - `/teacher/questions`

这些旧接口的共同特点是：

- 主要依赖显式表单参数
- 不承接 `conversation_summary / conversation_memory / active_context`
- 不经过 workflow preparation / readiness / soft confirm
- 不具备“先基于对话整理，再最小追问，再继续生成”的对话式能力

因此会带来四个问题：

1. 用户在对话里已经聊过知识点、学生薄弱点、题型偏好后，仍要重新手工填写参数，体验割裂。
2. 习题生成无法复用现有会话沉淀机制，导致 report / lesson plan / quiz 的工作流风格不一致。
3. 旧接口虽然能出题，但缺乏“信息是否充分”的判断层，无法优雅处理信息不足场景。
4. 后续如果要接按钮链路或 artifact 引用链路，继续叠加在旧接口上会导致双轨维护。

因此，本次设计选择以 chat v2 workflow 为主链路，把旧 `/teacher/quiz` 和 `/teacher/questions` 视为历史兼容实现，而不是继续作为核心架构基础。

## 3. 范围界定

### 3.1 本次范围

本次只设计并实现：

- chat v2 中的对话触发式习题生成链路
- 基于对话上下文的习题 preparation
- 信息充分性判断
- 关键缺口追问
- soft confirm
- soft confirm 后直接生成最终习题 artifact
- 课程资源持久化与 workflow 状态对齐

### 3.2 不在本次范围

以下内容明确不在 v1 范围：

- 右侧工作台中的“生成习题”按钮入口
- knowledge-base direct entry 风格的非对话入口
- 习题大纲、题目草案、二阶段人工确认
- 基于已生成 quiz artifact 的继续编辑、改写、局部重出题
- 题库管理、批量版本树、试卷编排
- 对旧 `/teacher/quiz` 和 `/teacher/questions` 做彻底删除

## 4. 目标用户体验

目标体验如下：

1. 教师先在对话中讨论教学主题、知识点、学生薄弱点、想练什么、题型偏好、难度、题量等。
2. 当教师说“根据上面的内容出一套题”“帮我生成练习题”“围绕这个知识点出 10 道中等难度题”时，系统识别为 `generate.quiz`。
3. 系统承接当前会话沉淀，自动整理出习题生成准备态。
4. 如果缺少最关键的信息，系统只追问最小关键缺口，例如：
   - “你希望围绕哪个知识点出题？”
   - “你更想要选择题、填空题，还是混合题？”
5. 如果当前信息已经足够生成一版可用习题，系统先给出软确认文案，例如：
   - “我将基于当前对话内容，围绕二次函数，按中等难度生成 10 道选择题和填空题混合练习，可以直接开始吗？”
6. 教师确认后，系统直接生成最终习题结果，不经过 outline 阶段。
7. 生成的习题进入右侧生成文件列表，并写入课程资源存储，类型为 `quiz`。

## 5. 总体架构

整体沿用报告 workflow 的主骨架，新增 quiz 对应实现：

`GenerationContext`
-> `QuizAssembler`
-> `QuizContextOrganizer`
-> `QuizReadinessJudge`
-> `QuizWorkflowRuntime`

各层职责如下：

### 5.1 GenerationContext

继续由现有 `GenerationContextBuilder` 从统一会话沉淀中组装：

- `conversation_summary`
- `conversation_memory`
- `active_context`
- `recent_relevant_messages`
- `selected_doc_ids`
- `referenced_artifact_ids`
- `active_artifact`
- `current_course_id`

这一层保持通用，不为 quiz 定制特殊结构。

### 5.2 QuizAssembler

负责把通用 `GenerationContext` 压缩成 quiz workflow 关心的输入材料，重点提取：

- 当前主题
- 已知知识点
- 用户目标
- 学生薄弱点或练习重点
- 难度、题量、题型等 slot hints
- 已选文档与 artifact 引用范围

它的目标不是直接决定生成什么题，而是给 `QuizContextOrganizer` 提供干净的上下文材料。

### 5.3 QuizContextOrganizer

负责利用 LLM 把当前上下文整理成 `QuizPreparationResult`。

这一步对应 report 中的 `ReportContextOrganizer`，但语义改为习题专属，包括：

- 当前是否明确是要“生成习题”
- 题目主题 / 知识点范围
- 目标对象
- 难度
- 题量
- 题型
- 是否需要答案与解析
- 练习重点 / 薄弱点
- 信息缺口
- 软确认文案

### 5.4 QuizReadinessJudge

负责判断当前信息是否已经足够生成一版可用习题。

可能输出三类动作：

- `ask_critical_gap`
- `weak_soft_confirm` / `strong_soft_confirm`
- `resume_after_soft_confirm`

注意：quiz workflow **不需要** “先出大纲”的中间动作。

### 5.5 QuizWorkflowRuntime

负责：

- workflow 阶段管理
- soft confirm 恢复
- 调用 quiz 生成引擎
- 生成 artifact
- 写回 workflow_state
- 对齐课程资源持久化

## 6. 习题槽位设计

### 6.1 设计原则

习题槽位不应简单照搬旧表单接口字段，而应优先贴近教师在自然对话中最常表达的信息。

系统应该：

1. 优先从会话沉淀中自动提取已有信息。
2. 允许对难度、题型、题量等进行合理默认。
3. 仅在关键缺口存在时追问。

### 6.2 核心必需槽位

建议将以下字段视为 quiz workflow 的核心槽位：

- `topic`：出题主题或核心知识点范围
- `difficulty`：整体难度
- `question_types`：题型列表
- `question_count`：题目数量

其中：

1. `topic` 是唯一严格硬缺口，缺失时必须追问。
2. `difficulty` 可以从上下文提取，提取不到时允许使用默认值。
3. `question_types` 可以从上下文提取，提取不到时允许使用默认组合。
4. `question_count` 可以从上下文提取，提取不到时允许使用默认值。

### 6.3 增强槽位

以下字段用于提升习题质量，但默认不阻塞生成：

- `audience`
- `objective`
- `weak_points`
- `knowledge_points`
- `include_answers`
- `include_explanations`
- `style_constraints`
- `source_scope_preferences`

这些字段可以来源于：

1. 用户在对话中的直接表达
2. `conversation_memory` 中的结构化沉淀
3. 已选文档和 artifact 所透露的上下文信息

## 7. QuizPreparationResult 设计

### 7.1 目标

习题 workflow 不应复用 `ReportPreparationResult`，因为两者的 readiness 逻辑和生成目标不同。

quiz 需要单独定义 preparation 结构，以便后续判断：

- 信息是否足够
- 缺什么
- 软确认怎么说
- 最终生成该吃什么输入

### 7.2 建议结构

```ts
type QuizContextSummary = {
  topic_summary: string
  learner_summary: string
  focus_summary: string
  knowledge_points: string[]
  weak_points: string[]
  constraints: Record<string, unknown>
  source_scope: string[]
}

type QuizPreparationResult = {
  quiz_intent: "generate_quiz" | "unclear"
  topic?: string
  audience?: string
  objective?: string

  difficulty?: string
  question_count?: number
  question_types: string[]
  include_answers: boolean
  include_explanations: boolean

  knowledge_points: string[]
  weak_points: string[]
  style_constraints: string[]

  preparation_source: string
  preparation_model: string

  quiz_context_summary: QuizContextSummary

  source_scope: {
    from_conversation: boolean
    from_docs: boolean
    from_course: boolean
    from_artifacts: boolean
  }

  missing_critical_fields: string[]
  confidence: "low" | "medium" | "high"
  soft_confirm_message: string
  followup_candidates: string[]
}
```

### 7.3 字段分层

严格关键字段建议只保留：

- `quiz_intent`
- `topic`

半关键字段如下，缺失时不阻塞生成，但会影响结果质量：

- `difficulty`
- `question_count`
- `question_types`

增强字段如下，不默认阻塞：

- `audience`
- `objective`
- `knowledge_points`
- `weak_points`
- `style_constraints`
- `include_answers`
- `include_explanations`

## 8. 信息充分性判断

### 8.1 判断目标

quiz readiness 判断的核心不是“字段是否全填完”，而是：

**当前是否已经足够生成一版教师可以直接使用的练习题。**

由于 quiz 没有大纲阶段，所以 readiness 一旦通过，就应该进入 soft confirm，而不是进入中间草案产物。

### 8.2 建议规则

当满足以下条件时，允许进入 soft confirm：

1. `quiz_intent = generate_quiz`
2. `topic` 存在
3. 满足以下任一条件：
   - `difficulty` 存在
   - `question_types` 非空
   - `question_count` 存在
   - `knowledge_points` 至少 1 条
   - `weak_points` 至少 1 条
   - `quiz_context_summary` 足够形成稳定练习方向

只有在以下情况才进入追问：

1. `topic` 缺失
2. intent 不清晰，无法判断用户是在咨询出题方式还是明确要求生成习题
3. 上下文过于稀薄，即使有主题也无法形成可用练习范围

### 8.3 默认值策略

为了减少阻塞，建议 quiz workflow 采用如下默认值：

- `difficulty` 默认 `medium`
- `question_count` 默认 `10`
- `question_types` 默认 `["choice"]` 或团队约定的默认组合
- `include_answers` 默认 `true`
- `include_explanations` 默认 `true`

默认值的作用是让系统在对话信息已基本充分时，尽量少追问，符合“先顺滑生成”的产品方向。

## 9. 软确认设计

### 9.1 设计目标

soft confirm 的作用不是让用户重新配置所有字段，而是让用户知道系统“理解成什么了”，并给一次轻量纠偏机会。

quiz 的 soft confirm 应比 report 更直接，因为后续没有 outline 阶段。

### 9.2 文案要求

soft confirm 文案应明确包含以下信息中的大部分：

- 围绕什么主题或知识点出题
- 题型
- 题量
- 难度
- 是否带答案解析

例如：

- “我将基于当前对话内容，围绕牛顿第二定律，按中等难度生成 10 道选择题和填空题混合练习，并附答案与解析，可以直接开始吗？”
- “我准备围绕二次函数的图像与性质，生成 8 道基础到中等难度练习题，重点覆盖你刚才提到的易错点，可以开始吗？”

### 9.3 恢复逻辑

当 workflow 已停在 `awaiting_confirm` 且阶段为 `soft_confirm` 时：

- 用户明确回复“可以”“开始吧”“确认生成”等，应直接恢复并进入题目生成。
- 用户补充修改信息，如“改成 5 道填空题”，则系统应先更新 preparation / filled slots，再重新判断是否需要再次 soft confirm。

## 10. 习题生成阶段设计

### 10.1 生成目标

soft confirm 通过后，系统直接生成最终 quiz artifact，不再引入大纲 artifact 或中间草案 artifact。

### 10.2 生成输入

建议在 runtime 内部落成统一的 quiz 生成输入结构，例如：

```ts
type QuizGenerationInput = {
  topic: string
  audience?: string
  objective?: string

  difficulty: string
  question_count: number
  question_types: string[]
  include_answers: boolean
  include_explanations: boolean

  knowledge_points: string[]
  weak_points: string[]
  style_constraints: string[]

  selected_doc_ids: string[]
  referenced_artifact_ids: string[]
  source_summary: string
}
```

### 10.3 引擎复用策略

v1 可以复用现有旧题目生成能力中的 prompt 资产、结构校验逻辑和课程资源存储格式，但不应继续以旧接口为主入口。

建议做法是：

- 对外统一走 chat v2 quiz workflow
- 对内可在 runtime 中复用已有 quiz 生成 prompt 或底层题目生成 helper
- 逐步把旧 `/teacher/quiz` 与 `/teacher/questions` 的有效逻辑抽取成可复用内部服务

这样既能降低 v1 改造成本，又不牺牲架构方向。

## 11. Artifact 与持久化设计

### 11.1 结果 artifact

最终生成结果类型建议统一为 `quiz`。

artifact 应至少包含：

```ts
type QuizArtifact = {
  artifact_id: string
  artifact_type: "quiz"
  title: string
  content: {
    id?: string
    title: string
    difficulty: string
    question_type: string
    questions: Array<{
      id: string
      type: string
      stem: string
      options?: string[]
      answer?: string
      explanation?: string
    }>
  }
  generation_state: {
    status: "completed"
    generation_mode: "initial"
    source_scope: Record<string, boolean>
  }
}
```

### 11.2 课程资源沉淀

生成完成后，应像 report 一样自动写入课程资源存储，`material_type = "quiz"`。

建议保存字段包括：

- `title`
- `material_type`
- `created_at`
- `updated_at`
- `difficulty`
- `question_type`
- `questions`
- `generation_state`

这应与当前课程资源中 quiz 的读取方式兼容，避免前端展示层出现额外分支。

## 12. Workflow 状态设计

quiz workflow 应复用现有 workflow_state 框架，只新增 quiz 专属 stage 语义。

建议阶段包括：

- `preparing`
- `critical_gap`
- `soft_confirm`
- `generating`
- `completed`
- `failed`

其中：

- `critical_gap` 表示系统正在等待用户补足关键缺口
- `soft_confirm` 表示系统已理解生成意图，等待用户确认
- `generating` 表示系统正在生成最终习题

与 report 的关键差异是：

- quiz 没有 `outline_review`
- quiz 不保存中间 outline artifact

## 13. 与现有 report workflow 的对齐原则

虽然 quiz 没有大纲阶段，但整体节奏应与 report 保持一致：

### 13.1 需要保持一致的部分

- 使用相同的 `GenerationContextBuilder`
- 使用相同的 conversation state 沉淀来源
- 同样先做 workflow-specific context organize
- 同样通过 readiness judge 决定追问或 soft confirm
- 同样支持 soft confirm 恢复
- 同样生成 artifact 并写入课程资源

### 13.2 明确不同的部分

- report 是“软确认 -> 大纲 -> 确认 -> 正文”
- quiz 是“软确认 -> 直接生成最终习题”

这意味着 quiz 是 report-first 承接模式的一个更短分支，而不是另一套完全不同的架构。

## 14. 测试与验收建议

### 14.1 核心测试方向

至少覆盖以下场景：

1. 用户明确要求生成习题，且上下文中主题明确，系统进入 soft confirm。
2. 用户要求生成习题，但缺少主题，系统只追问主题，不追问所有字段。
3. soft confirm 后用户回复确认，系统直接生成 quiz artifact。
4. soft confirm 后用户补充“改成填空题”，系统更新 preparation 后重新进入 soft confirm 或直接生成。
5. 生成完成后 quiz artifact 正确进入右侧文件列表和课程资源存储。
6. 历史会话恢复后，workflow_state 为 quiz 的软确认阶段仍可继续。

### 14.2 产品验收标准

满足以下条件视为本次目标达成：

1. 教师可在纯对话中自然触发习题生成。
2. 系统能承接会话沉淀，而不是要求用户重新填写表单。
3. 系统在关键字段缺失时能最小追问。
4. 系统在信息充分时能先软确认。
5. 用户确认后可直接生成最终习题，不出现 outline 中间态。
6. 生成结果能像现有 report artifact 一样进入统一 artifact / course material 体系。

## 15. 后续演进方向

本次设计故意为后续扩展留出空间：

1. 接入右侧工作台中的显式“生成习题”按钮链路。
2. 支持 direct-entry 模式下的 quiz preparation。
3. 支持 quiz artifact 的继续编辑、重出题、按题型重排。
4. 支持 quiz 与 lesson plan / report / ppt 之间的 artifact 引用联动。
5. 在 quiz workflow 稳定后，逐步弱化旧 `/teacher/quiz` 与 `/teacher/questions` 入口的重要性。

## 16. 最终结论

本次习题生成设计应选择与报告生成一致的 chat v2 workflow 思路，而不是继续叠加旧表单接口。

最终采用的产品与工程原则是：

- **先承接对话上下文**
- **再用 LLM 整理 quiz preparation**
- **判断信息是否充分**
- **不足则最小追问**
- **足够则软确认**
- **确认后直接生成最终习题**

这条链路保留了 report workflow 的核心价值，同时根据 quiz 的产品特征去掉了“大纲确认”阶段，使习题生成在体验上更轻、更快，也更适合作为对话中的即时输出能力。
