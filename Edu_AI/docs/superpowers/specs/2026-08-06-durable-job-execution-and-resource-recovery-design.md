# 教师端持久化后台任务与资源恢复设计

**状态：** 已确认，待实施计划

**日期：** 2026-08-06

**适用范围：** `Edu_AI` 教师端统一任务中心、后台生成执行器与课程资源读取

**前置文档：** `2026-08-06-teacher-p0-usability-and-job-center-design.md`
**目标：** 让后台任务真正脱离前端页面生命周期，并保证“任务完成”与“资源可读取”一致

---

## 1. 问题与证据

### 1.1 用户可见故障

教师从生成工厂提交报告后立即刷新页面。任务中心随后显示任务“已完成”，点击“打开结果”进入课程资源页，但资源页显示 0 个资源，无法看到任务结果。

任务中心还存在横向溢出：430px 宽的抽屉中，成功任务卡片可能被 Grid 的内容固有宽度撑到约 2031px，“打开结果”按钮被推到视口之外。

### 1.2 本次实例的事实

任务 `job_f448423d27ab4811` 的后端记录显示：

- 创建：2026-08-06 10:56:30；
- 后端开始：2026-08-06 10:56:30；
- 后端完成：2026-08-06 10:56:58；
- 实际执行约 27.8 秒；
- `TaskStore` 保存了完整结果载荷；
- 课程资源文件 `report-bd1afffc7221.json` 已落盘；
- 资源记录的 `owner_user_id=teacher`、`source_job_id=job_f448423d27ab4811`。

因此，这个实例中前端刷新没有终止后台线程。资源页为空的直接原因是：四条旧报告资源把对象形式的内容版本写入了顶层 `version` 字段，读取适配器执行 `int(version)` 时抛出 `TypeError`；列表函数在最外层吞掉异常并返回已经累积的空列表，导致一条旧资源损坏隐藏整个课程的全部资源。

### 1.3 当前架构仍然不满足的可靠性

现有 `background_runner` 使用 API 进程内的 daemon thread 执行闭包：

- 前端刷新或切换页面不会终止线程；
- API 进程重启、崩溃、热更新或重新部署会终止线程；
- 闭包和运行参数没有形成可重新执行的持久化命令；
- `running` 任务没有工作器租约、心跳和超时接管；
- 进程重启后不能判断任务仍在执行、已经丢失还是应该重试；
- 课程资源、短期结果表和 `EduJob` 账本之间缺少完成一致性门禁。

本设计同时修复当前资源读取故障和上述持久化执行缺口。

---

## 2. 目标与非目标

### 2.1 目标

1. 前端刷新、路由切换、关闭任务抽屉、继续对话和组件卸载不影响任务执行。
2. API 进程重启后，排队任务自动继续，租约过期的运行任务可安全恢复。
3. 任务只有在结果资源成功发布并能按当前用户重新读取后才标记 `succeeded`。
4. 单条损坏的历史资源不能让整个资源列表返回空。
5. 任务中心能精确打开 `course_id + material_type + material_id` 对应资源。
6. 重试和崩溃恢复采用至少一次执行、一次资源发布语义，不重复创建课程资源。
7. 继续使用现有认证、课程存储、`EduJob` API 和前端全局轮询，不引入新的部署依赖。
8. 所有已进入统一任务中心的长耗时资源任务最终都通过同一个持久化执行边界运行。

### 2.2 非目标

- 不在本轮引入 Celery、Redis、RabbitMQ、Kafka、SSE 或 WebSocket；
- 不把课程资源正文和附件整体迁入数据库；
- 不承诺外部模型调用绝对只发生一次；
- 不恢复生成前弹窗的临时表单 UI；
- 不增加新的资源类型或生成能力；
- 不重写模型、RAG、OpenMAIC 或视频渲染算法。

---

## 3. 方案比较与决策

### 3.1 方案 A：只修资源列表和前端入口

修复旧资源兼容、抽屉溢出和精确链接。

优点：

- 改动小；
- 可以立即解决本次“任务成功但资源页为空”。

缺点：

- daemon thread 仍会在后端重启时丢失；
- 无法满足统一后台管理的核心承诺。

### 3.2 方案 B：SQLite 持久化执行器，推荐并采用

扩展现有 `TaskStore` 为持久化执行队列，保存可序列化命令；由后端工作器领取、续租和执行；`EduJob` 继续作为对外状态账本；启动协调器负责恢复和对账。

优点：

- 不增加 Redis 等部署依赖；
- 适合当前单机或少量 API 实例；
- SQLite 的事务领取可避免多个工作器同时取得同一任务；
- 能逐类迁移现有后台生成器；
- 前端和任务 API 无需感知底层执行器变化。

缺点：

- 需要把当前不可序列化闭包改成命令处理器；
- SQLite 不适合未来的大规模分布式吞吐，但边界可替换。

### 3.3 方案 C：外部任务队列

使用 Celery、RQ 或 Dramatiq，搭配 Redis/RabbitMQ。

优点：

- 成熟的分布式调度、并发、监控和重试能力；
- 更适合多机部署。

缺点：

- 显著增加安装、部署和运维复杂度；
- 超出当前“先保证教师端基本可用”的范围。

### 3.4 已确认决策

采用方案 B，并先完成资源一致性修复。执行器接口必须保持可替换，未来接入外部队列时不修改前端、任务 API 和业务处理器契约。

---

## 4. 总体架构

```text
教师端业务页面
  │ 提交可序列化任务
  ▼
任务提交服务
  ├─ 创建 EduJob（公开状态与 owner 权限）
  └─ 写入 DurableTask（执行命令与恢复元数据）
          │
          ▼
SQLite DurableTaskStore
  │ 原子领取 / 租约 / 心跳 / 重试
  ▼
DurableJobWorker
  │
  ├─ CommandHandlerRegistry
  │    ├─ 报告 / 教案 / 博客 / 习题
  │    ├─ PPT / 闪卡 / 图谱 / 小游戏
  │    ├─ AI 课堂 / 视频导出
  │    └─ RAG 文档 / 视频入库
  │
  ├─ CourseMaterialPublisher
  │    ├─ 幂等保存
  │    └─ owner 回读验证
  │
  └─ JobCompletionCoordinator
       ├─ succeeded
       ├─ partially_succeeded
       ├─ failed
       └─ canceled

GlobalJobManager
  │ 只轮询 /api/jobs
  ▼
任务中心 ──精确 result_ref──> 课程资源详情
```

### 4.1 三个明确边界

1. **DurableTaskStore 管执行：** 哪个命令应该执行、由谁领取、是否失租、还能重试几次。
2. **EduJob 管展示：** 当前用户可见的状态、进度、错误、取消、重试关系和结果引用。
3. **Course Storage 管结果：** 最终课程资源正文、附件、版本、owner、来源任务和内容哈希。

三者使用同一个 `edu_job_id` 关联，但职责不混用。

`DurableTask.status=leased` 是执行器内部状态，对外映射为
`EduJob.status=running`，不扩展现有前端公开状态枚举。失租后重新排队时，
公开账本回到 `queued` 并记录“正在恢复”，教师不需要理解租约术语。

### 4.2 一致性原则

跨 SQLite 和文件账本无法使用单个数据库事务，因此采用可对账的状态顺序和幂等补偿：

1. 先创建 `EduJob`；
2. 再写 `DurableTask`；
3. 若第二步失败，立即把 `EduJob` 标记为 `failed`，错误码为 `TASK_ENQUEUE_FAILED`；
4. 工作器完成业务计算后先发布资源；
5. 按 owner 回读并验证资源；
6. 保存执行结果引用；
7. 最后把 `EduJob` 标记为终态；
8. 启动协调器修复崩溃点留下的孤立记录。

---

## 5. 持久化任务数据模型

在现有 SQLite `tasks` 表上做可重复迁移，保留旧结果查询兼容字段，并补充：

| 字段 | 说明 |
|---|---|
| `task_id` | 与 `edu_job_id` 相同的主键 |
| `workflow_type` | 稳定命令类型 |
| `handler_version` | 命令解释版本，默认 1 |
| `owner_user_id` | 任务所有者 |
| `course_id` | 可空课程 ID |
| `scope_type` / `scope_id` | 课程、知识点或其他范围 |
| `command_json` | 脱敏、可序列化的任务输入 |
| `config_snapshot_id` | 提交时冻结的模型配置快照 |
| `idempotency_key` | 当前 owner 下的业务幂等键 |
| `status` | `pending/leased/succeeded/partially_succeeded/failed/canceled` |
| `attempt_count` | 已领取执行次数 |
| `max_attempts` | 最大自动执行次数 |
| `available_at` | 下次可领取时间 |
| `lease_owner` | 工作器实例 ID |
| `lease_expires_at` | 租约过期时间 |
| `heartbeat_at` | 最近心跳 |
| `cancel_requested` | 合作式取消标记 |
| `progress_json` | 当前阶段、百分比和说明 |
| `result_ref_json` | 最终资源引用 |
| `result_json` | 兼容旧聊天结果读取；受 TTL 控制 |
| `error_code` / `error` | 稳定错误码和可读错误 |
| `created_at` / `started_at` / `finished_at` / `updated_at` | 生命周期时间 |

约束：

- `task_id` 唯一；
- `(owner_user_id, workflow_type, idempotency_key)` 在幂等键非空时唯一；
- `command_json` 禁止包含 API Key、Token、密码、Authorization 和服务器绝对路径；
- 原始上传文件只记录受控存储根目录内的相对标识；
- schema 迁移可重复执行，旧任务没有命令载荷时只读展示，不尝试自动恢复。

---

## 6. 任务状态机

```text
pending
  ├─ claim ─────────────> leased
  ├─ cancel ────────────> canceled
  └─ invalid command ───> failed

leased
  ├─ heartbeat ─────────> leased
  ├─ publish verified ──> succeeded
  ├─ content only ──────> partially_succeeded
  ├─ retryable error ───> pending（延迟重试）
  ├─ final error ───────> failed
  ├─ cancel observed ───> canceled
  └─ lease expired ─────> pending 或 failed
```

规则：

- 前端不得直接写状态；
- `succeeded` 只能由完成协调器写入；
- 运行中取消是合作式取消，处理器在阶段边界检查；
- 已发布资源不能因迟到的取消请求被删除；
- 正常执行路径中的终态不可改写，重试创建新任务并设置 `retry_of_job_id`；
- 启动对账是唯一例外：有确定证据表明历史 `succeeded` 的资源不存在或
  owner 无法回读时，可以通过带审计字段的修复操作降级为
  `partially_succeeded`，记录 `reconciled_from=succeeded` 和原因；不得借此
  把失败任务升级为成功；
- 自动恢复增加 `attempt_count`，但不创建新的用户可见任务 ID；
- 用户主动重试创建新 ID，保留完整审计链。

---

## 7. 工作器、租约与启动恢复

### 7.1 原子领取

工作器使用 SQLite `BEGIN IMMEDIATE` 事务：

1. 选择 `status=pending AND available_at<=now` 的最早任务；
2. 校验 owner、handler 和命令版本；
3. 写入 `status=leased`、`lease_owner`、`lease_expires_at`、`attempt_count+1`；
4. 提交事务后再执行外部模型或文件操作。

多工作器或多 API 进程只能有一个领取成功。

### 7.2 租约与心跳

- 默认租约 45 秒；
- 执行期间每 10 秒续租；
- 心跳由执行包装器负责，不依赖业务处理器主动上报；
- 业务进度更新不能替代租约心跳；
- 工作器停止领取后允许当前任务在短暂优雅关闭期继续，超时则由新进程在租约过期后接管。

### 7.3 启动恢复

应用 lifespan 启动时：

1. 执行 SQLite schema 迁移；
2. 扫描没有 `DurableTask` 的活动 `EduJob`；
3. 有可恢复命令快照时补建执行行；
4. 无命令快照的旧活动任务标记 `failed`，错误码 `LEGACY_TASK_NOT_RECOVERABLE`；
5. 把租约已过期且未达最大次数的任务重新置为 `pending`；
6. 达到最大次数的任务标记 `failed/WORKER_LOST`；
7. 对已有 `result_ref` 且资源回读成功的任务补写 `succeeded`；
8. 启动工作器循环。

### 7.4 关闭行为

- 停止领取新任务；
- 继续心跳直到优雅关闭期限；
- 不把进程关闭直接写成业务失败；
- 未完成任务等待租约过期后由下一实例恢复。

---

## 8. 可序列化命令与处理器注册表

禁止把 Python 闭包、服务实例、请求对象或数据库连接当作可恢复任务载荷。所有任务使用：

```json
{
  "workflow_type": "report_direct",
  "handler_version": 1,
  "payload": {
    "course_id": "computational-thinking",
    "scope_type": "course",
    "scope_id": null,
    "selected_doc_ids": ["doc-1"],
    "report_config": {},
    "question": "生成综述报告"
  }
}
```

处理器统一接口：

```text
validate(command, execution_context)
execute(command, execution_context) -> GenerationResult
cancel_check()
```

`execution_context` 由后端在执行时重新构造，包括：

- owner；
- 课程与范围；
- 配置 revision 快照；
- 课程存储管理器；
- 进度回调；
- 取消检查；
- `source_job_id`；
- 幂等键。

迁移范围覆盖当前统一任务中心中的长耗时任务：

- 报告、教案、教学博客、习题；
- PPT、闪卡、思维导图、小游戏；
- AI 课堂生成、课堂视频导出；
- RAG 文档导入／重建；
- 视频入库。

未迁移的工作流不得宣称支持“后端重启恢复”，也不得显示与持久化任务相同的恢复文案。

---

## 9. 至少一次执行与幂等发布

本系统承诺：

- **至少一次命令执行；**
- **同一任务最多发布一份最终课程资源；**
- **不承诺外部供应商调用只发生一次。**

原因：进程可能在外部模型已经返回、但本地事务尚未完成时崩溃。恢复后无法可靠判断供应商是否已经计费，只能重新执行。

防重复措施：

1. 资源 ID 在任务提交时确定，或由稳定幂等键派生；
2. 资源 manifest 保存 `source_job_id` 和 `idempotency_key`；
3. 发布前先按 `source_job_id` 查询已有资源；
4. 内容哈希相同则复用已有资源；
5. 内容不同且任务 ID 相同时拒绝静默覆盖，进入 `partially_succeeded` 并记录冲突；
6. 崩溃发生在“资源已保存、任务未完成”之间时，启动对账直接完成任务，不重新调用模型。

---

## 10. 资源发布与完成一致性

### 10.1 发布结果契约

业务处理器不直接宣称任务成功，只返回：

```text
GenerationResult
  content_status
  candidate_resource
  diagnostics
```

`CourseMaterialPublisher` 负责：

1. 校验 owner、课程、类型和稳定 material ID；
2. 保存正文与附件；
3. 原子发布 manifest；
4. 使用相同 owner 调用详情读取；
5. 校验 `material_id`、`material_type`、`course_id`、`source_job_id` 和内容哈希；
6. 生成标准 `result_ref`。

### 10.2 终态判定

| 条件 | 任务终态 |
|---|---|
| 内容生成成功，资源保存并回读成功 | `succeeded` |
| 内容生成成功，资源保存或回读失败，但结果载荷可短期取回 | `partially_succeeded` |
| 内容未生成 | `failed` |
| 用户取消且资源尚未发布 | `canceled` |

禁止仅根据 `artifacts[0].artifact_id` 推断资源已保存。

### 10.3 标准结果引用

```json
{
  "resource_type": "course_material",
  "course_id": "computational-thinking",
  "material_type": "report",
  "material_id": "report-bd1afffc7221",
  "source_job_id": "job_f448423d27ab4811"
}
```

课堂和视频保留各自必要字段，但仍须提供可验证的稳定资源身份。

---

## 11. 历史资源兼容与列表容错

### 11.1 根因修复

旧报告把内容版本对象写入顶层 `version`，与 v2 manifest 的整数版本发生字段冲突。修复规则：

- manifest 保留整数 `version`；
- 报告内容版本迁移为 `artifact_version`；
- 读取旧数据时，对象形式的 `version` 使用其中的 `version_number` 作为 manifest 初始版本，原对象复制到 `artifact_version`；
- 无可识别版本时使用 1，并记录兼容诊断；
- 新写入路径由 manifest 保留字段覆盖业务载荷同名字段，禁止业务数据再次覆盖 schema 字段。

### 11.2 单文件故障隔离

资源列表按文件处理：

- 单文件解析或规范化失败时记录文件名、课程、稳定错误码；
- 跳过该条并继续读取其他资源；
- API 返回可读取资源，不再因为一条旧数据返回空列表；
- 响应可通过诊断字段或服务器日志暴露跳过数量，但不向普通用户返回服务器绝对路径；
- 资源详情读取失败返回明确 404 或数据损坏错误，不伪装为空课程。

### 11.3 迁移策略

- 读时兼容不修改文件；
- 提供 dry-run 迁移报告；
- 显式 apply 后原子改写；
- 迁移前保留备份或可回滚副本；
- 不自动删除无法解析的旧资源。

---

## 12. API 行为

现有 `/api/jobs` 路径保持兼容，补充或强化：

### 12.1 提交

- 返回 202 和完整 `EduJob`；
- 同一 owner 的相同幂等键返回已有活动任务；
- 命令入队失败不得留下长期 queued 假任务。

### 12.2 列表与详情

- 列表只读 `EduJob` 公开字段；
- 详情可返回恢复次数、最近心跳和稳定错误码，不返回命令中的敏感字段；
- `succeeded` 必须有可验证 `result_ref`；
- 历史异常成功任务若资源不存在，在对账后降为 `partially_succeeded`，不继续显示完整成功。

### 12.3 取消

- queued 任务立即取消；
- leased 任务设置 `cancel_requested`；
- 处理器在模型调用前后、资源发布前和多阶段边界检查；
- 无法立即中断的供应商调用完成后，不再发布资源。

### 12.4 重试

- 只允许失败、部分成功和被判定不可恢复的任务；
- 创建新任务 ID；
- 复制经过脱敏和校验的命令快照；
- 记录 `retry_of_job_id`；
- 重新解析文件存在性和权限，不能盲目复用失效路径。

---

## 13. 前端恢复体验

### 13.1 任务中心布局

- `.job-center-list` 使用 `grid-template-columns: minmax(0, 1fr)`；
- `.job-card`、顶部文本区和详情区显式 `min-width: 0`；
- 内容区域禁止横向滚动；
- 长标题使用省略号和 Tooltip，不改变卡片轨道宽度；
- 操作按钮始终位于抽屉可视范围；
- 任务卡片优先展示主动作，复制任务 ID 为次要动作。

### 13.2 完成任务动作

成功任务显示“查看结果”。链接必须携带：

```text
#resources?course_id=...&material_type=...&material_id=...
```

课程资源页：

1. 解析目标资源；
2. 获取资源列表；
3. 若目标不在当前列表，调用资源详情接口；
4. 自动选择目标资源并滚动到对应卡片；
5. 不受默认筛选、置顶或排序影响；
6. 目标不存在时显示“任务已完成，但结果资源不可读取”，提供复制任务 ID 和重试入口。

### 13.3 状态文案

- `pending`：等待后台执行；
- `leased`：后台处理中；
- 失租待恢复：任务中断，正在自动恢复；
- `partially_succeeded`：内容已生成，但资源保存或读取失败；
- `failed`：显示稳定错误说明和可重试性；
- `succeeded`：结果已保存，可打开；
- `canceled`：已取消，未发布结果。

前端刷新后只从 `/api/jobs` 和课程资源 API 恢复，不读取组件内存来决定任务状态。

---

## 14. 安全与权限

- 任务列表、详情、取消、重试和结果资源均校验 owner；
- 命令载荷提交前执行敏感字段清理；
- 工作器执行时重新校验课程和文档访问权限；
- 相对文件标识解析后必须仍位于受控存储根目录；
- 工作器日志不打印 API Key、完整命令载荷或报告正文；
- 启动恢复不能把旧任务归属给当前碰巧登录的用户；
- 无 owner 的旧执行任务默认不可自动执行，必须显式迁移。

---

## 15. 可观测性

每次任务至少记录：

- `queued_at`、`started_at`、`finished_at`；
- `attempt_count`；
- `lease_owner` 和最后心跳；
- 当前阶段和进度；
- `error_code`；
- `source_job_id`；
- `result_ref`；
- 资源发布与回读耗时；
- 是否由启动恢复或租约接管。

最低稳定错误码：

```text
TASK_ENQUEUE_FAILED
COMMAND_INVALID
HANDLER_NOT_FOUND
HANDLER_VERSION_UNSUPPORTED
WORKER_LOST
MAX_ATTEMPTS_EXCEEDED
RESOURCE_PUBLISH_FAILED
RESOURCE_VERIFY_FAILED
RESOURCE_CONFLICT
RESULT_NOT_FOUND
LEGACY_TASK_NOT_RECOVERABLE
CANCELED_BY_USER
```

---

## 16. 实施顺序

### 阶段 1：恢复当前结果可见性

1. 修复 manifest `version` 字段冲突；
2. 单文件列表容错；
3. 为本次旧报告样例增加回归测试；
4. 修复任务中心横向溢出；
5. 增加精确资源深链和自动选择。

### 阶段 2：完成一致性门禁

1. 标准化 `GenerationResult` 和 `result_ref`；
2. 发布后按 owner 回读验证；
3. 保存失败使用 `partially_succeeded`；
4. 增加资源与任务启动对账。

### 阶段 3：持久化执行器

1. 扩展 SQLite schema；
2. 实现原子领取、租约、心跳和启动恢复；
3. 建立命令处理器注册表；
4. 迁移生成工厂和对话触发的资源任务；
5. 迁移课堂、视频、RAG 和视频入库任务；
6. 删除相应页面私有轮询和不可恢复闭包提交路径。

### 阶段 4：故障演练

1. 前端刷新；
2. 多页面操作；
3. 后端优雅重启；
4. 后端强制终止；
5. 资源发布前后故障注入；
6. 多工作器并发领取；
7. 取消与恢复竞争。

---

## 17. 测试设计

### 17.1 后端单元测试

- 对象形式旧 `version` 能规范化，原内容版本保留；
- 一条损坏资源不会隐藏同目录其他资源；
- 命令载荷脱敏；
- SQLite 原子领取只允许一个工作器成功；
- 心跳续租；
- 失租任务重新入队；
- 达到最大次数后失败；
- 终态不可覆盖；
- 同一幂等键不重复创建任务；
- 同一 `source_job_id` 不重复发布资源；
- 资源回读失败不能标记成功；
- owner 不匹配不能恢复、取消、重试或读取资源。

### 17.2 后端集成测试

- 提交报告后删除请求客户端，任务继续完成；
- 工作器执行中模拟进程丢失，租约过期后接管；
- 资源已保存、终态未写入时重启，对账完成任务且不再次调用处理器；
- 多工作器同时启动只生成一个资源；
- 取消请求发生在资源发布前时不发布资源；
- `partially_succeeded` 能通过用户重试生成新任务；
- 所有已接入任务类型都使用可序列化命令，不再依赖闭包恢复。

### 17.3 前端测试

- 任务卡片长标题不造成横向溢出；
- 完成任务显示可见的“查看结果”；
- 结果链接包含课程、类型和资源 ID；
- 资源页按深链选择目标；
- 目标不在首屏列表时通过详情接口恢复；
- 目标不存在时显示一致性错误；
- 刷新后运行任务仍来自服务器；
- 新对话不移除、不重置其他后台任务。

### 17.4 真实浏览器验收

1. 提交一个可观察到运行态的报告任务；
2. 立即刷新；
3. 切换到知识库并继续普通对话；
4. 打开任务中心，确认同一 ID 继续更新；
5. 完成后点击“查看结果”；
6. 资源中心自动选中正确报告；
7. 在 1280、1440、1920px 下确认无横向滚动。

### 17.5 重启恢复验收

1. 提交慢任务并确认进入 `leased`；
2. 终止 API 进程；
3. 重启 API；
4. 等待旧租约过期；
5. 确认任务进入恢复状态并由新工作器领取；
6. 最终只有一份资源；
7. `attempt_count` 和恢复原因可查；
8. 任务中心无需保留原浏览器页面即可恢复。

---

## 18. 验收标准

以下条件全部满足才可宣称修复完成：

- 本次 `report-bd1afffc7221` 和同目录正常资源能被课程资源 API 返回；
- 四条旧报告版本记录不再使资源列表整体为空；
- 任务中心在常见桌面宽度下 `scrollWidth <= clientWidth`；
- “查看结果”精确打开对应资源；
- 前端刷新、切页、继续对话不会影响任务；
- 后端重启后 pending 和失租任务可恢复；
- 资源发布后崩溃不会重复生成第二份资源；
- 资源回读失败时任务不是 `succeeded`；
- 所有任务、资源和恢复动作保持 owner 隔离；
- 自动化测试、生产构建和真实浏览器故障演练通过。

---

## 19. 风险与控制

| 风险 | 控制 |
|---|---|
| 恢复导致外部模型重复计费 | 明确至少一次语义；优先对账已有资源；记录 attempt |
| SQLite 多进程竞争 | `BEGIN IMMEDIATE` 原子领取；短事务；外部调用不持有事务 |
| 双存储状态不一致 | 固定写入顺序；启动对账；终态幂等 |
| 旧命令无法反序列化 | handler version；不支持时明确失败，不猜测执行 |
| 旧资源字段冲突 | 读时兼容、写时保留字段保护、显式迁移 |
| 取消晚于资源发布 | 已发布资源不删除；任务完成优先于迟到取消 |
| 工作器无限重试 | 最大次数、指数退避、稳定错误码 |
| 改动范围过大 | 分四阶段提交，每阶段有独立回归和回滚点 |

---

## 20. 最终产品语义

统一任务中心不是“把前端轮询集中到一个抽屉”，而是服务端后台执行能力的可视入口。

教师提交任务后可以刷新、切换课程、继续对话或关闭当前页面。只要后端服务可用，任务就继续；后端进程异常后，任务由持久化命令和租约机制恢复。系统只有在结果资源真实保存且当前教师能够重新读取时才显示“已完成”，并能从任务中心精确打开该资源。
