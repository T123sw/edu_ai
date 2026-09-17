# 学习 Agent P2 验收：无需聊天的学习闭环

日期：2026-09-17。代码已实现并通过隔离环境验收；业务环境未迁移、未启用。依照[阶段计划](../superpowers/plans/2026-09-17-learning-agent-implementation-cn.md)。

## 本阶段交付

- 新增严格事件契约、`ProgressService`、PostgreSQL 事实仓储及迁移 `20260917_0024`（父版本 `0023`）。资源完整引用包括课程、类型、ID、版本；完成修订与节点自评修订独立。
- 记录打开、语义阅读位置、到达末尾、显式学完/撤销、自评/清除。阅读事实不会推导已学完，已学完和用户自评不会推导已掌握。
- 事件 ID 在用户内唯一；相同请求重放原回执，异载荷或旧对象修订返回 409。每次重试先检查当前课程、节点、资料权限与版本。流序号过期的阅读位置返回 `applied=false`，新序号可以回看更早位置。
- 事实、课程修订号、事件、回执、`learning_progress_outbox` 同事务；数据库事务锁协调不同连接/进程。outbox 仅保留待后续摘要处理的事实，不在 P2 调用模型。
- 新增 `GET /api/self-learning/courses/{course}/progress` 和 `POST /api/self-learning/courses/{course}/topics/{topic}/events`。回执的 `projection_delta` 在 V1 返回一致的完整投影，客户端按 `facts_revision` 防止迟到响应回退状态。
- 界面等待服务器回执后显示“资料已学完，理解尚未验证”；提供撤销、自评、继续学习。保存或模型失败都不阻止导航；冲突需要放弃原操作并刷新后重新选择，不自动覆盖其他设备。
- 待同步事件以“账号/课程/事件 ID”分别保存在 localStorage，避免不同标签页整包覆盖；重开页面保留原事件 ID，每次发送核对当前账号，重新进入对应课程或恢复网络后补发。新账号不会发送旧账号队列。
- iframe 协议校验来源窗口、同源、随机通道、完整资源版本和递增序号；正文位置节流，未发送的同流位置合并为最新值，保留在途请求与所有显式动作；课堂使用 scene ID。播放器核对实际版本，版本不一致显示错误并停止新阅读采集。恢复课堂按 scene ID 定位。
- 核心完成投影、可选资料跳过和下一节点推荐沿用 P0 纯函数；侧栏记忆和文末操作共用服务确认后的事实。手机端保留保存状态。

## 验证

使用 Python 3.12、PostgreSQL 14 临时实例（127.0.0.1:55441）、每个测试独立 schema；浏览器使用独立 FastAPI fixture、真实学习 API 与数据库，认证/模型确定性替身。未调用真实模型，未接触业务库。

```bash
# backend/src；LEARNING_TEST_DATABASE_URL 指向隔离测试库
python -m pytest tests/self_learning tests/test_self_learning.py tests/database/test_alembic_revision_chain.py -q

# frontend；PATH 中包含上述 Python
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec node --import tsx --test src/liveLearning/readingContext.test.ts src/liveLearning/learningState.test.ts src/selfLearning/learningMemory.test.ts src/liveLearning/learningClient.test.ts
LEARNING_TEST_DATABASE_URL=<隔离测试库> pnpm exec playwright test -c playwright.learning-progress.config.ts
```

最终结果：后端 **70 passed、1 skipped**（SQLite 不适用的跨进程用例，PostgreSQL 对应项已通过）；前端单测 **9 passed**；浏览器 **11 passed**。局部 TypeScript、修改入口 ESLint、Python 编译及 `git diff --check` 通过。多设备冲突用例追加刷新恢复提示后单独复验。后端新增测试包含迁移升级/使用/降级、事务回滚、六连接并发重放、v1/v2 隔离、撤销、自评清除、旧序号丢弃、版本变更及旧 PATCH 写入保护。浏览器涵盖滚到底不完成、真实阅读事件保存、刷新恢复、断网重试 ID 不变、模型失败、可选资料跳过、账号隔离、版本不一致、多设备冲突及 P1 历史回归。

类型验证范围说明：既有 `tsconfig.self-learning.json` 与修改入口 ESLint 使用原有范围验证。将 `MaterialEntry` 连带导入整个旧播放器/导出链时，仍出现原有 OpenMAIC action/quiz/PPTX 类型和 Markdown 声明错误；本阶段没有顺带修改这些无关模块。浏览器测试实际加载 MaterialEntry；课堂播放的语义回调和 scene ID 恢复尚无专门浏览器 fixture，需在 P3 的真实课堂上下文验收中继续验证。

## 启用边界与后续

- `LEARNING_PROGRESS_V1_ENABLED=false` 默认关闭；新环境至少先迁移至 `20260917_0024`。迁移链后续可能已有准备 Agent 的新版本，以仓库 Alembic head 为准。
- 开启后旧 `/learning` PATCH 仅接受选择和笔记，完成、自评、位置必须走事件 API；防止旧客户端绕过修订检查。开启前须处理旧客户端刷新与未同步写入。
- 旧数据只有无版本 completed/position 时不自动当作当前版本事实；保留原记录，P6 负责迁移核对。不能在已有真实学习数据的环境直接打开开关后宣称完成了历史迁移。
- 生产接入仍使用旧课程只读适配，未声明必学规则时显示“核心要求尚未定义”。显式 manifest 在服务及独立浏览器 fixture 中验证；准备 Agent 的真实 committed manifest 交接属于后续阶段。
- P2 不提供虚构检查题或自动掌握结论；检查证据、长期记忆和 outbox 消费属于 P4。后续 P3 实现准确阅读上下文、受限工具运行器和持久化答疑轮次。
