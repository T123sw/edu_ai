# 学习 Agent P1：知识点持久化会话验收

日期：2026-09-17。状态：代码与隔离环境验收完成；未在业务数据库迁移或启用。依据[分阶段计划](../superpowers/plans/2026-09-17-learning-agent-implementation-cn.md)，本阶段不包含 P3 工具运行器、P4 长期记忆或真实模型教学质量验收。

## 1. 已实现范围

- `app/self_learning/db_models.py`：学习会话唯一索引、轮次请求身份、租约及尝试 token；原始消息复用 conversation 表。
- `repository.py` / `postgres_repository.py`：事务建立会话和一次导学、完整消息追加、分页游标、同请求载荷冲突、失败重试、过期接管与迟到回答隔离。
- `session_service.py`：访问与节点校验、服务端模板导学、旧文件只读导入、原会话 ID 映射、来源哈希与记录数。GET 不创建会话。
- `api/self_learning.py`：POST `/courses/{course}/topics/{topic}/enter`、GET `/courses/{course}/topics/{topic}/session?before=...&limit=...`，以及现有同步回答的新仓储写入路径。
- `learningClient.ts` / `LearningAgent.tsx`：按用户、课程、节点缓存服务端消息，切节点恢复、分页读取、一次导学、回答及错误归属原节点。
- `postgres_conversation_repository.py`：旧整会话替换方法拒绝覆盖学习会话，防止其他工作台路径删除后重插历史。
- Alembic `20260917_0023`：两张学习索引/轮次表，依赖 `20260917_0022`；未执行在业务数据库上。

消息写入收口到 begin_turn/finish_turn 事务，未另开放任意追加 API。独立会话由稳定 ID 和数据库唯一约束共同保证，标题变化、重排及同节点换资料不影响归属。模型调用在事务外执行。

## 2. 测试环境

项目 Python 3.12 环境：`/home/zxqs_ep/miniforge3/envs/edu-ai`。PostgreSQL 使用本轮新建的临时 14 集群，端口 55441，每个测试另建随机 schema。SQLite 仅补充契约测试；PostgreSQL 并发用例实际运行。目标部署 PostgreSQL 版本上的发布检查仍须在部署前执行。

浏览器使用真正的学习服务、API 和隔离 PostgreSQL，会话不使用前端 mock；认证和模型使用明确的测试替身，不代表生产登录或真实模型已经验收。前端在 5196、fixture API 在 8016，测试退出清理其 schema。

首次 browser fixture 启动暴露旧 Config 的 `load_dotenv(override=True)` 会覆盖环境，导致测试成员写入发生外键失败并回滚。fixture 已在导入应用前禁用 dotenv 加载并显式固定测试数据库和临时存储；随后浏览器测试通过。未执行任何业务库 schema 迁移，也未启用业务环境的新会话路径。

## 3. 验证命令与结果

后端工作目录 `backend/src`：

```bash
LEARNING_TEST_DATABASE_URL='postgresql+psycopg://zxqs_ep@127.0.0.1:55441/postgres' \
  /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m pytest \
  tests/self_learning tests/test_self_learning.py \
  tests/persistence/test_postgres_conversation_repository.py \
  tests/database/test_database_foundation.py -q --tb=short
```

组合运行 **59 passed, 1 skipped**（67.31秒）。随后新增“旧仓储不能覆盖学习历史”“实际追加105轮不截断”两组用例，SQLite/PostgreSQL 共 **4 passed**；新增保护后既有 conversation 仓储回归 **2 passed**。会话来源映射补全后定向复验 session API **8 passed（12.83秒）**。后两次为重复回归，不重复计入新增用例数。唯一跳过项为 SQLite 的独立进程并发用例，对应 PostgreSQL 四进程用例实际通过。

前端工作目录 `frontend`，PATH 指向上述项目环境：

```bash
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec eslint src/liveLearning/learningClient.ts src/selfLearning/LearningAgent.tsx src/liveLearning/LiveApp.tsx
pnpm exec node --import tsx --test src/liveLearning/learningClient.test.ts
LEARNING_TEST_DATABASE_URL='postgresql+psycopg://zxqs_ep@127.0.0.1:55441/postgres' \
  pnpm exec playwright test -c playwright.learning-session.config.ts
```

类型与 lint 检查通过；分页合并测试 **2 passed**；浏览器 **3 passed（21.5秒）**。类型检查范围已纳入真实 LiveApp 和新学习客户端。

Alembic heads 为唯一 `20260917_0023`；新迁移在独立 SQLite/PostgreSQL schema 内完成 upgrade→实际会话使用→downgrade，核对列、约束和外键；既有消息表保留。`git diff --check` 通过。

## 4. 场景证据

| 场景 | 实测结果 |
| --- | --- |
| 初次/重复/并发进入 | 唯一会话，一条导学；四个独立 PostgreSQL worker 结果一致 |
| A→B→A、同节点切资料、刷新 | 浏览器恢复原会话和消息，无重复开场 |
| 节点改名重排 | API 会话 ID 不变 |
| 不同用户/未知节点/撤权 | 新旧查询均被服务重新校验，不返回其他用户记录 |
| 150轮旧历史 | 301条消息含导学，后端和浏览器分页到最早问题，无重复遗漏 |
| 实际追加105轮 | 211条消息含导学，最早问题仍可读取 |
| 同请求重放/异载荷 | 原回执复用；异问题或资料返回409，不再调用模型 |
| 同节点并发提问 | 一个成功领取，其余返回明确busy，不丢弃输入 |
| 模型失败再试 | 用户消息保留，重试不重复用户消息，成功后追加一次回答 |
| lease过期与旧worker | 新token接管，旧token不能提交；读取不依赖原进程内存 |
| 回答期间切节点 | 浏览器结果留在原节点，不改变当前目录选择 |
| 旧会话导入失败 | 事务回滚，原文件保留；原ID、日期等来源元数据可追溯 |
| 旧整会话写入器误用 | 拒绝覆盖学习历史 |

## 5. 启用与回退边界

默认 `LEARNING_SESSION_V1_ENABLED=false`，在 `.env.example` 中有说明。发布时须先备份并验证迁移到 `20260917_0023`，确认所有 API worker 已升级、停止旧学习问答写入并处理未结束请求，再在受控发布中启用。不能新旧 worker 混写同一个旧会话。

启用后课程响应携带 `sessionPersistence=true`，前端从独立会话接口读历史；旧 room 响应不再携带全课程聊天。新 API 与前端需配套发布。该开关是本阶段全实例切换开关，P6 的按课程/用户细粒度切换尚未实现。

已经导入并产生新消息后，不能简单关闭开关回到陈旧 JSON；回退须保留数据库读取适配与备份，不删除新增历史。旧文件仅作为迁移证据保留。活动中的旧请求或损坏来源会返回可诊断错误，须先核对，不强行清空旧状态。

P1 回答仍采用同步模型接口，接管重试需要客户端再提交；独立后台轮次、工具循环、取消与断线任务恢复在 P3 实现。P1 不宣称这些能力已经具备。

下一阶段为 P2：阅读事实、完成、自评分离，以及不聊天的完整学习路径。
