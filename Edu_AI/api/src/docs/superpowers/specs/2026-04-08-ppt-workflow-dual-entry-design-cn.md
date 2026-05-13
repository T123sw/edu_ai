# PPT 双入口统一工作流设计（对话入口 + 显式入口）

**状态：** 已完成初版设计，可进入实施计划阶段  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat` 与 `D:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt`

## 1. 设计目标

本设计要解决的不是“如何再包一层调用 html2ppt”，而是如何把 PPT 生成功能以与现有 report v2 一致的方式接入主系统。

目标有六个：

1. 提供两个对外入口：
   - 对话驱动入口
   - 显式配置 / 文档驱动入口
2. 两个入口在“信息采集层”分开，在“PPT 生成主链路”完全合流。
3. PPT 生成不直接一步到位，而是先产出可确认、可修改的 `ppt_outline`。
4. `content_markdown` 不由入口层直接生成，而由统一 assembler 在后半程稳定组装。
5. `content_markdown` 的最终拼装以代码模板化为主，而不是完全交给 LLM 自由输出。
6. 最终结果以标准 `artifact` 形式回到现有 v2 响应骨架中，支持预览、下载、重试与后续 revision。

## 2. 非目标

本阶段不做以下事情：

1. 不把 `html2ppt` 内嵌到 Python 进程内，仍保持其作为独立 Node 服务运行。
2. 不让前端直接调用 `html2ppt` 服务，所有调用都由 Python 后端中转。
3. 不在第一版支持多页 revision；第一版先对齐 `html2ppt` 当前的单页 revision 能力。
4. 不把 `content_markdown` 暴露为默认终端用户可见内容；它首先是内部协议产物。
5. 不复用旧 `service.py` 里 `ppt -> report_agent` 的回退行为作为正式方案。
6. 不在第一版实现图片/媒体检索、素材匹配、联网搜图或图像生成；第一版先完成纯文字 PPT 主链路。

## 3. 总体架构

### 3.1 双入口，单内核

系统对外保留两个入口：

1. `POST /api/chat/v2/reply`
   - 面向自然语言对话流
   - 通过 `action_hint=generate.ppt` 或意图识别进入 PPT workflow
2. `POST /api/chat/v2/ppt`
   - 面向显式表单、文档驱动、配置式启动
   - 前端明确表达“我要生成 PPT”

两条入口都不能直接：

- 直接组装 `content_markdown`
- 直接调用 `html2ppt`
- 直接把结果当普通回复文本返回

两条入口都必须先归一化为统一的 `PptWorkflowRequest`，再进入同一条主链路：

`PptWorkflowRequest`
-> `PptOutlineBuilder`
-> `awaiting_outline_confirmation`
-> `PptContentMarkdownAssembler`
-> `PptContentValidator`
-> `Html2PptClient`
-> `ppt_deck artifact`

### 3.2 设计原则

1. 信息采集与协议组装分离。
2. 用户确认的是大纲，不是协议文本。
3. LLM 负责内容组织，代码负责协议稳定性。
4. `html2ppt` 是强协议下游，因此提交前必须先做主系统自己的协议校验。
5. 所有中间结果都尽量以结构化对象存在，必要时再转成字符串协议。

## 4. 两个入口的职责边界

### 4.1 对话入口

继续复用：

`POST /api/chat/v2/reply`

用途：

1. 从多轮对话中识别 PPT 生成意图。
2. 从 conversation memory、workflow state、selected docs、当前请求中整理 PPT 输入。
3. 在信息不足时继续追问关键缺口。
4. 在信息足够时先产出 `ppt_outline`，等待用户确认。

该入口的优势是：

- 能消费已有对话上下文
- 能自然追问
- 能在已有会话里承接后续确认、修改、重试、revision

建议新增或统一支持的 action：

- `generate.ppt`
- `ppt.outline.confirm`
- `ppt.outline.edit`
- `ppt.generate.retry`
- `ppt.revision.create`

### 4.2 显式入口

新增：

`POST /api/chat/v2/ppt`

用途：

1. 让前端从“PPT 生成页”显式启动一个 workflow session。
2. 用户上传文档、填写页数 / 风格 / 受众 / 目标等字段。
3. 后端校验并归一化显式配置。
4. 直接进入 `generating_outline`，然后与对话入口合流。

该入口的定位不是“直接创建一个 PPT 文件”，而是：

**启动一个 PPT workflow session。**

因此其响应也应返回：

- `conversation`
- `workflow`
- `message`
- `artifacts`
- `status_card`

而不是只返回一个同步下载地址。

### 4.3 `conversation_id` 的处理原则

对外：

- `conversation_id` 可以不传

对内：

- 一旦进入 workflow，系统必须保证存在 `conversation_id`

如果显式入口没传 `conversation_id`，后端需要自动创建一个，并把该次 PPT workflow 全程挂在这个 conversation 下。这样可以保证：

1. outline 确认有稳定归属
2. status card 有稳定归属
3. artifacts 有稳定归属
4. revision 与重试不产生孤儿任务

## 5. 接口草案

### 5.1 对话入口请求

```json
{
  "question": "请基于我们前面的内容帮我整理成 PPT",
  "conversation_id": "conv_xxx",
  "model_id": "optional",
  "course_id": "optional",
  "action_hint": "generate.ppt",
  "allow_rag": false,
  "allow_web": false,
  "selected_doc_ids": ["doc_001", "doc_002"]
}
```

说明：

1. `action_hint` 可以显式传 `generate.ppt`，也可以由后端识别自然语言路由到 `ppt`。
2. `selected_doc_ids` 继续沿用现有 capability / doc 选择机制。
3. 如果当前会话里已有可继续的 PPT workflow，则优先走 workflow resume。

### 5.2 显式入口请求

```json
{
  "conversation_id": "optional-conv-id",
  "entry_mode": "explicit_ppt",
  "topic": "TCP 三次握手",
  "audience": "大一计算机专业学生",
  "objective": "用于 15 分钟课堂讲解，帮助学生理解连接建立过程",
  "slide_count": 8,
  "theme_id": "heu_academic_elegant",
  "template_style": "教学简洁风",
  "visual_preference": "图文并茂",
  "include_notes": true,
  "selected_doc_ids": ["doc_001"],
  "user_instruction": "希望前半部分更基础，后半部分加入抓包示意",
  "idempotency_key": "ppt-explicit-001"
}
```

说明：

1. 显式入口优先传 `selected_doc_ids` 或文档引用，不建议直接把完整文档正文放进请求体。
2. 文档正文的拉取、摘要和切片由后端完成，避免前端承担内容拼装职责。
3. `entry_mode=explicit_ppt` 用于 trace 和后续行为区分。

### 5.3 显式入口成功响应

建议保持 v2 骨架：

```json
{
  "message": {
    "role": "assistant",
    "content": "已根据你的配置生成 PPT 大纲，请先确认。"
  },
  "conversation": {
    "conversation_id": "conv_xxx"
  },
  "action": {
    "name": "ppt.outline.review",
    "available_actions": [
      "ppt.outline.confirm",
      "ppt.outline.edit",
      "ppt.cancel"
    ]
  },
  "workflow": {
    "workflow_id": "wf_ppt_xxx",
    "workflow_type": "ppt",
    "status": "running",
    "stage": "awaiting_outline_confirmation"
  },
  "artifacts": [
    {
      "artifact_type": "ppt_outline"
    }
  ],
  "trace": {
    "path": "workflow",
    "entry_mode": "explicit_ppt"
  }
}
```

## 6. 统一内部对象

### 6.1 `PptWorkflowRequest`

两条入口必须归一化成统一请求对象：

```ts
type PptWorkflowRequest = {
  source_type: "conversation" | "explicit"
  conversation_id: string

  topic: string
  audience: string
  objective: string

  slide_count: number
  theme_id: string
  template_style: string
  visual_preference: string
  include_notes: boolean

  selected_doc_ids: string[]
  source_summary: string

  constraints: {
    must_include: string[]
    avoid: string[]
    preferred_examples: string[]
  }

  metadata: {
    request_id: string
    user_id: string
    tenant_id?: string
    idempotency_key?: string
    entry_mode?: string
  }
}
```

说明：

1. `source_summary` 由后端从文档和对话中抽取得出。
2. 对话入口和显式入口都不直接生成 `content_markdown`。
3. `selected_doc_ids` 作为资料引用入口保留。

### 6.2 `PptOutline`

`ppt_outline` 是用户确认层产物，不是协议层产物，而且第一版就要细到“章节级 + 页级”：

```ts
type PptOutline = {
  deck_title: string
  deck_subtitle?: string
  theme_id: string
  confirmation_status: "pending" | "confirmed" | "edited"
  chapters: Array<{
    chapter_index: number
    chapter_title: string
    chapter_goal: string
    slides: Array<{
      slide_index: number
      role: "cover" | "toc" | "section" | "content" | "thanks"
      title: string
      goal: string
      key_points: string[]
      presenter_notes?: string
    }>
  }>
  slides: Array<{
    slide_index: number
    role: "cover" | "toc" | "section" | "content" | "thanks"
    title: string
    goal: string
    key_points: string[]
    presenter_notes?: string
  }>
}
```

说明：

1. `confirmation_status` 用于区分系统原始大纲、用户确认版大纲、用户修订版大纲。
2. `chapters` 负责表达章节结构，`slides` 负责表达最终逐页顺序，二者必须保持一致。
3. 每一页都至少要有 `role / title / goal / key_points`，否则视为还不够进入 `content_markdown` 组装。
4. 这一层允许用户改章节名、页标题、页顺序、页数增减，但不要求直接理解 `Blocks` 协议。

### 6.3 `PptDeckArtifact`

最终产物建议统一成 `ppt_deck` artifact：

```ts
type PptDeckArtifact = {
  artifact_id: string
  artifact_type: "ppt_deck"
  title: string
  content: {
    job_id: string
    revision_id: string
    pptx_url: string
    html_url: string
    fragment_url: string
    manifest_url: string
    slide_count: number
  }
  generation_state: {
    status: "queued" | "running" | "completed" | "failed"
    phase:
      | "submitting_ppt_job"
      | "polling_ppt_job"
      | "completed"
      | "failed"
    progress: number
    message: string
  }
}
```

## 7. Workflow 状态与动作

### 7.1 工作流阶段

建议固定以下阶段：

1. `collecting_inputs`
2. `generating_outline`
3. `awaiting_outline_confirmation`
4. `assembling_content_markdown`
5. `validating_content_markdown`
6. `submitting_ppt_job`
7. `polling_ppt_job`
8. `completed`
9. `failed`

其中：

- 对话入口可能在 `collecting_inputs` 停留多轮
- 显式入口通常直接进入 `generating_outline`
- 两者从 `generating_outline` 开始完全一致

### 7.2 标准动作枚举

建议把用户动作显式建模：

1. `generate.ppt`
2. `ppt.outline.confirm`
3. `ppt.outline.edit`
4. `ppt.generate.retry`
5. `ppt.revision.create`
6. `ppt.cancel`

前端不要根据 workflow stage 猜动作，而是由响应显式返回当前允许动作。

### 7.3 `action` 返回建议

```json
{
  "action": {
    "name": "ppt.outline.review",
    "available_actions": [
      "ppt.outline.confirm",
      "ppt.outline.edit",
      "ppt.cancel"
    ]
  }
}
```

## 8. 主链路设计

### 8.1 Outline 生成

`PptOutlineBuilder` 的职责是：

1. 消费 `PptWorkflowRequest`
2. 生成 deck 级标题、副标题、页数建议
3. 生成章节级结构
4. 生成逐页 `role / title / goal / key_points`
4. 输出 `ppt_outline`

这一层可以使用 LLM，但输出必须结构化。

这一层的要求比 report 大纲更严格：

1. 大纲不能只停留在“几个一级点”。
2. 大纲必须明确到每个章节。
3. 大纲必须明确到每一页。
4. 每一页都要能回答“这一页讲什么、解决什么目标、至少覆盖哪几个点”。

### 8.2 信息充分性判断与追问

是否进入 `generating_outline`，判断标准不是“能不能勉强生成一份 PPT”，而是：

**是否已经有足够信息生成一份稳定的、逐页级的 `ppt_outline`。**

这一层不要设计成“严格填表式槽位收集”，而要设计成：

**软槽位提取 + 少次追问 + 模型自主补全。**

#### 8.2.1 `PptPreparationResult`

建议先把对话上下文、已选文档、当前请求归并成一份 PPT 准备对象：

```ts
type PptPreparationResult = {
  ppt_intent: "generate_ppt" | "revise_ppt" | "unclear"

  deck_topic?: string
  audience?: string
  objective?: string
  key_points: string[]
  source_basis: Array<"conversation_summary" | "recent_messages" | "selected_docs" | "artifact_context">

  slide_count?: number
  template_style?: string
  visual_preference?: string
  include_notes?: boolean

  must_include: string[]
  avoid: string[]
  preferred_examples: string[]

  missing_critical_fields: string[]
  readiness: "ready_for_outline" | "needs_followup"
  followup_question?: string
  assumptions: string[]
}
```

这份对象的目标不是“把所有字段都填满”，而是回答两个问题：

1. 现在是否已经足够生成逐页大纲。
2. 如果不够，最值得追问的唯一缺口是什么。

#### 8.2.2 软槽位分层

建议把信息位拆成两层：

核心软槽位：

1. `deck_topic`
2. `audience`
3. `objective`
4. `key_points`
5. `source_basis`

弱约束槽位：

1. `slide_count`
2. `template_style`
3. `visual_preference`
4. `include_notes`
5. `must_include`
6. `avoid`
7. `preferred_examples`

设计原则：

1. 核心软槽位服务于“能不能稳定拆页”。
2. 弱约束槽位服务于“结果是否更贴合偏好”，缺失时优先用默认值和模型推断补齐。
3. 除非弱约束字段会直接影响结构正确性，否则不单独追问。

#### 8.2.3 Ready / Follow-up 判断

建议至少满足：

1. `deck_topic` 明确。
2. `audience` 和 `objective` 至少能从对话或资料里推断出稳定版本。
3. 至少有 2 到 4 个稳定的关键讲解点，足以拆成章节和页面。

其中“稳定”指的是：

1. 模型可以解释这份内容是讲给谁听的。
2. 模型可以判断应该讲到什么深度。
3. 模型可以把内容拆成多页，而不是只能产出空泛标题。

如果不满足，就停留在 `collecting_inputs` 并追问。追问规则：

1. 一次只问一个最高价值缺口。
2. 优先追问能直接影响章节拆分和页级结构的问题。
3. 不在 `content_markdown` 阶段补问，避免协议层返工。
4. 总体追问控制在 1 到 2 轮；超过后优先基于合理假设生成草案大纲。

建议优先级：

1. 缺 `deck_topic`
   - `这份 PPT 主要想讲哪个主题？`
2. 缺 `audience`
   - `这份 PPT 主要面向哪类学生或听众？`
3. 缺 `objective`
   - `你希望这份 PPT 更偏课堂讲解、汇报展示，还是复习总结？`
4. 缺稳定的逐页关键点
   - `你最希望这份 PPT 重点覆盖哪 2 到 4 个部分？`

#### 8.2.4 追问边界

以下字段不建议默认追问：

1. `slide_count`
2. `template_style`
3. `visual_preference`
4. `include_notes`

这些字段更适合：

1. 从对话中隐式提取
2. 从产品默认值补齐
3. 由模型在大纲阶段做合理假设

只有当用户明确表达了偏好，或这些偏好会显著改变结构时，才进入准备结果。

#### 8.2.5 Outline Prompt 框架

大纲质量的上限，很大程度取决于提示词是否鼓励模型“主动补全而不是机械等字段”。建议 prompt 明确以下约束：

系统目标：

1. 你要基于现有对话总结、文档摘要和用户要求，生成一份**章节级 + 逐页级** PPT 大纲。
2. 你应优先复用已有信息，尽量少追问。
3. 只有当缺失信息会直接导致逐页大纲不稳定时，才提出 1 个最高优先级追问。

输入上下文：

1. `conversation_summary`
2. `recent_relevant_messages`
3. `selected_doc_summaries`
4. `ppt_preparation_result`
5. `user_request`

生成要求：

1. 先判断信息是否足够生成逐页大纲。
2. 如果足够，输出结构化 `PptOutline`。
3. 如果不够，输出 `needs_followup=true`，并只返回一个最关键追问。
4. 对未明确但可合理推断的内容，允许在 `assumptions` 中写出假设并继续生成。
5. 每页必须给出 `role / title / goal / key_points`。
6. 大纲应优先体现教学结构、讲解节奏和认知递进，而不是平均切页。

模型行为要求：

1. 不要因为缺少风格、页数、视觉偏好就停止生成。
2. 不要把所有不确定点都变成追问。
3. 当主题、受众、目标已基本明确时，应主动归纳出 2 到 4 个关键讲解点并完成拆页。
4. 只有在主题不清、受众完全不清、目标完全不清、或内容重点无法拆页时，才允许追问。

输出建议：

```json
{
  "needs_followup": false,
  "followup_question": null,
  "assumptions": ["默认面向本科课堂讲解", "默认保留一页目录与一页结束页"],
  "outline": {
    "deck_title": "...",
    "chapters": [],
    "slides": []
  }
}
```

### 8.3 `content_markdown` 组装

`PptContentMarkdownAssembler` 的职责是：

1. 把**已确认的逐页级 `PptOutline`**组装为最终协议字符串
2. 负责固定字段顺序
3. 负责把页级 `key_points` 稳定映射为协议里的 `Blocks`
4. 负责 Notes 的收口

关键原则：

**协议格式由代码主导，不由 LLM 自由发挥。**

原因：

1. `html2ppt` 是强协议下游。
2. LLM 直接写协议文本时容易出现字段漂移。
3. 后续 revision、测试、排错都需要稳定协议文本。

## 9. `content_markdown` 校验层

在 `assembling_content_markdown` 之后，必须增加独立阶段：

`validating_content_markdown`

校验器建议至少检查：

1. `# Deck` 与 `## Slide N` 基本结构是否成立
2. 每页是否存在合法 `Role`
3. 每页是否存在 `Title`
4. 每页是否存在 `### Blocks`
5. `Role` 是否落在允许值内
6. `Media` block 是否最多一个
7. `Media.Kind`、`URL`、`Poster-URL` 是否完整且合法
8. 页码是否连续
9. 生成结果是否与 outline 页数一致

这层失败时，不应直接调用 `html2ppt`，而应在主系统内提前失败并暴露清晰错误。

## 10. `html2ppt` 适配层

### 10.1 角色定位

`Html2PptClient` 只负责基础服务通信，不负责业务组织。

它不做：

- 大纲生成
- Markdown 组装
- 用户确认逻辑

它只做：

1. `create_job`
2. `get_job_status`
3. `get_job_results`
4. `create_revision`
5. `get_revision_status`

### 10.2 建议接口

```ts
type Html2PptClient = {
  createJob(input: {
    content_markdown: string
    theme_id: string
    metadata: {
      request_id: string
      timestamp: string
      idempotency_key: string
      user_id: string
      tenant_id?: string
    }
  }): Promise<{ job_id: string; status: string }>

  getJobStatus(jobId: string): Promise<{
    job_id: string
    status: string
    phase: string
    progress: number
    message: string
    latest_revision_id?: string | null
    error?: Record<string, unknown> | null
  }>

  getJobResults(jobId: string): Promise<{
    job_id: string
    latest_revision_id: string
    theme_id: string
    results: {
      html_fragment_url: string
      html_full_url: string
      pptx_url: string
      manifest_url: string
    }
    slide_count: number
    metadata: Record<string, unknown>
  }>

  createRevision(input: {
    job_id: string
    mode: "single_slide"
    target_slides: number[]
    updated_content?: string
    user_instruction?: string
  }): Promise<{ revision_id: string; status: string }>

  getRevisionStatus(jobId: string, revisionId: string): Promise<{
    revision_id: string
    status: string
    phase: string
    progress: number
    message: string
    error?: Record<string, unknown> | null
  }>
}
```

### 10.3 错误映射

后端需要把 `html2ppt` 的错误映射为稳定上层语义，例如：

- `INVALID_REQUEST`
- `INVALID_CONTENT_FORMAT`
- `UNSUPPORTED_THEME_ID`
- `MEDIA_DOWNLOAD_FAILED`
- `AGENT_GENERATION_FAILED`
- `SERVICE_RESTARTED`

同时保留原始下游错误到 trace 中，方便排障。

## 11. Artifact 设计

### 11.1 建议 artifact 类型

第一版建议至少支持：

1. `ppt_outline`
2. `ppt_deck`

建议保留但默认不面向普通用户展示的内部 artifact：

3. `ppt_content_markdown`

### 11.2 展示策略

普通用户默认可见：

- `ppt_outline`
- `ppt_deck`

调试模式 / 高级模式可见：

- `ppt_content_markdown`

原因是：

1. 用户关心的是大纲、预览、下载。
2. `content_markdown` 更像协议中间层，不应默认增加认知负担。

## 12. 与现有 v2 响应骨架的对齐

PPT workflow 应继续返回与现有 report v2 一致的响应骨架：

```json
{
  "message": {},
  "conversation": {},
  "action": {},
  "workflow": {},
  "artifacts": [],
  "sources": [],
  "trace": {},
  "status_card": {}
}
```

这样可以最大程度复用：

1. `response_builder_v2`
2. `status_card_builder`
3. `conversation_store_adapter`
4. 前端现有右侧产物区与 workflow 展示逻辑

## 13. 建议文件分层

建议新增以下模块：

### 13.1 入口层

- `app/chat/api/routes_v2.py`
  - 新增 `POST /api/chat/v2/ppt`
- `app/chat/application/ppt_service_v2.py`
  - 显式 PPT workflow 启动入口

### 13.2 请求归一化层

- `app/chat/application/ppt_request_normalizer.py`
  - 把对话入口和显式入口统一整理成 `PptWorkflowRequest`

### 13.3 Workflow 编排层

- `app/chat/workflows/ppt/runtime.py`
  - `PptWorkflowRuntime`

### 13.4 中间产物构建层

- `app/chat/workflows/ppt/outline_builder.py`
- `app/chat/workflows/ppt/content_markdown_assembler.py`
- `app/chat/workflows/ppt/content_validator.py`

### 13.5 基础设施适配层

- `app/chat/workflows/ppt/html2ppt_client.py`

### 13.6 领域模型层

- `app/chat/domain/ppt_workflow_request.py`
- `app/chat/domain/ppt_outline.py`
- `app/chat/domain/ppt_artifact.py`

## 14. 与现有系统的挂接建议

### 14.1 v2 workflow registry

在 `reply_service_v2` 的 workflow registry 中新增：

- `ppt`

并让 route rules 支持：

- `generate.ppt`

### 14.2 旧链路处理

旧 `service.py` 中 `ppt -> report_agent` 的回退行为只保留临时兼容，不应继续作为正式实现。

正式实现应迁移到：

- `MainOrchestrator`
- `PptWorkflowRuntime`

### 14.3 status card

建议为 PPT 新增状态标签：

- `PPT 大纲`
- `生成 PPT 内容`
- `提交 PPT 任务`
- `导出 PPT`

便于前端在 workflow 卡片中展示具体阶段。

## 15. 实施优先级

建议按以下顺序实施：

1. 定义领域模型与 artifact schema
2. 新增显式入口 `POST /api/chat/v2/ppt`
3. 新增 `PptWorkflowRuntime`
4. 打通 `outline -> confirm -> content_markdown`
5. 接入 `Html2PptClient`
6. 接入 `ppt_deck artifact`
7. 最后把对话入口路由到正式 PPT workflow

图片能力建议作为下一阶段独立扩展：

1. 先在 `PptOutline` 中增加 `visual_hint`
2. 再补 `media_asset` 解析层
3. 最后由 assembler 映射为 `content_markdown` 里的 `Media` block

这样做的原因是：

1. 显式入口更容易快速打通主链路
2. 对话入口依赖 memory 与追问逻辑，复杂度更高
3. 先跑通显式入口可以更早验证 `outline / content_markdown / html2ppt` 这条后半程

## 16. 最终结论

PPT 接入的正确方向不是“再做一个直连 html2ppt 的接口”，而是：

1. 保留两个入口，分别服务对话场景与显式配置场景
2. 两个入口都统一归一化到 `PptWorkflowRequest`
3. 所有生成逻辑收敛到同一个 `PptWorkflowRuntime`
4. 用户确认对象是 `ppt_outline`
5. 协议输出对象是 `content_markdown`
6. 最终产物对象是 `ppt_deck artifact`
7. `html2ppt` 作为独立下游服务，由适配层统一调用

这套结构既贴合现有 chat v2 / report v2 的系统方向，也能最大限度保证 PPT 协议稳定性、前端交互一致性和后续 revision 可扩展性。
