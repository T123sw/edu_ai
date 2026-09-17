# 学习辅导 Agent 分阶段 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 按阶段顺序执行；只有用户明确要求时才采用多 agent 并行。不要把计划中的代码片段直接当作已实现接口。

**Goal:** 建立按知识点独立会话、安静陪学、可追溯学习证据及课程准备任务交接的学习 Agent。

**Architecture:** Python 学习业务服务管理会话、事实、检查和版本，学习 Agent 使用受限工具教学。复用模型网关、PostgreSQL、消息与任务基础设施；课程 manifest 和准备交接遵循准备侧单一契约。前端导航和阅读不依赖模型运行。

**Tech Stack:** 现有 Python 3.12 / FastAPI / Pydantic / SQLAlchemy / Alembic / PostgreSQL；React / TypeScript / Vite / pnpm 10.28 / Playwright；不因本计划引入新的 Agent 框架。

**Spec:** [详细技术设计 V1](../../architecture/2026-09-17-learning-agent-technical-design-cn.md)、[学习主设计](../../architecture/2026-09-17-learning-agent-design-cn.md)、[准备 Agent 具体设计](../../architecture/2026-09-17-course-preparation-agent-technical-design-cn.md)。

## Global Constraints

- 会话逻辑归属为“当前用户 + 当前课程 + 知识点稳定标识”。
- 当前请求优先于历史偏好；不自动合并其他知识点的完整聊天历史。
- 阅读事实、完成标记、用户自评和理解证据分别记录；学完不等于掌握。
- 用户全程不聊天也能继续；不按停留时间、沉默或滚动触发催促。
- 修改保留历史版本和引用；共享课程的个人修订不覆盖公共原版。
- 生产事实使用 PostgreSQL；JSON/SQLite 只能作为旧数据来源或隔离测试实现，不作为生产降级事实源。
- 既有未提交修改属于当前工作基础，不回滚、不批量格式化、不打包提交其他修改。若创建 worktree，必须显式带入本任务依赖的未提交文件，不能只用 HEAD 假定功能齐全。
- 本计划的文件名为具体落点提案；Alembic revision 依据实施时 heads 分配，下面只写迁移职责，不预设父 revision。

---

## 1. 阶段与依赖

进入 P1 前阅读[Agent 运行、工具与记忆设计 V1](../../architecture/2026-09-17-learning-agent-runtime-design-cn.md)。运行设计已补齐；P0—P6 已分阶段实现并隔离验证；学习 Agent V1 实施完成，业务环境未启用。最终证据见[P6 验收](../../acceptance/2026-09-17-learning-agent-p6-cn.md)。

| 阶段 | 交付 | 依赖 | 当前状态 |
| --- | --- | --- | --- |
| P0 | 统一契约、旧课程只读适配、状态纯函数 | 已确认产品设计 | 已实现；后续阶段已接入口 |
| P1 | 持久化知识点会话、一次导学、完整消息历史 | P0 | 已完成隔离验收；业务环境未启用 |
| P2 | 阅读、完成、自评分离；不聊天完整学习路径 | P1 | 已完成隔离验收；业务环境未启用 |
| P3 | 版本化阅读定位、异步答疑、受限工具运行 | P1/P2 | 已完成隔离验收与三个真实模型问题；业务环境未启用 |
| P4 | 检查与目标证据、可管理偏好及摘要 | P3 | 已完成隔离验收；默认关闭 |
| P5 | 准备 Agent 任务交接、通知、版本连续性 | P3/P4；准备侧真实提交接口 | 已实现、隔离验收 |
| P6 | 旧数据迁移、真实模型与并发验收、分范围切换 | P0—P5 | 已实现并完成隔离完整验收 |

P0 不改变用户流程；P1 验证会话；P2 首次形成无聊天可用闭环；P3 开始验收 Agent 教学与工具；P4/P5 分别扩展证据、资源准备。每阶段独立记录结果，失败时修复本阶段，不用后续功能掩盖未通过的基础约束。

准备侧未完成不阻塞 P0—P4：使用 LegacyCourseView 支持旧课程和版本固定的测试 manifest；不伪造准备成功。P5 可以先做契约测试，但只有真实准备任务产生可读版本才算完成。

## 2. 文件职责

| 路径（相对仓库根） | 职责 |
| --- | --- |
| `backend/src/app/self_learning/contracts.py` | Pydantic 输入、事件、资源、会话与结果契约 |
| `backend/src/app/self_learning/course_reader.py` | manifest/旧课程适配、准确版本读取及访问校验 |
| `backend/src/app/self_learning/projections.py` | 状态和下一步动作纯函数 |
| `backend/src/app/self_learning/db_models.py` | 学习新增 ORM；复用 Base，不复制现有消息表 |
| `backend/src/app/self_learning/repository.py` | 原子操作仓储协议 |
| `backend/src/app/self_learning/postgres_repository.py` | 事务、幂等、追加消息与租约实现 |
| `backend/src/app/self_learning/session_service.py` | 会话建立、历史读取和导学 |
| `backend/src/app/self_learning/progress_service.py` | 学习事件、事实及投影 |
| `backend/src/app/self_learning/turn_service.py` | 轮次接收、查询、执行和恢复 |
| `backend/src/app/self_learning/context_builder.py` | 当前阅读、历史与摘要预算装配 |
| `backend/src/app/self_learning/agent_runtime.py`、`tools.py`、`learning-role.md` | 学习角色、工具调度和输出验证 |
| `backend/src/app/self_learning/model_adapter.py`、`tool_registry.py`、`tool_dispatcher.py` | 严格模型传输、每轮挂载、工具校验与副作用日志 |
| `backend/src/app/self_learning/memory_lifecycle.py`、`summary_service.py` | 记忆 epoch、来源抑制、依赖失效及无工具摘要 |
| `backend/src/app/self_learning/check_service.py`、`memory_adapter.py` | 即时检查、既有题库/记忆适配 |
| `backend/src/app/self_learning/preparation_adapter.py`、`notifications.py` | 准备任务请求、结果关联与通知 |
| `backend/src/app/self_learning/migration.py` | 只读扫描、幂等导入、对账与切换清单 |
| `backend/src/app/api/self_learning.py` | 新契约路由及旧版本适配 |
| `frontend/src/liveLearning/learningClient.ts`、`learningState.ts` | API DTO、同步队列、服务事实状态 |
| `frontend/src/liveLearning/readingContext.ts`、`MaterialEntry.tsx` | iframe 协议、版本定位与选区 |
| `frontend/src/liveLearning/CheckCard.tsx`、`LearningNotifications.tsx` | 检查与后台通知 |
| `frontend/src/selfLearning/Classroom.tsx`、`LearningAgent.tsx` | 复用布局，通过 live props 接真实能力 |

不一次性创建空模块。每个文件随首个需要它的任务落地。预览/模拟入口与 live 入口保留显式边界，真实请求失败不能转成示例回复。

## 3. 执行与测试约定

每项任务按“行为测试失败 → 最小实现 → 定向测试通过 → 契约/相邻回归 → 更新验收记录”执行。下面代码块给出不可省略的断言与关键算法，测试中的 fixture 必须在同任务中建立，不依赖真实用户数据。完成一个任务才勾选它的步骤；不要在开始执行时批量标完成。

后端命令工作目录 `backend/src`，使用安装项目依赖的 Python 环境：

```bash
python -m pytest tests/self_learning -q
python -m pytest tests/test_self_learning.py -q
```

前端命令工作目录 `frontend`：

```bash
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec node --import tsx --test src/liveLearning/*.test.ts
pnpm exec playwright test -c playwright.live-learning.config.ts
```

新的 liveLearning TypeScript 文件需纳入类型检查配置，不能因不在旧 include 列表中而绕过检查。纯服务测试先用 SQLite/内存 fixture 验证逻辑，数据库行锁、部分唯一索引和租约竞争必须另外在隔离 PostgreSQL 上验证。缺少数据库或模型凭据时明确记录未运行，skip 不算通过。

## P0：统一契约与状态规则

### Task 0.1：课程与阅读契约

**Files:** 新增 `contracts.py`、`course_reader.py`、`tests/self_learning/test_contracts.py`、`tests/self_learning/test_course_reader.py`。

**Interfaces:** `CourseReader.read(actor, course_id, manifest_ref=None) -> CourseView`；类型至少包括 `Actor, ResourceRef, ManifestRef, CourseView, TopicView, ReadingContext`，字段依设计第 3/11 节。`TopicView.topic_id` 映射 manifest 的 `node_id`，`required` 未知时为 null。

- [x] 创建 fixture：alice/bob、两个稳定节点、同 ID 不同类型资料、v1/v2 正文、共享与个人资料；写测试验证节点重排、资源类型区分和旧版本不可读。
- [x] 执行 `python -m pytest tests/self_learning/test_contracts.py tests/self_learning/test_course_reader.py -q`，确认失败来自未实现行为。
- [x] 实现版本引用和定位判别联合；禁止额外身份字段；manifest 与 legacy 适配集中在 course_reader。

```python
def test_legacy_does_not_invent_completion_rules(legacy_reader, actor):
    view = legacy_reader.read(actor, 'course')
    assert view.source == 'legacy'
    assert view.manifest_ref is None
    assert view.completion_policy == 'unknown'

# 版本读取关键边界：读取失败返回业务错误，不回退最新。
if requested.version != loaded.version:
    raise ResourceVersionUnavailable(requested)
```

- [x] 上述两组测试通过，核对 external `node_id` / internal `topic_id` / legacy `chapter_id` 映射和准备侧 schema。

### Task 0.2：状态投影与下一步

**Files:** 新增 `projections.py`、`tests/self_learning/test_projections.py`；扩展 `contracts.py` 定义 `LearningFacts, TopicProjection, NextAction`。

**Interfaces:** `project_topic(topic: TopicView, facts: LearningFacts) -> TopicProjection`；`next_actions(course: CourseView, facts: LearningFacts, topic_id: str) -> list[NextAction]`。

- [x] 建立真实行为用例：滚到底未完成、核心完成但无证据、可选未读、空核心规则、旧版完成与新版不混用。
- [x] 运行 `python -m pytest tests/self_learning/test_projections.py -q` 验证红灯。
- [x] 实现状态纯函数；完成与证据分别计算，始终保留导航动作。

```python
def test_completion_does_not_imply_understanding(core_topic, completed_facts):
    result = project_topic(core_topic, completed_facts)
    assert result.progress == 'core_completed'
    assert result.judgment == 'unverified'

def test_scrolling_does_not_complete(core_topic, end_reached_facts):
    assert project_topic(core_topic, end_reached_facts).progress == 'in_progress'
```

- [x] 测试通过，保存 P0 验收记录；此阶段不宣称生产会话或学习流程已上线。

## P1：稳定会话与完整历史

### Task 1.1：追加消息和幂等会话仓储

**Files:** 新增 `db_models.py`、`repository.py`、`postgres_repository.py`、`tests/self_learning/test_session_repository.py`；修改 `app/database/__init__.py` 显式加载模型；新增 Alembic 学习会话/轮次迁移。

**Interfaces:** `ensure_session(actor, course_id, topic_id, introduction) -> SessionView`；`append_message(session_id, message_id, role, content, payload) -> MessageView`；`list_messages(actor, session_id, after, limit) -> MessagePage`。`MessageView` 定义稳定 ID、序号、角色、消息类型、内容与来源引用。

- [x] 测试同用户同节点重复 enter 仅一个会话/导学、bob 隔离、分页 150 轮原文完整、消息幂等和并发序号。
- [x] 执行仓储测试并记录缺少新模块的初始失败，再完成实现。
- [x] 实现数据库唯一约束与事务追加，不调用整会话 upsert；历史页游标绑定 session 并用序号排序。

```python
def test_enter_once_and_isolated(repo, alice, bob):
    first = repo.ensure_session(alice, 'course', 'a', '导学')
    again = repo.ensure_session(alice, 'course', 'a', '导学')
    other = repo.ensure_session(bob, 'course', 'a', '导学')
    assert first.session_id == again.session_id
    assert other.session_id != first.session_id
    assert len(repo.list_messages(alice, first.session_id, None, 50).items) == 1
```

- [x] 在临时数据库迁移 upgrade 并验证唯一约束；SQLite 服务测试通过后，PostgreSQL 两连接同时 enter 也只有一次导学。

### Task 1.2：会话 API、旧回答存储接入与前端恢复

**Files:** 新增 `session_service.py`、`tests/self_learning/test_session_api.py`、`frontend/src/liveLearning/learningClient.ts`；修改 `api/self_learning.py`、`self_learning/service.py`、`LiveApp.tsx`、`LearningAgent.tsx`；新增 `frontend/tests/live-learning/agent-session.spec.ts`。

**Interfaces:** `SessionService.enter/messages`；新增 POST enter、GET session 分页接口；旧同步 `answer` 通过学习仓储保存到同一个 session。前端按 session ID 缓存消息，切节点不清除其他节点缓存。

- [x] 写 API 鉴权与 E2E：进入 a→切 b→回 a→刷新，导学数与 session ID 不变；同节点换资料不新建对话。
- [x] 执行新增API和浏览器测试，记录接入期间的问题并修复。
- [x] 入口鉴权后解析稳定节点 ID；前端仅在节点变化时 enter，GET 查询不创建会话。旧历史先只读导入并记录导入完成标识，后续新消息只写新仓储。

```typescript
test('returning to a topic restores one introduction', async ({ page }) => {
  await page.goto('/#/classroom/learning-fixture');
  await page.getByRole('button', { name: '节点 A 核心文档', exact: true }).click();
  await expect(page.locator('[data-message-kind="introduction"]')).toHaveCount(1);
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await page.getByRole('button', { name: '节点 A 核心文档', exact: true }).click();
  await page.reload();
  await expect(page.locator('[data-message-kind="introduction"]')).toHaveCount(1);
});
```

- [x] 后端新用例及 `tests/test_self_learning.py` 回归通过，E2E 使用隔离课程 fixture；更新 P1 验收记录。

## P2：不聊天也能完成的学习路径

2026-09-17：代码已实现，隔离验证结果见[P2 验收](../../acceptance/2026-09-17-learning-agent-p2-cn.md)。业务功能开关默认关闭；旧数据迁移留在 P6。

### Task 2.1：版本化事件和状态事务

**Files:** 新增 `progress_service.py`、`tests/self_learning/test_progress_service.py`、`tests/self_learning/test_progress_repository.py`；扩展契约、仓储和 ORM；新增自主学习事件/状态 Alembic 迁移。

**Interfaces:** `ProgressService.record(actor, course_id, topic_id, event) -> EventReceipt` 与 `read(...) -> LearningProjection`；事件严格采用设计第 11.2 节。

- [x] 写事件重放、异载荷冲突、v1/v2 分离、撤销完成、自评修改、两设备修订冲突、同流旧位置丢弃用例。
- [x] 执行事件服务和仓储测试，验证 SQLite/PostgreSQL 行为。
- [x] 实现事件/事实/回执/outbox 同事务；重放早于 revision 检查，晚于权限检查；目标对象使用完整资源引用。

```python
def test_replay_does_not_write_twice(progress, alice, completion_event):
    first = progress.record(alice, 'course', 'a', completion_event)
    replay = progress.record(alice, 'course', 'a', completion_event)
    assert replay == first
    assert progress.read(alice, 'course').facts_revision == first.facts_revision
```

- [x] 用 PostgreSQL 并发提交相同事件验证一次写入；新测试与 P0/P1 回归通过。

### Task 2.2：阅读事件、完成操作与继续入口

**Files:** 新增 `frontend/src/liveLearning/learningState.ts`、`learningState.test.ts`、`readingContext.ts`、`readingContext.test.ts`；修改 `LiveApp.tsx`、`MaterialEntry.tsx`、`selfLearning/Classroom.tsx`、`Content.tsx`、`learningMemory.ts`；新增 `frontend/tests/live-learning/quiet-learning.spec.ts`。

**Interfaces:** 父子窗口协议遵循设计第 11.3 节；live 模式按 `EventReceipt` 更新已保存状态。读写队列按账号隔离，退出账号后不把旧事件发给新账号。

- [x] E2E 验证滚到底不完成、完成成功后显示“理解尚未验证”、跳过检查继续、失败时可导航、可选资料未读不阻止核心完成。
- [x] 验证新前端在回执前不显示已保存完成，失败保留待同步状态。
- [x] 位置事件节流，关键完成动作立即提交；本地显示“保存中/未同步”，服务确认后才显示完成。继续入口不等待模型；离线操作保留事件 ID，重连校验当前版本再补发。

```typescript
test('end of document does not mark completed', async ({ page }) => {
  await page.goto('/#/classroom/learning-fixture');
  const reader = page.frameLocator('iframe.sl-live-material');
  await reader.locator('[data-reading-end]').scrollIntoViewIfNeeded();
  await expect(page.getByText('已标记学完', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByText('资料已学完，理解尚未验证')).toBeVisible();
  await page.getByRole('button', { name: '继续学习', exact: true }).click();
});
```

- [x] 类型检查、同步队列单测及 E2E 通过；同一事实驱动 Agent 卡与文末区。尚无题目时明确检查不可用，不能点击后显示样例题。更新 P2 验收记录。

## P3：阅读定位与 Agent 答疑

### Task 3.1：准确版本读取和上下文装配

**Files:** 新增 `context_builder.py`、`resource_reader.py`；上下文测试集中在 `tests/self_learning/test_agent_runtime.py`；扩展版本读取 API；修改 `MaterialEntry.tsx`、`readingContext.ts`、`LearningAgent.tsx`。

**Interfaces:** `ContextBuilder.build(actor, turn: TurnView, budget: int) -> ContextPacket`；`ContextPacket` 包含消息、服务引用表、来源修订和预算统计。问题上下文在发送时固定，不在模型运行中随 selectedId 改变。

- [x] 测试同节点不同版本引用、选区优先、长文分块、跨节点只注入相关摘要、撤权后引用不可读。
- [x] 上下文测试与运行器集成测试通过；实际文件为 `test_agent_runtime.py`，没有单独建立计划中的 `test_context_builder.py`。
- [x] 按设计预算装配，无法定位时明确低置信位置；资料中的工具指令保持数据属性。

```python
def test_no_foreign_topic_full_history(builder, alice, turn_on_a):
    packet = builder.build(alice, turn_on_a, budget=4000)
    assert 'B 节点私聊原文标记' not in str(packet.messages)
    assert packet.citations['ctx_01'].resource_ref.version == 1
```

- [x] API/前端都验证加载的正文版本等于发送的版本；无法取得旧版时测试返回明确错误，不回退最新。

### Task 3.2：有界工具运行与持久化轮次

**运行决策补充：** 使用独立 `LearningAgentRuntime` + `LearningModelAdapter`，复用现有模型配置解析，通过独立异步 HTTP 执行 function calling（避免旧同步 failover 代理阻断底层取消）；不直接实例化工作台 HarnessRuntime，也不挂 MCP/通用 skill loader。registry、dispatcher 和 `learning_agent_tool_calls` 日志遵循运行设计第3—5节。

- [x] 先验证并修复模型适配边界：损坏 JSON、截断参数、网络中断不得执行工具；总 deadline/cancel 必须传递到底层调用，不能继承120秒固定超时却声称90秒结束。
- [x] 工具 schema/handler 同源、按模式/阶段冻结挂载；未挂载工具拒绝。所有调用尝试计预算，坏参数不转为空对象执行。
- [x] 保存只读工具意图、operation ID、结果与检查点；worker 可恢复重做只读调用。业务写入 receipt、unknown 写入对账、任务已提交但回答失败的入口属于 P4/P5，本阶段未挂载写工具。
- [x] 运行设计第11节当前适用的传输、注册与作用域用例进入 `test_model_adapter.py`、`test_agent_runtime.py`；没有修改通用网关，写任务部分成功用例留待 P4/P5。

**Files:** 新增 `turn_service.py`、`agent_runtime.py`、`tools.py`、`learning-role.md`、`tests/self_learning/test_agent_runtime.py`、服务/API 测试同样位于 `test_agent_runtime.py`；新增 `turn_repository.py`，修改 `bootstrap.py` 启动独立答疑 worker、`api/self_learning.py`；新增 `frontend/tests/live-learning/agent-turns.spec.ts`。

**实施调整：** 以独立 PostgreSQL 答疑队列承接轮次，接收、用户消息及检查点共用会话事务；不另注册通用任务队列。见[P3验收](../../acceptance/2026-09-17-learning-agent-p3-cn.md)。

**Interfaces:** `TurnService.accept/get` 采用设计第 11 节；`LearningAgentRuntime.run(context, tools, policy) -> AnswerResult`；`AnswerResult` 字段依设计第 13 节。工具只注册当前阶段真实可用工具。

- [x] 测试 answer 直接返回、按需读片段、未知工具被拒、超限退出、未知引用不被保存为有效引用、同请求异载荷 409。
- [x] 测试接收后重启恢复、租约过期重领、旧 worker 完成被拒、回答过程中切节点归属不变。
- [x] 实现 accept 短事务与 durable 执行，模型调用置于事务外；失败保留用户消息和原输入，重试不重复消息或副作用。

```python
def test_late_worker_cannot_commit(turn_repo, claimed_turn):
    old = claimed_turn
    new = turn_repo.reclaim_expired(old.turn_id)
    assert new.attempt > old.attempt
    assert not turn_repo.complete(old.turn_id, old.token, '迟到回答')
    assert turn_repo.complete(new.turn_id, new.token, '有效回答')
```

- [x] 运行新测试、现有问答回归、真实数据库重启测试；前端轮询/流式只更新原 session。至少手工验证三个真实模型问题并标明模型配置，更新 P3 验收。

## P4：理解检查、偏好与摘要

### Task 4.1：可追溯理解检查

**Files:** 新增 `check_service.py`、`tests/self_learning/test_checks.py`、`frontend/src/liveLearning/CheckCard.tsx`、`frontend/tests/live-learning/understanding-check.spec.ts`；扩展 schema/仓储/路由与必要迁移。

**Interfaces:** `CheckService.offer/submit`；`CheckView` 不包含答案，`AttemptView` 包含已保存的作答状态、评价方式、反馈与证据引用。

- [x] 写检查跳过无证据、答错不锁导航、重复提交只一个 attempt、题目版本变化、模型评价失败保留答案、无效选项拒绝的测试。
- [x] 执行 `python -m pytest tests/self_learning/test_checks.py -q` 验证失败。
- [x] 优先复用题库快照与作答；即时题单独保存。确定性客观批改按 option ID 比较，不用字符正则猜选项。

```python
def test_invalid_option_is_not_graded(checks, alice, check):
    with pytest.raises(InvalidAnswer):
        checks.submit(alice, check.session_id, check.check_id,
                      {'request_id': 'attempt-1', 'option_ids': ['outside']})
```

- [x] 验证刷新可恢复原 attempt、前端不显示未持久化的已验证状态；P0 证据规则回归通过。

### Task 4.2：偏好生命周期与摘要失效

**记忆决策补充：** 复用存储与审计，但不在学习回复结束时直接调用旧 `persist_turn` 激活抽取结果；新增显式scope处理、memory_epoch、来源抑制与依赖传播，遵循运行设计第6—8节。

- [x] 挂载 `read_learning_preferences` / `update_learning_preference`；校验当前原话、长期意图和作用域。教学 observation 在回答后校验保存，不注册独立写观察工具。
- [x] 新增 `test_memory_lifecycle.py` 覆盖删除时索引尚未清理、旧消息再次检索、旧后台摘要完成、回答正在生成四个并发情形，保证失效偏好不被重新注入。
- [x] 实现中文词项检索与稳定排序；上下文按实际tokenizer或保守字节上界计数，验证不会按中文字符数除4低估预算。
- [x] 新增 `test_summary_service.py` 验证无工具摘要、来源检查、CAS更新、保留近期完整轮次与全部原始历史；将真实模型教学质量评测纳入P6。

**Files:** 新增 `memory_adapter.py`、`tests/self_learning/test_memory_adapter.py`、`test_summary_invalidation.py`；适配 `app/chat/memory/service.py` 及已有管理 API；修改个人中心实际入口；新增 `frontend/tests/live-learning/learning-preferences.spec.ts`。

**Interfaces:** `MemoryAdapter.read(...) -> MemoryContext`、`update_preference(actor, preference_id, value, expected_revision)`、`delete_preference(actor, preference_id, expected_revision)`；摘要以来源修订 CAS 更新。

- [x] 写当前要求覆盖偏好、一次性要求不自动持久化、跨用户隔离、删除传播到缓存/摘要/索引、旧后台摘要完成不能复活偏好用例。
- [x] 记忆/摘要新增测试先观察到缺模块失败后实现；实际集中在 `test_memory_lifecycle.py`、`test_summary_service.py`，未重复建立建议文件名。
- [x] 复用已有记忆服务并补齐来源失效检查，前端提供查看、更正和删除；长对话摘要不截掉原文。

```python
def test_deleted_preference_never_reappears(memory, alice, existing_preference):
    memory.delete_preference(alice, existing_preference.id, existing_preference.revision)
    context = memory.read(alice, 'course', 'a', '解释递归')
    assert existing_preference.id not in {p.id for p in context.preferences}
    assert existing_preference.value not in context.summary
```

- [x] 已有 memory 相关回归及新 E2E 通过；验证两次摘要更新乱序不覆盖新结果，更新 P4 验收。

实施落点与实际数量见[P4验收](../../acceptance/2026-09-17-learning-agent-p4-cn.md)。新迁移 `0027`，复用共享记忆表；启用默认关闭，所有失败/修复/通过日志保留。

## P5：准备任务交接和版本连续性

### Task 5.1：准备请求适配与真实状态

**Files:** 新增 `preparation_adapter.py`、`tests/self_learning/test_preparation_adapter.py`；扩展 `tools.py`、`contracts.py`。

**Interfaces:** `PreparationAdapter.submit(actor, source_turn_id, request) -> PreparationReceipt`；外部字段完全采用准备设计第 9.2/9.3 节，包括 operation、target、origin、learning_context、overrides。

- [x] 测试解释不建任务、明确保存才提交、目标歧义不猜写入、同请求重放、提交响应丢失后恢复、共享资料个人修订。
- [x] 执行 `python -m pytest tests/self_learning/test_preparation_adapter.py -q` 确认失败。
- [x] 从当前轮次恢复用户、会话和请求范围；交给准备服务幂等接收。准备接口不可用时工具返回真实 unavailable，不模拟 succeeded。

```python
def test_replay_preserves_preparation(adapter, alice, source_turn, supplement):
    first = adapter.submit(alice, source_turn.turn_id, supplement)
    replay = adapter.submit(alice, source_turn.turn_id, supplement)
    assert first.preparation_id == replay.preparation_id
```

- [x] 对接真实准备服务运行一次补充资源任务，核对 origin/目标/权限和真实 task receipt。

### Task 5.2：通知消费与新版本阅读

**Files:** 新增 `notifications.py`、`tests/self_learning/test_notifications.py`、`test_version_continuity.py`、`frontend/src/liveLearning/LearningNotifications.tsx`、`frontend/tests/live-learning/preparation-handoff.spec.ts`；扩展数据库与上下文适配。

**Interfaces:** `NotificationService.consume(event) -> bool`、`list(actor, course_id, after=None) -> NotificationPage`、`mark_read(actor, notification_id)`；结果绑定只读准备侧 manifest，不调用旧 attach。

- [x] 测试同事件两次、旧 attempt 迟到、事件先于前端轮询、当前会话正在回答、用户已切节点、结果撤权、版本冲突。
- [x] 运行新测试验证失败。
- [x] 按事件 ID 与 attempt/revision 去重，通知与聊天分开；用户主动打开新版本时映射可靠位置，无映射明确从章节或开头恢复。

```python
def test_duplicate_notification_is_one_record(notifications, succeeded_event):
    assert notifications.consume(succeeded_event) is True
    assert notifications.consume(succeeded_event) is False
    assert len(notifications.list(succeeded_event.actor, 'course').items) == 1
```

- [x] 端到端验证后台任务期间继续答疑，结果完成不切页面、不复制旧完成标记、不重复挂资源；更新 P5 验收。

2026-09-17：P5 已完成，见 [P5 验收](../../acceptance/2026-09-17-learning-agent-p5-cn.md)。准备侧真实模型生成/修订、浏览器后台交付与 39 项最终回归通过。旧课程采用个人补充 manifest，不宣称整课 ready。

## P6：迁移与整体验收

### Task 6.1：只读预检、幂等导入和切换

**Files:** 新增 `migration.py`、`tests/self_learning/test_migration.py`；按项目 CLI 模式增加 `backend/src/app/database/migrate_self_learning_cli.py`；更新服务能力配置、旧接口兼容适配。

**Interfaces:** `scan(source) -> MigrationReport`、`import_records(report, repository) -> ImportResult`、`reconcile(report, repository) -> ReconciliationResult`；CLI 显式区分 `scan/import/reconcile`，默认只读扫描。

- [x] 构造少于/多于 100 轮的剩余旧记录、无版本完成、孤立资料、占位笔记、重复导入 fixture。
- [x] 测试旧 ID 不变、未知版本不绑定当前版本、丢失历史不补造、重跑记录数不增加。
- [x] 实现可审计导入记录与冲突清单；切换前保存并恢复验证隔离备份，按课程/用户范围启用新版能力。

```python
def test_repeat_import_is_idempotent(importer, scanned_source):
    first = importer.import_records(scanned_source)
    second = importer.import_records(scanned_source)
    assert second.created == 0
    assert second.total == first.total
    assert importer.reconcile(scanned_source).unexplained_differences == []
```

- [x] 切换后旧写入口不再接受同域独立写入；应用回退仍读新事实库，验证不会被旧 JSON 覆盖。

### Task 6.2：真实模型、多 worker 与完整用户路径

**Files:** 新增 `backend/src/tests/self_learning/test_postgres_concurrency.py`、`test_live_agent.py`、`frontend/tests/live-learning/agent-acceptance.spec.ts`；新增 `docs/acceptance/2026-09-17-learning-agent-implementation-cn.md`。

- [x] PostgreSQL 两 worker：重复 enter、同事件竞争、同节点提问竞争、租约过期迟到写入、outbox 重投。
- [x] 真实模型：当前段落解释、跨节点先修联系、换例子、即时检查、保存练习、资料修订、多候选目标、资料提示注入、无权资料、模型超时。
- [x] 浏览器：不聊天完整学习、跨节点往返、选区提问后切节点、离线补发、刷新恢复作答、后台结果到达、个人偏好删除、账号切换。

```bash
python -m pytest tests/self_learning/test_postgres_concurrency.py -m integration -q
python -m pytest tests/self_learning/test_live_agent.py -m live_integration -q
```

- [x] 保存实际测试数量、失败原因、模型与性能环境，不把 skip 算通过；按主设计 11 个场景逐项映射证据。
- [x] 更新架构索引、项目地图与验收记录。只在所有阶段门槛满足后写“学习 Agent V1 实施完成”；准备侧尚未接通或真实模型未测时单独保留未完成项。

## 4. 验收追踪

| 主设计场景 | 实现任务 |
| --- | --- |
| 1 首次导学只一次 | 1.1 / 1.2 |
| 2 知识点会话隔离与恢复 | 1.1 / 1.2 / 3.2 |
| 3 不聊天也可推进 | 2.1 / 2.2 |
| 4 阅读不催促、不自动完成 | 0.2 / 2.2 |
| 5 完成、自评、检查分离 | 2.1 / 4.1 |
| 6 选区、版本及迟到回答 | 3.1 / 3.2 |
| 7 去重与不打断 | 1.1 / 2.1 / 5.2 |
| 8 准备任务不阻塞学习 | 5.1 / 5.2 |
| 9 旧引用、个人版本连续性 | 0.1 / 5.2 / 6.1 |
| 10 权限隔离与偏好删除 | 全部服务入口 / 4.2 |
| 11 模型失败可继续学习 | 2.2 / 3.2 / 6.2 |

## 5. 本轮设计检查记录

已核对主设计约束、准备侧 manifest/交接字段、现有文件位置和前端 iframe 入口。系统默认 PATH 不是项目环境；按部署说明已找到 `/home/zxqs_ep/miniforge3/envs/edu-ai`，其中 Python 3.12、Node、pnpm 与项目依赖可用。测试使用该环境，不连接生产库试迁移。

P0 已完成 Task 0.1/0.2 的领域实现和行为测试：新增 23 项与既有学习服务 6 项，共 29 项通过。CourseReader 使用可注入、负责鉴权的读取适配器，尚未接实际 manifest 服务/API；目标理解判断保守返回 `unverified`，证据评价按 P4 实现。P0 的完成不代表 Agent 运行、数据库迁移或前端已上线。详细记录见[验收记录](../../acceptance/2026-09-17-learning-agent-implementation-cn.md)。

## 6. P1执行记录

Task 1.1/1.2 已完成，见[P1验收](../../acceptance/2026-09-17-learning-agent-p1-cn.md)。消息追加收口到轮次领取/完成事务，避免开放无约束追加；分页参数采用 `before` 从最新页向前加载。数据库迁移与新路径默认关闭，业务环境尚未启用。API/浏览器测试在接入过程中补充，仓储测试先观察到缺模块失败后实现；不把测试环境启动失败当作功能红灯证据。下一步P2，P3运行器及P4记忆仍未实现。
