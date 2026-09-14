# 课程知识库 Agent 工作流程设计

**日期：** 2026-09-10  
**状态：** 已批准，进入实施  
**范围：** 新建课程的知识库规划交接、课程知识库增量规划、Agent 状态查询与失败重试、结构化审核入口；不重写解析、索引、质量门禁和发布内核。

## 1. 目标

教师创建课程后，不再先进入课程详情再寻找“一键构建”入口。系统把当前课程上下文交给教师工作台 Agent，由 `edu-course-knowledge` Skill 根据自然语言和课程元数据生成课程目录方案；已有课程则分析现有目录和资料覆盖，生成仅针对所选知识点的补充清单。

Agent 负责理解和推进，正式构建仍由持久化任务执行。教师必须在可视化页面检查并确认当前修订版目录，模型没有确认或发布权限。

本阶段的成功标准：

1. 每个通过教师端新建的课程都会自动进入本课程的 Agent 工作区，并发送一次课程知识库规划请求；
2. Agent 方案返回结构化 `knowledge_plan`、版本绑定的审核地址和 `awaiting_confirm` 状态；
3. Agent 能查询真实构建状态，并在教师明确要求时重试失败或阻塞的构建；
4. 新建与增量规划共用同一应用服务和数据库状态，不由工具直接调用 FastAPI route；
5. 增量基线保护、人工确认、质量门禁和原子发布保持不变；
6. 失败、刷新或重复请求不会让模型把“已规划”误报成“已发布”。

## 2. 不在本阶段处理的内容

- 不把教材解析、网页抓取、文件写入、RAG 索引或数据库发布暴露为 Agent 自由工具；
- 不让 Agent 自动选择三档大纲或自动确认目录；
- 不让 Agent 自动重试失败构建；只有教师当前消息明确要求重试时才允许；
- 不重写现有 `course_knowledge_plan_builder` 的完整 Step/Attempt 持久化模型；
- 不恢复已经从主向导移除的固定模块数、固定叶节点数和完全重建表单；
- 不在创建课程事务中同步调用模型。课程创建必须保持快速，Agent 交接失败不能回滚已创建课程。

## 3. 方案比较

### 方案 A：纯 Agent 执行全部构建

Agent 自行搜索、抓取、生成、索引和发布。灵活性最高，但长任务恢复、幂等、副作用审计、权限与发布一致性都会依赖模型调用顺序，不适合作为正式课程知识库的写路径。

### 方案 B：保留现有向导，仅增加聊天入口

改动最小，但 Agent 只能把用户送回向导，无法查询真实状态或解释失败，也无法形成跨轮闭环。

### 方案 C：Agent 前台 + 持久化执行内核（采用）

Agent Skill 负责规划、修改、状态查询和显式重试；应用服务负责权限后的业务命令；持久化工作流负责有副作用的长任务；教师页面负责目录选择、编辑与确认。这一方案能改善交互与增量判断，同时保留现有可靠性边界。

## 4. 职责边界

| 能力 | Agent Skill | 应用服务 | 持久化工作流 / 数据库 | 教师 UI |
| --- | --- | --- | --- | --- |
| 判断新建或补充 | 是 | 提供 baseline 和资料快照 | 保存版本 | 展示结果 |
| 理解自然语言要求 | 是 | 校验长度和身份 | 保存原始 requirements | 可继续修改 |
| 生成三档目录/补充清单 | 调用工具 | 调用模型、结构校验、独立审查 | 保存 proposal 与 revision | 选择项目 |
| 上传教材 | 否 | 暂存并提交解析任务 | 解析、记录状态 | 选择文件 |
| 选择方案/编辑图谱 | 不自动 | 校验 revision | 保存草稿 | 教师操作 |
| 确认目录 | 禁止 | 校验 revision 和结构 | 记录确认人和确认版本 | 教师显式操作 |
| 抓取、索引、AI 补充 | 不直接执行 | 提交任务 | 执行并记录证据 | 显示进度 |
| 查询构建 | 是 | 返回授权后的状态投影 | 状态事实来源 | 显示自然语言结果 |
| 重试失败构建 | 仅明确请求 | 校验状态并入队 | 重跑现有任务、保持发布门禁 | 可在聊天或页面触发 |
| 发布 | 禁止 | 无 Agent 发布命令 | 质量通过后原子发布 | 只读结果 |

Skill 是模型的任务说明，不是权限边界或状态机。所有工具每次调用都重新校验当前用户、课程和操作权限。

## 5. 应用服务

新增聚焦的课程知识库应用服务，供 FastAPI route 和 Harness 工具共用。服务不依赖 HTTP 请求对象，也不构造用户可见文案。

核心接口：

```python
class CourseKnowledgeApplicationService:
    def create_draft(self, *, course_id: str, actor_user_id: str) -> dict: ...
    def plan(self, *, course_id: str, actor_user_id: str,
             requirements: str, build_id: str | None = None,
             expected_revision: int | None = None) -> dict: ...
    def status(self, *, course_id: str, build_id: str) -> dict: ...
    def retry(self, *, course_id: str, actor_user_id: str,
              build_id: str) -> tuple[dict, dict]: ...
```

`plan` 在没有 `build_id` 时创建草稿；修改已有方案必须提供当前 `expected_revision`。`status` 只返回 Agent 需要的最小投影，不返回教材正文、内部异常栈或未授权资料。`retry` 只接受 `blocked`/`failed` 构建，并返回最新构建投影和 job。

API route 继续使用现有依赖完成权限检查，随后调用应用服务。Harness 工具也先调用课程访问服务，再调用同一应用服务，避免从工具层直接导入 route。

## 6. Agent 工具与 Skill

工具集合：

```text
plan_course_knowledge
query_course_knowledge_build
retry_course_knowledge_build
```

### `plan_course_knowledge`

- 首次请求允许省略 `build_id` 和 `revision`；
- 修改请求必须同时携带会话中最近一次工具结果的 `build_id` 与 `revision`；
- 返回 `mode=create|supplement`、摘要、proposal、revision 和审核地址；
- 返回成功仅代表 `awaiting_review`，不能说已经更新知识库。

### `query_course_knowledge_build`

- 默认使用会话当前 `knowledge_plan.build_id`，也允许显式指定；
- 返回 `draft/queued/running/blocked/failed/succeeded`、阶段、进度、质量分和已发布版本；
- `succeeded` 且存在 `published_version` 才能表述为已更新。

### `retry_course_knowledge_build`

- 只有当前用户明确要求重试时调用；
- 仅允许 `blocked` 或 `failed`；
- 返回 `running` 状态和 job ID，但对教师只表达为“已重新开始处理”；
- 不把重试等同于成功。

Skill 的 description 改为以 `Use when...` 开头，并明确创建、补充、查询进度和重试失败四类触发条件。Skill 保持简短，结构与规划约束继续放在 `references/planning.md`。

## 7. Harness 结果契约

`ChatResponseV2` 新增可选字段：

```json
{
  "knowledge_plan": {
    "course_id": "course-...",
    "build_id": "kb-...",
    "revision": 2,
    "mode": "create",
    "status": "awaiting_review",
    "summary": "...",
    "review_url": "#knowledge?..."
  },
  "action": {
    "name": "knowledge.review",
    "href": "#knowledge?..."
  },
  "workflow": {
    "type": "course_knowledge_base",
    "status": "awaiting_confirm",
    "stage": "proposal_review"
  }
}
```

状态查询映射：

| 构建事实 | workflow.status | action.name |
| --- | --- | --- |
| draft | awaiting_confirm | knowledge.review |
| queued/running/publishing | running | knowledge.status |
| blocked/failed | failed | knowledge.retry_available |
| succeeded 且 published_version 存在 | completed | knowledge.completed |

Harness 结果投影负责生成固定、可信的审核链接和状态文案，不能依赖模型是否复述工具 JSON。模型文本可以解释方案，但不得覆盖结构化状态。

## 8. 新建课程交接

创建课程成功后：

1. 保存课程到前端课程列表并设置为当前课程；
2. 写入一次性 `queuedMessage`：`请根据刚创建课程的名称、简介、教学对象和课程目标，为这门课规划课程知识库。先生成可审核方案，不要直接发布。`；
3. 跳转到本课程 `#ai?course_id=...`；
4. ChatPanel 以普通会话模式发送消息；
5. Harness 加载 `edu-course-knowledge` 并调用规划工具；
6. 返回审核链接，教师进入现有课程知识页面完成选择、编辑和确认。

交接不进入 `generation_factory` 静默成品模式，因为知识库必须人工确认。若 Agent 请求失败，消息保留在输入框或对话中供教师重试，课程本身仍然存在。

## 9. 增量流程

应用服务创建草稿时冻结当前 `baseline_graph_version`、完整 baseline 和资料快照。已有 baseline 时，规划模型只允许：

- 给已有叶节点增加资料建议；
- 在已有章节下增加知识点；
- 保留所有旧节点、名称、类型、父子关系和原顺序；
- 只执行教师选择的补充项目。

保存草稿、确认目录、启动任务和最终发布继续执行基线版本检查。若期间发布了其他版本，本方案返回冲突，Agent 只能解释需要重新分析，不能自动覆盖。

## 10. 错误处理与恢复

- 未登录、学生角色、无课程或无 generate 权限：工具不可见或拒绝调用；
- 修改方案缺少 revision：返回非重试型参数错误，要求先查询当前方案；
- 教材仍在解析：保持 draft，提示等待或从页面移除失败教材；
- 资料快照或 baseline 变化：返回版本冲突，重新创建方案；
- 构建 blocked/failed：查询工具返回实际失败摘要；只有教师明确要求才调用 retry；
- Harness 超时：已保存的 build 不删除；下轮通过 query 恢复；
- 已成功发布：query 返回发布版本；重复查询不创建新任务。

## 11. 测试策略

### 单元与契约测试

- 应用服务：首次规划、修改规划、跨课程拒绝、状态投影、仅失败可重试；
- Agent 工具：权限、会话默认 build、无当前 build、显式重试；
- Harness 投影：规划、运行、失败、完成四类结构化结果；
- Skill 静态合同：触发描述、禁止确认/发布、查询后才能宣称完成；
- 前端：创建课程后排入一次消息并跳转当前课程 AI 工作区；
- 清理旧前端集成测试对未挂载配置步骤的断言。

### 端到端验证

使用隔离数据库、模拟可控模型/检索器和正式 HTTP/UI 路径：

1. 教师新建课程后进入 AI 工作区；
2. 自动请求生成 `create` 方案和审核链接；
3. 选择标准方案、保存并确认目录；
4. 可控来源为每个叶节点提供合格资料，任务通过质量门禁并发布版本 1；
5. 再次要求只补充一个知识点的练习，生成 `supplement` 清单；
6. 选择一个项目，确认并执行；
7. 版本 2 保留版本 1 全部节点和文档关联，并只对所选叶节点增加资料；
8. 学生不能看到或调用规划、确认、重试工具。

真实外网和真实模型仅作为可选冒烟，不作为可重复验收的硬依赖。

## 12. 可观测性与隐私

- trace 记录工具名、build ID、revision 和工具成功/失败；
- 教师回复不展示内部异常栈、模型审查提示、API key、原始数据库状态或工具参数；
- 方案和任务状态以数据库为事实来源，会话只保存最近引用；
- 验收证据不得包含真实密钥、完整私有教材正文或生产用户信息。

