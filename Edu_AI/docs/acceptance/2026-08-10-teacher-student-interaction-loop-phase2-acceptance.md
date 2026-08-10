# 教师—学生交互回环 Phase 2 验收文档

验收目标：证明“教师发布学习任务 → 学生发现并学习 → 系统记录可信证据 → 教师看到反馈 → 双端 Agent 正确理解学习事实”在真实双账号环境中完整可用。

当前状态：确定性 Agent 自动化闭环已通过；由于真实外部模型人工验收、完整前端测试、旧库迁移和部分手工降级场景没有本次证据，整体结论为不通过。

验收范围：教师—学生学习交互与 Agent 学习事实；不包含课程创建/加入链路。

## 1. 依据与基线

- 设计规格：`docs/superpowers/specs/2026-08-10-teacher-student-interaction-loop-phase2-design-cn.md`
- 实施计划：`docs/superpowers/plans/2026-08-10-teacher-student-interaction-loop-phase2.md`
- 真实 E2E 基线：`Edu_AI/docs/acceptance/2026-08-10-teacher-student-learning-loop-real-e2e.md`
- 基线结论：界面与数据链路、持久化和权限已通过；教师 Agent、学生 Agent 的学习任务语义未通过。
- 基线测试提交：`243da92`
- 基线学习任务：`lt_a2ea9f4a13644c2aad65eeb9b2b39fd0`

基线任务仅用于复现旧问题，不作为 Phase 2 通过证据。Phase 2 必须创建带 `E2E-LOOP2-` 前缀的新任务，避免历史对话和旧任务状态污染结论。

## 2. 签字规则

最终结论只允许：

- **通过**：全部 P0 门禁、全部需求编号和真实双账号 Agent 场景均有可复验证据，且没有新增 P0/P1 回归。
- **不通过**：任一必验项失败、缺少证据或只能依靠人工推测。

不使用“基本通过”“有条件通过”或“单元测试通过所以整体通过”。每个失败项必须记录阻断编号、复现步骤、实际结果和证据位置。

## 3. 验收环境记录

执行验收时，在同一次测试记录中写明：

| 字段 | 必填内容 |
| --- | --- |
| 验收提交 | 实施分支最终 HEAD 完整哈希 |
| 执行时间 | Asia/Shanghai 日期与时间 |
| 前端地址 | 实际访问地址 |
| 后端地址 | 实际 API 地址 |
| 学习数据库 | 独立 `LEARNING_DB_PATH`，不得使用生产或个人真实学习库 |
| 教师账号 | 拥有目标课程 owner/editor 权限的测试账号 |
| 学生账号 | 属于目标课程的 viewer 测试账号 |
| 课程 | 课程 ID 与名称 |
| 浏览器 | 浏览器名称和版本 |
| 模型/网关 | Agent 验收实际使用的模型与网关配置名称，不记录密钥 |

本次执行记录：

| 字段 | 实际值 |
| --- | --- |
| 验收提交 | Task 7 提交前工作树；最终提交哈希见 `task-7-report.md` 与 Git 历史 |
| 执行时间 | 2026-08-11，Asia/Shanghai |
| 前端地址 | `http://127.0.0.1:15173`（测试结束后已停止） |
| 后端地址 | `http://127.0.0.1:18001`（测试结束后已停止） |
| 学习数据库 | `Edu_AI/test-results/learning-loop/worker-0-1786379881521/learning.db` |
| 教师/学生账号 | fixture 内隔离的 `teacher` / `student` 测试账号；证据不保存密码或令牌 |
| 课程 | `computational-thinking` / 计算思维 |
| 浏览器 | 本机 Google Chrome 151，Playwright `desktop1440` |
| 模型/网关 | `deterministic-learning-e2e`；只用于自动化工具选择与结构化事实验收，不等同于真实模型人工验收 |

## 4. 需求—证据追踪矩阵

| 编号 | 验收断言 | 自动化证据 | 真实场景证据 | 初始状态 |
| --- | --- | --- | --- | --- |
| LOOP2-FR-001 | `lt_`、`job_`、`logical_task_id` 领域不可混淆 | `test_learning_task_domain.py` | 双端确定性 Agent trace | 通过 |
| LOOP2-FR-002 | 学生首页显示真实待学习任务数 | overview/API 与前端映射测试 | `02-student-home-pending.png` | 通过 |
| LOOP2-FR-003 | 自报、活动证据、测评验证口径分离 | store/service/API 测试 | `03-student-in-progress.png`、`04-student-self-reported.png` | 通过 |
| LOOP2-FR-004 | 教师看到班级汇总、逐人状态和证据口径 | service/API 权限测试 | `05-teacher-feedback.png` | 通过 |
| LOOP2-FR-005 | 学生 Agent 只读本人学习事实 | learning tool 权限测试 | `07-student-agent-history-recovery.png` 与目标后端测试 | 通过 |
| LOOP2-FR-006 | 教师 Agent 读取当前课程真实汇总 | learning tool 与 context 测试 | `06-teacher-agent-deterministic.png` 与目标后端测试 | 通过 |
| LOOP2-FR-007 | 学习查询不调用后台生成任务状态工具 | planner/executor 防错测试 | 双端确定性 Agent trace 断言 | 通过 |
| LOOP2-FR-008 | 教师可区分重名课程资源 | 前端筛选与展示测试 | 本轮 E2E 使用真实共享资源，但未构造两个重名资源 | 不通过 |
| LOOP2-FR-009 | 历史对话恢复失败不污染新 Agent 回合 | recovery 单元测试 | 17 个 guard 测试与 `07-student-agent-history-recovery.png` | 通过 |
| LOOP2-FR-010 | 刷新、重新登录、后端重启后事实一致 | 持久化/迁移测试 | E2E 重启前后 API 深比较、双端重新登录 | 通过 |
| LOOP2-NFR-001 | 事件幂等，进度与完成口径单调不回退 | learning store 测试 | 目标后端测试及 E2E API 断言 | 通过 |
| LOOP2-NFR-002 | 每次学习查询执行角色和课程权限校验 | API/tool 权限测试 | 目标后端 403 断言与 E2E API 摘要 | 通过 |
| LOOP2-NFR-003 | Agent 数字与状态可追溯到结构化事实和工具 trace | tool/trace 测试 | 双端确定性 Agent trace 与截图 | 通过 |
| LOOP2-NFR-004 | 单课程摘要失败不阻断整个课程列表 | overview 前端降级测试 | 本次没有局部失败页面证据 | 不通过 |

## 5. P0 自动化门禁

### 5.1 后端学习与 Agent 目标测试

在 `Edu_AI/api/src` 执行：

```powershell
python -m pytest -q tests/learning tests/chat/test_learning_context_injection.py tests/chat/runtime/test_learning_task_domain.py tests/chat/runtime/test_learning_agent_tools.py tests/chat/runtime/test_teaching_task_contract.py tests/chat/runtime/test_plan_compiler.py tests/chat/runtime/test_agent_tools.py tests/chat/runtime/test_agent_memory_restore.py
```

通过条件：0 failed；旧 `completed` 映射为 `self_reported`；重复事件不增加证据数；乱序事件不降低进度或完成口径；学习任务 ID 不能进入生成任务工具。

### 5.2 权限与聊天回归

在 `Edu_AI/api/src` 执行：

```powershell
python -m pytest -q tests/test_course_access.py tests/test_course_route_authorization.py tests/chat
```

通过条件：0 failed；学生不能读取班级汇总，教师不能代学生写学习事件，其他课程和其他学生数据不可见。

### 5.3 前端测试、规范与构建

在 `Edu_AI` 执行：

```powershell
npm test
npm run lint
npm run build
```

通过条件：测试 0 failed，lint 0 errors，生产构建成功。

### 5.4 浏览器 E2E

在 `Edu_AI` 执行：

```powershell
npx playwright test tests/e2e/teacher-student-learning-loop.spec.ts --project=desktop1440
```

通过条件：0 retries 后通过；失败时保留 screenshot、trace 和关键 API 响应摘要，禁止仅靠重跑掩盖不稳定问题。

## 6. 真实双账号主场景

### 6.1 数据准备

1. 使用独立学习数据库启动服务。
2. 选取教师可编辑且测试学生已加入的课程，记录课程学生数 `N`。
3. 准备两个标题相同、类型或短 ID 不同的课程共享资源。
4. 教师新建标题为 `E2E-LOOP2-<时间戳>` 的学习任务，选择其中一个重名资源并发布。
5. 记录 `task_id`；必须以 `lt_` 开头。

### 6.2 教师发布后的断言

- 资源选择器可搜索、按类型筛选，并显示资源类型、创建者、时间和短 ID。
- 教师可明确判断选中的是哪个重名资源。
- 发布后的初始汇总为：课程学生 `N`，开始 0，自报完成 0，活动证据 0，测评验证 0。
- 学生账号可以看到已发布任务；草稿对学生不可见。

### 6.3 学生学习后的断言

1. 学生首页“待学习任务”增加 1，不能由全局生成 job 数量决定。
2. 学生打开目标资源，系统记录 `resource_opened`。
3. 返回学习页后状态显示“进行中 · N%”；进度不足 100% 时不得出现“已完成 N%”。
4. 学生点击“我已完成”前看到说明：这是学生自报，不代表测评通过。
5. 完成后状态显示“学生自报完成”，`completion_basis=self_reported`。
6. 未产生测评证据时，任何页面和 Agent 均不得声称知识点已掌握或测评已通过。

### 6.4 教师反馈断言

- 教师刷新后看到开始人数 1、自报完成人数 1，对应完成率为 `1/N`。
- 逐人列表中目标学生为 100%，完成口径为“学生自报完成”，最近活动时间非空。
- 教师页面、学生页面和 API 对同一任务的状态、进度、证据口径完全一致。

## 7. 双端 Agent 必验场景

### 7.1 教师 Agent

提问：

> 这门课最新学习任务完成情况怎样？只根据系统学习记录回答，并说明完成口径。

回答必须包含：

- `E2E-LOOP2-<时间戳>` 的准确标题；
- 课程学生数 `N`、开始人数 1、自报完成人数 1、完成率 `1/N`；
- 明确说明“学生自报完成不等于测评通过或知识点掌握”；
- 数据所属课程和事实时间。

trace 必须满足：

- `task_domain=course_learning`；
- 使用 `get_course_learning_progress` 或当轮同源结构化学习上下文；
- 不出现 `query_generation_job_status`、旧 `query_task_status` 或历史 `job_...`。

### 7.2 学生 Agent

提问：

> 我刚完成了什么学习任务？结合我的学习记录告诉我下一步做什么。

回答必须包含：

- 当前学生刚完成的 `E2E-LOOP2-<时间戳>`；
- “学生自报完成”的真实口径；
- 与当前任务资源或知识点相关的一条可执行下一步建议。

回答与 trace 不得包含：

- 其他学生的身份或进度；
- 历史生成任务 `job_...`；
- 未有测评证据时的“已经掌握”“测评通过”等结论；
- 通过生成任务状态工具替代学习事实。

### 7.3 空结果与澄清

- 当前课程没有匹配学习任务时，Agent 明确说没有匹配记录，不转查后台生成任务。
- 用户只说“任务怎么样”且无法确定领域时，Agent 只进行一次领域澄清，不猜测。
- 学习上下文读取失败时，Agent 说明“学习数据暂不可用”，普通聊天仍可继续。

## 8. 权限、幂等与持久化验收

| 操作 | 期望结果 |
| --- | --- |
| 学生创建或发布学习任务 | 403 |
| 学生读取班级汇总或其他学生进度 | 403 |
| 教师代学生写学习事件 | 403 |
| 非课程成员读取课程学习数据 | 403 或 404，按现有防枚举约定 |
| 重复提交同一 `event_id` | `created=false`，进度与证据数不重复增加 |
| 完成后再提交较低进度或打开资源 | 进度仍为 100%，完成口径不回退 |
| 刷新页面和重新登录 | UI、API、Agent 事实不变 |
| 后端重启 | 任务、事件、证据口径和汇总不变 |

旧数据库迁移必须在副本上演练：旧任务数和事件数不变，旧完成记录映射为 `self_reported`，连续启动两次不重复迁移。不得使用真实用户学习库做破坏性演练。

## 9. 故障恢复与局部降级

- 人为使一门课程的 `/learning/overview` 请求失败：该课程卡显示可重试的局部不可用状态，其他课程仍正常显示。
- 人为使历史对话详情请求失败：页面不显示裸 `Failed to fetch`；可重试、可新建对话、可发送新消息。
- 恢复失败的旧对话不得把残缺 `pending_tasks` 或历史 `job_...` 带入新学习查询。
- 登录页显示“平台账号”；记住账号只恢复用户名，不在 localStorage/sessionStorage/页面源码中持久化密码。
- 个人中心“可访问课程”与当前账号实际课程列表数量一致；课程接口失败时显示“暂不可用”，不伪装成 0。

## 10. 证据清单

一次完整验收至少保存：

1. 自动化命令、退出码和测试摘要。
2. 教师发布后初始汇总截图。
3. 学生首页待学习任务数截图。
4. 学生“进行中 · N%”和“学生自报完成”截图。
5. 教师逐人反馈与证据口径截图。
6. 教师 Agent 回答、结构化事实和工具 trace。
7. 学生 Agent 回答、结构化事实和工具 trace。
8. 四类权限请求的状态码与响应摘要。
9. 后端重启前后同一任务的 API 响应对比。
10. 历史对话失败恢复和课程摘要局部降级截图。

证据文件不得包含密码、令牌、模型密钥、学生私聊正文或与目标课程无关的个人数据。

## 11. 最终验收记录

下表记录本次实际执行结果；缺少本次可复验证据的项目一律记为“不通过”。

| 门禁 | 状态 | 证据 |
| --- | --- | --- |
| 后端学习与 Agent 目标测试 | 通过 | 目标 14 passed；扩展命令 96 passed、5 warnings |
| 权限与聊天回归 | 不通过 | E2E 与目标测试覆盖关键 403，但第 5.2 节完整命令本次未跑 |
| 前端测试、lint、build | 不通过 | history guard 17 passed；lint 0 errors；build 成功；完整 `npm test` 因执行权限审批未实际启动 |
| Playwright 双账号 E2E | 通过 | `1 passed (1.2m)`，用例 46.8s，retries=0；worker `worker-0-1786379881521` |
| 教师真实 Agent | 不通过 | 自动化确定性网关通过；真实外部模型人工验收没有凭据/本次证据 |
| 学生真实 Agent | 不通过 | 自动化确定性网关通过；真实外部模型人工验收没有凭据/本次证据 |
| 刷新、重新登录、后端重启 | 通过 | 同一 E2E 内后端重启、API 重新登录、双端清理认证后 UI 登录，事实深比较一致 |
| 旧库迁移演练 | 不通过 | 没有在副本上执行旧库迁移演练 |
| 历史对话失败恢复 | 通过 | detail 固定 500 后显示友好错误，可新建对话并完成新的学生学习查询 |
| 单课程摘要局部降级 | 不通过 | 没有本次局部失败页面截图 |

最终结论：**不通过**

阻断项：`BLOCK-REAL-MODEL`（双端真实外部模型人工验收缺失）、`BLOCK-FULL-REGRESSION`（完整前端与第 5.2 回归缺少本次结果）、`BLOCK-MANUAL-SCENARIOS`（旧库迁移、重名资源、单课程摘要局部降级证据缺失）。自动化确定性 Agent 门禁和真实双账号数据闭环本身均已通过。

签字条件：第 4 节全部需求、第 5 节全部门禁和第 6—9 节真实场景均通过。
