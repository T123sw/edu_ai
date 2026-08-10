# 教师—学生交互回环 Phase 2：真实可用优化设计

日期：2026-08-10

状态：已确认目标，待实施

前置交付：Teacher–Student Learning Loop Phase 1、Agent Memory V2 设计

问题证据：`Edu_AI/docs/acceptance/2026-08-10-teacher-student-learning-loop-real-e2e.md`

## 0. 决策摘要

本阶段只有一个目标：让“教师发布学习任务 → 学生发现并学习 → 系统留下可信证据 → 教师看到反馈 → 双端 Agent 正确理解学习事实”这一条回环真实可用。

Phase 1 已经证明任务、事件、进度和权限可以贯通；Phase 2 不重做课程体系，也不一次性实现完整 Memory V2，而是修复真实 E2E 暴露出的三个断点：

1. **任务语义断点**：Agent 混淆课程学习任务与后台生成任务。
2. **学习事实断点**：系统把学生点击“完成”显示成未经限定的“已完成”，无法区分自报、活动证据和测评证据。
3. **产品反馈断点**：课程首页、进度文案、资源选择和历史对话恢复没有围绕同一条学习回环表达真实状态。

采用“结构化事实优先、模型只负责表达”的实现路线。课程学习状态由 `LearningService` 计算，前端与 Agent 读取同一事实源；Agent 不得依靠历史对话猜测当前学习进度。

## 1. 成功定义

当以下场景同时成立，才算“真实可用”：

- 教师能创建、发布课程学习任务，并清楚知道任务引用了哪些课程共享资源。
- 学生首页能发现待学习任务，进入任务后能打开资源、开始、继续和自报完成。
- 系统能明确区分“未开始、进行中、学生自报完成、活动证据完成、测评验证完成”，不把自报等同于掌握。
- 教师能看到班级汇总与每名课程学生的状态、证据级别、最近活动时间。
- 教师 Agent 能准确回答最新学习任务的参与人数、完成人数、完成率与证据口径。
- 学生 Agent 只能读取自己的任务和进度，并能准确说出刚完成或待完成的课程学习任务。
- 任何学习查询都不会错误调用后台生成任务工具；任何生成任务查询也不会读取课程学习进度代替后台状态。
- 刷新、重新登录和后端重启后，任务、学习证据与 Agent 回答保持一致。

## 2. 非目标

本阶段不包含：

- 完整的向量化长期个人记忆或对所有对话做 RAG 记忆召回。
- 自动生成稳定人格画像、心理画像或不可解释的“学习能力分”。
- 基于阅读时长直接推断知识点掌握度。
- 家长端、管理端、分组教学、提醒推送、截止日期和教师评分工作流。
- 用一次大规模重构替换现有课程、资源、聊天或生成任务系统。

## 3. 统一术语与不可违反的领域规则

### 3.1 三类对象必须分开

| 领域 | 统一名称 | 示例 ID | 含义 |
| --- | --- | --- | --- |
| 课程协作 | 课程学习任务 | `lt_...` | 教师发布给课程学生的学习安排 |
| 内容生产 | 后台生成任务 | `job_...` | 报告、闪卡、PPT、课堂等异步生成工作 |
| Agent 执行 | Agent 执行计划 | `logical_task_id` | 一轮 Agent 规划和工具调用过程 |

不得再使用无领域限定的“教学任务”同时表示前两类对象。界面文案、工具描述、错误码、日志字段和测试名称都必须携带领域。

ID 前缀只用于防错和诊断，真正的路由依据是结构化字段：

```python
TaskDomain = Literal["none", "course_learning", "generation_job"]
```

### 3.2 当前请求优先于历史对话

Agent 处理任务查询时按以下优先级解析：

1. 用户本轮明确提供的任务 ID。
2. 用户本轮表达中的任务领域和当前 `course_id`。
3. 当前页面传入的结构化课程学习上下文。
4. 同领域、同课程的最近引用。
5. 不允许跨领域回退。

例如，用户说“我刚完成了哪个学习任务”时，历史中的 `job_...` 不得成为候选；用户说“刚才生成闪卡的任务到哪了”时，`lt_...` 不得成为候选。

### 3.3 UI、API、Agent 共用事实源

- `LearningStore` 保存事件和进度投影。
- `LearningService` 是课程学习规则与统计的唯一实现。
- HTTP API、课程首页指标、教师学习页和 Agent 学习工具都调用 `LearningService`。
- Agent system prompt 可携带紧凑摘要，但涉及数字和任务状态的回答必须来自当轮结构化学习事实或专用只读工具。

## 4. 产品流程

### 4.1 教师端

1. 教师进入课程“学习任务”。
2. 创建草稿，填写标题和说明，从课程共享资源中搜索并选择资源。
3. 资源项必须显示类型、创建者、更新时间和短 ID；重名资源必须可区分。
4. 发布后，教师看到课程学生数、未开始、进行中、学生自报完成、有活动证据、测评验证完成和最近活动。
5. 教师可通过 Agent 查询当前课程学习情况，Agent 必须说明数据时间和完成口径。

### 4.2 学生端

1. 学生首页显示“待学习任务”数量，不再用后台生成任务数量冒充学习任务。
2. 学生进入任务后打开关联资源，系统记录 `resource_opened`；支持的资源可继续上报活动或完成证据。
3. 进度不足 100% 时显示“进行中 · N%”，不得显示“已完成 N%”。
4. 学生可点击“我已完成”，但界面明确标注这是学生自报；教师端和 Agent 同样保留该口径。
5. 学生询问 Agent 时，只能读取自己的课程学习记录，不能看到其他学生或教师私有信息。

## 5. 可信学习事实模型

### 5.1 完成口径

```python
CompletionBasis = Literal[
    "none",
    "self_reported",
    "activity_evidenced",
    "assessment_verified",
]
```

语义如下：

- `none`：没有完成声明或完成证据。
- `self_reported`：学生点击“我已完成”；系统不声称已经掌握知识点。
- `activity_evidenced`：受支持的资源产生了可核验的完成事件，例如 AI 课堂播放到末场景。
- `assessment_verified`：测评产生得分或通过结果；只有这一层可以成为知识点掌握推断的证据。

完成口径只能单调提升：`none < self_reported < activity_evidenced < assessment_verified`。重复或乱序事件不得降低现有口径。

### 5.2 事件与进度扩展

保留现有事件兼容性，并新增结构化证据：

```python
LearningEventType = Literal[
    "started",
    "resource_opened",
    "progress_updated",
    "completed",              # 兼容旧客户端，解释为 self_reported
    "resource_completed",
    "assessment_scored",
]

@dataclass(frozen=True)
class LearningEvidence:
    evidence_type: str
    source_type: str
    source_id: str
    value: float | str | bool | None
    occurred_at: str
```

`TaskProgressRecord` 增加：

- `completion_basis`
- `evidence_count`
- `last_activity_at`

旧记录迁移规则：现有 `status=completed` 统一解释为 `completion_basis=self_reported`；不得追溯推断为测评验证完成。

### 5.3 掌握度边界

本阶段不生成数值知识点掌握度。只有 `assessment_verified` 证据可以输出“已有测评证据”，其余情况一律输出“尚未测评”或“仅有学习活动/学生自报”，避免 Agent 伪造掌握结论。

## 6. Agent 任务语义与学习工具

### 6.1 教学任务契约扩展

`TeachingTaskContract` 新增：

```python
task_domain: Literal["none", "course_learning", "generation_job"] = "none"
```

状态查询的计划编译规则：

- `intent=status + task_domain=course_learning + actor_role=student` → `get_my_learning_progress`
- `intent=status + task_domain=course_learning + actor_role=teacher` → `get_course_learning_progress`
- `intent=status + task_domain=generation_job` → `query_generation_job_status`
- `task_domain=none` 且无法依据本轮消息唯一判断 → 只问一次澄清问题，不猜测。

现有 `query_task_status` 重命名为 `query_generation_job_status`；保留一版内部兼容别名，但不得继续暴露给模型。

### 6.2 专用只读工具

学生工具：

```json
{
  "name": "get_my_learning_progress",
  "arguments": {"course_id": "computational-thinking", "task_id": "lt_optional"}
}
```

返回当前学生自己的待完成、已完成、完成口径、最近活动、资源和知识点 ID。

教师工具：

```json
{
  "name": "get_course_learning_progress",
  "arguments": {
    "course_id": "computational-thinking",
    "task_id": "lt_optional"
  }
}
```

只返回当前课程的班级汇总，不把学生名单或逐人记录放进 Agent system prompt。教师需要查看学生明细时使用学习任务页面和现有教师进度 API；工具不得返回学生对话内容、个人知识库内容或其他课程数据。

### 6.3 回答约束

- 数字、任务标题、任务状态和完成口径必须逐项来自工具或结构化上下文。
- 回答教师时说明“学生自报完成”和“测评验证完成”的区别。
- 回答学生时优先给一个与当前任务资源或知识点相关的下一步，不得用旧生成任务替代学习任务。
- 工具返回空结果时说明“当前课程没有匹配的学习任务”，不得改查后台生成任务。
- 每次学习查询 trace 记录 `task_domain`、`tool_name`、`course_id`、`actor_role`、`task_id` 和事实时间；日志不记录学生对话正文。

## 7. 后端 API 与查询模型

保留 Phase 1 API，并增加课程首页与 Agent 共用的摘要接口：

```text
GET /api/courses/{course_id}/learning/overview
```

学生响应只包含自己的：

```json
{
  "pending_tasks": 1,
  "in_progress_tasks": 0,
  "self_reported_completed_tasks": 1,
  "verified_completed_tasks": 0,
  "latest_activity_at": "2026-08-10T07:26:14Z"
}
```

教师响应包含课程汇总，不默认返回学生明细。任务详情和教师进度接口继续承载明细。

所有事件继续要求幂等 `event_id`；服务端验证资源属于任务、任务属于当前课程、学生属于课程。`assessment_scored` 还必须验证来源资源确实是该任务引用的测评资源。

## 8. 前端收口

### 8.1 课程卡片

课程卡片拆分两个指标：

- 教师：`进行中学习任务`、`后台生成中`。
- 学生：`待学习任务`、`后台生成中`。

学习指标来自 `/learning/overview`，生成指标继续来自全局 job store。

### 8.2 学习任务页面

- `getProgressLabel(1)` 返回“进行中 · 1%”。
- 自报完成显示“学生自报完成”，活动证据显示“已有活动证据”，测评验证显示“测评已验证”。
- “我已完成”按钮在未开始时仍可使用，但点击前展示轻量说明：这会记录为学生自报，不代表测评通过。
- 教师资源选择器提供搜索、类型筛选和重名资源元数据。

### 8.3 Agent 对话恢复

历史对话详情加载失败时：

- 清除本次失败恢复产生的残缺当前对话状态。
- 保留新建对话和发送能力。
- 显示可关闭、可重试的局部错误，不在主页面悬挂裸 `Failed to fetch`。
- 不把未完整恢复的历史 `pending_tasks` 交给当前 Agent。

### 8.4 双角色一致性

- 登录页统一使用“平台账号”；应用只允许记住用户名，不持久化密码。
- 个人中心“可访问课程”复用课程列表/成员关系的真实数量。

## 9. 权限与隐私

| 能力 | 教师 owner/editor | 学生 viewer |
| --- | --- | --- |
| 创建、发布学习任务 | 允许 | 拒绝 |
| 查看班级汇总 | 允许 | 拒绝 |
| 查看学生明细 | 允许，仅本课程 | 只能查看自己 |
| 写入学习事件 | 拒绝代写 | 允许写自己的 |
| 调用教师学习 Agent 工具 | 允许 | 拒绝 |
| 调用学生学习 Agent 工具 | 不用于读取学生身份 | 允许读取自己 |

Agent 权限取自认证角色与课程成员关系，不接受模型参数覆盖。学生查询中即使传入其他 `student_id` 也必须忽略或拒绝。

## 10. 错误处理与降级

- 学习上下文读取失败不得中断普通聊天，但学习查询必须明确回答“学习数据暂不可用”，不得凭历史对话猜测。
- Agent 选择的工具与 `task_domain` 不匹配时返回 `TASK_DOMAIN_MISMATCH`，规划器最多重规划一次，且只能切换到同领域工具或请求澄清。
- `/learning/overview` 单课程失败时只影响该课程卡片，页面其余课程继续可用并提供重试。
- 重复学习事件返回既有投影，不重复增加证据数。
- 历史对话加载失败不得污染新的 Agent 请求。

## 11. 可观察性

新增结构化指标：

- `learning_agent_query_total{role,task_domain,tool,result}`
- `learning_task_event_total{event_type,created}`
- `learning_overview_latency_ms{role}`
- `learning_domain_mismatch_total{from_tool,to_domain}`
- `chat_history_restore_failure_total{role}`

发布门禁要求 `learning_domain_mismatch_total` 在验收数据集上为 0。

## 12. 迁移与兼容

1. SQLite 学习库以向前兼容方式增加列，启动时检测并迁移；不删除旧事件。
2. 旧 `completed` 事件和已完成投影映射为 `self_reported`。
3. 前端在后端未返回新字段时按 `completion_basis=none` 处理，但正式发布必须前后端同时上线。
4. `query_task_status` 只保留内部兼容期，不进入工具 schema；所有新 trace 使用 `query_generation_job_status`。
5. 本阶段不迁移到向量数据库，不把学习事实写入 RAG 文档。

## 13. 需求编号

| 编号 | 要求 |
| --- | --- |
| LOOP2-FR-001 | 课程学习任务、后台生成任务和 Agent 执行计划必须有独立领域语义 |
| LOOP2-FR-002 | 学生首页必须显示真实待学习任务数量 |
| LOOP2-FR-003 | 学习状态必须区分自报、活动证据和测评验证 |
| LOOP2-FR-004 | 教师必须看到班级及学生级学习反馈和证据口径 |
| LOOP2-FR-005 | 学生 Agent 必须只读取自己的课程学习事实 |
| LOOP2-FR-006 | 教师 Agent 必须读取当前课程的真实学习汇总 |
| LOOP2-FR-007 | 学习查询不得调用后台生成任务状态工具 |
| LOOP2-FR-008 | 重名资源在任务创建时必须可区分 |
| LOOP2-FR-009 | 历史对话恢复失败不得污染当前 Agent 学习判断 |
| LOOP2-FR-010 | 刷新、重新登录和后端重启后学习事实必须一致 |
| LOOP2-NFR-001 | 学习事件必须幂等且进度与完成口径单调不回退 |
| LOOP2-NFR-002 | 所有学习查询必须执行角色与课程权限校验 |
| LOOP2-NFR-003 | Agent 学习回答必须可追溯到结构化事实与工具 trace |
| LOOP2-NFR-004 | 学习首页摘要单课程失败不得阻断整个课程列表 |

## 14. 完成定义

Phase 2 完成必须同时满足：

1. 需求 LOOP2-FR-001 至 LOOP2-FR-010、LOOP2-NFR-001 至 LOOP2-NFR-004 全部有自动化或真实浏览器证据。
2. 教师真实提问“这门课最新学习任务完成情况”时，回答包含正确任务标题、课程学生数、完成数、完成率和完成口径，且 trace 不含后台生成任务工具。
3. 学生真实提问“我刚完成了什么学习任务”时，回答引用当前学生的 `lt_...` 任务，不出现历史 `job_...`。
4. 教师页面、学生页面和双端 Agent 对同一任务的状态与数字完全一致。
5. 学生直接点击完成后，所有界面与 Agent 都明确称为“学生自报完成”，不声称知识点已掌握。
6. 权限、幂等、刷新、重新登录、后端重启和对话恢复失败场景全部通过。
7. 不新增 P0/P1 回归，现有教师端生成、学生个人知识库和课程资源主链路测试继续通过。
