# 学习 Agent P3 验收：阅读定位与持久化答疑

日期：2026-09-17。代码及隔离环境验证记录；业务环境未迁移、未启用。依据[阶段计划](../superpowers/plans/2026-09-17-learning-agent-implementation-cn.md)。

## 交付与边界

- 独立学习角色、上下文装配和 function calling 循环。发送时固定用户、课程、节点、资料类型/ID/版本、位置和选区；正文按准确版本读取，旧版本不可用时明确失败，不回退最新。引用保存标题、版本、定位和内容哈希，提交前再次校验权限及来源。
- 唯一选区定位到正文 offset；课堂按 scene ID 定位。只有像素位置或不能准确匹配时标记 approximate，不声称已定位段落。初始上下文最多 24 KB，包含本节点最近最多 12 条消息和预算内的课程事实，不注入其他节点完整历史。完整历史仍保留在 P1 消息仓储中。
- 冻结挂载 4 个只读工具：`read_resource_excerpt`、`search_course_resources`、`read_course_learning_summary`、`search_learning_history`。schema 与 handler 同源，工具身份/课程范围由服务注入，资源句柄由服务签发；每次读取重新鉴权。跨节点历史仅按需检索本人短片段。未知工具、身份参数注入及无效参数均拒绝。
- 单轮最多 8 次模型请求、6 次工具调用，含一次结构修复；总 deadline 90 秒，工具等待上限 3 秒，输入序列化上限 64 KB、模型响应上限 2 MB。损坏/重复字段 JSON、截断工具参数、部分响应中断不能触发工具。最终答案允许解包完整的单个 JSON 代码围栏，工具参数仍严格 JSON。
- 模型连接使用直接异步 HTTP，取消/超时关闭本地上游连接；不经过旧同步 failover 代理。DeepSeek 备用密钥仅用于同配置端点的 HTTP 402，沿用现有主密钥优先规则，不在 400/401 或收到部分正文后切换。关闭连接不能保证模型供应商停止其服务器计算或计费。
- 接收短事务原子保存轮次、请求快照和用户消息。后台 worker 保存检查点与工具意图/结果，租约到期可接管；token fencing 拒绝旧 worker 提交。最终消息、轮次结果、outbox 同事务。取消、失败、刷新及显式重试保留原始问题；重试不重复追加用户消息。
- 新增迁移 `20260917_0026`（父版本 `0025`）：`learning_answer_runs`、`learning_agent_tool_calls`、`learning_agent_outbox`。新增 `agent-turns` 接收/列表/查询/取消/重试 API，以及准确版本资料读取 API。
- 前端显示真实执行阶段、可取消/重试、Markdown 回答和来源标题/版本；迟到回答只更新原会话。阅读和继续入口不依赖答疑成功。选区通过校验来源窗口、通道、版本和序号的 iframe 消息传入，失焦输入问题时保留选区。
- 修复阅读回归：正文就绪后才显示末尾标记；首次恢复滚动在布局阶段完成，避免延迟恢复覆盖用户滚动。课堂 iframe 固定首次恢复位置，避免阅读回调触发重载。

## 与计划的实施差异

使用应用生命周期启动的独立 PostgreSQL 答疑队列及 worker，没有向通用 `durable_job_runtime` 注册 handler。这样轮次、用户消息、检查点共享已有会话事务，避免双队列接收不一致；服务重启后仍以数据库恢复。模型配置沿用服务端解析与配置修订快照，传输独立实现，以满足真实取消要求；没有改动旧工作台网关。

上下文、工具、服务测试集中在 `test_agent_runtime.py`，未为计划中的每个建议文件名建立重复测试文件。工具 registry/dispatcher 集中在 `tools.py`。

本阶段没有写工具，因此没有业务写入 receipt、unknown 写入对账或“任务成功但回答失败”的实现；相关验收保留到 P4/P5。读取工具超时后放弃结果；已启动的本地只读文件/数据库调用可能在隔离线程内完成，但不能改动后续上下文或发布回答。没有把线程超时声称为所有底层 I/O 已物理终止。

## 验证

环境：Python 3.12、PostgreSQL 14 临时实例 `127.0.0.1:55441`；后端测试逐个独立 schema。浏览器启动独立 FastAPI fixture，使用真实学习 API/数据库与确定性认证/模型替身。真实模型测试也使用合成资料和隔离 schema。

```bash
# backend/src，LEARNING_TEST_DATABASE_URL 指向隔离库
python -m pytest tests/self_learning tests/test_self_learning.py tests/database/test_alembic_revision_chain.py -q

# frontend
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec eslint src/liveLearning src/selfLearning src/learningWorkspaceEntry.tsx
pnpm exec node --import tsx --test src/liveLearning/readingContext.test.ts src/liveLearning/learningState.test.ts src/selfLearning/learningMemory.test.ts src/liveLearning/learningClient.test.ts
pnpm exec playwright test -c playwright.learning-progress.config.ts
pnpm exec playwright test -c playwright.learning-agent.config.ts

# 仓库根；显式指定隔离数据库
PYTHONPATH=backend/src python backend/src/scripts/smoke_learning_agent.py
```

前端单测 **9 passed**，P1/P2 浏览器回归 **11 passed**，P3 浏览器 **3 passed**；局部 TypeScript 与修改范围 ESLint 通过。后端 **113 passed、1 skipped**（旧 SQLite 跨进程用例不适用，PostgreSQL 对应项通过）。实际停止并启动隔离 PostgreSQL 后，检查点保留、过期租约重新领取为 attempt 2、旧 worker 被拒，最终仅一条用户问题、一条回答和一条 outbox；见[重启记录](artifacts/learning-agent-p3-db-restart.json)。

覆盖准确旧版本/撤权、长文定位、课堂 scene 定位、跨用户及跨节点隔离、六连接幂等接收/四 worker 竞争领取、过期租约、旧 worker fencing、检查点恢复、取消中断在途模型、最终消息/outbox 事务回滚、工具预算、无效引用、历史分页、传输损坏和 402 凭证作用域。真实模型暴露的工具调用列表被执行队列清空问题已修复，并断言后续模型请求保留原始 tool_calls。

### 三个真实模型问题

模型 `deepseek-v4-pro`，配置来源 `environment`，temperature 0.2，max_tokens 2000，thinking disabled；测试不记录密钥。完整合成问题、回答、引用和耗时见[成功记录](artifacts/learning-agent-p3-real-model.json)。

| 问题 | 结果 | 模型轮数 / 工具次数 | 耗时 |
| --- | --- | --- | --- |
| 解释选中的 return/print 句子 | 结合选区解释，引用 a-core v2 与正文定位 | 1 / 0 | 4.57 秒 |
| square(3) 为什么得到 9，只给一步提示 | 最终仅给代入提示；一次结构修复 | 2 / 0 | 3.42 秒 |
| 先查阅其他课程资料再解释闭包 | 实际检索/读取，引用 b-core v2 的 make_adder 例子 | 5 / 4 | 12.99 秒 |

逐项回读：解释与合成来源一致，没有虚构完成/掌握或写入行为，第三题引用来自另一节点的已授权资料。3 个样例是 P3 连通性与教学约束冒烟，不代表全面教学质量评测。保留[初次失败记录](artifacts/learning-agent-p3-real-model-initial.json)和[定位记录](artifacts/learning-agent-p3-real-model-diagnosis.json)：围栏 JSON 导致结构失败、执行队列误清空历史 tool_calls 导致 HTTP 400；修复后以上三题通过。

## 启用和后续

`LEARNING_AGENT_V1_ENABLED=false` 默认关闭；启用要求会话存储和迁移 `0026` 可用，并依照 P1/P2 数据迁移边界操作。本轮未启用开关、未迁移业务数据库。

长期偏好、跨轮摘要压缩与失效、理解检查/目标证据属于 P4；P3 仅保留会话原始消息、每轮工作检查点及 P2 事实，不自动写长期记忆。准备 Agent 提交及结果通知属于 P5，当前没有挂载写工具，`suggested_action_ids=[]`、`observation=null`。

沿用 P2 的类型检查范围：整体旧播放器/导出链仍有原有 OpenMAIC action/quiz/PPTX 与 Markdown 声明错误，未声称全仓 TypeScript 通过。文档资料 iframe 已经浏览器验证，课堂 scene 定位已由后端测试覆盖，真实音视频课堂的浏览器播放/定位仍需 P6 综合验收；没有新增课堂浏览器 fixture。
