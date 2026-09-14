# 课程知识库 Agent 工作流程验收

**日期：** 2026-09-10  
**状态：** 自动化验收通过；2026-09-11 真实链路补充验收有条件通过  
**设计：** `docs/superpowers/specs/2026-09-10-course-knowledge-agent-workflow-design-cn.md`  
**计划：** `docs/superpowers/plans/2026-09-10-course-knowledge-agent-workflow-implementation-cn.md`

## 1. 验收目标

验证课程知识库采用“Agent 规划与恢复交互 + 确定性持久化构建”的统一流程，并覆盖新建课程和已有课程增量补充。

## 2. 必须通过的产品行为

### 新建课程

- [x] 创建课程字段通过输入框 placeholder 提供可模仿的课程名称、简介、对象和学习目标示例；
- [x] 首次构建需求输入框通过分行 placeholder 提示受众、课时、重点、资料数量、排除项和资料偏好；
- [x] 教师创建课程后，当前课程身份已设置；
- [x] 页面进入该课程的 AI 工作区，而不是停在课程详情；
- [x] 系统只排入一条课程知识库规划请求；
- [x] 请求要求先生成可审核方案且禁止直接发布；
- [x] Agent 返回简明、标准、完整三份方案；
- [x] 响应包含结构化 `knowledge_plan`、revision 和审核地址；
- [x] 点击审核地址打开对应 build 的知识库向导；
- [x] 创建方案不产生正式知识库发布版本。

### 增量补充

- [x] 增量需求输入框通过分行 placeholder 提示目标知识点、补充数量、保留范围和资料偏好；
- [x] 有 baseline 时返回 `supplement`，不返回三份重建目录；
- [x] 未选择的建议不进入执行 topics；
- [x] 保存、确认、启动和发布都阻止丢失或移动已有节点；
- [x] baseline 已变化时旧方案不能继续发布；
- [x] 版本 2 保留版本 1 的节点与已有文档关联。

### Agent 状态与权限

- [x] 无 build ID 时 query 使用会话当前方案；
- [x] draft 返回审核状态，不声称已发布；
- [x] running 返回真实阶段和进度；
- [x] blocked/failed 返回可重试状态，但不自动重试；
- [x] 教师明确要求后可重试 failed/blocked；
- [x] succeeded 且存在 published_version 才返回完成；
- [x] 学生或无 generate 权限用户看不到或不能调用规划与重试工具；
- [x] Agent 没有确认和发布工具。

### 构建内核

- [x] 教材优先、缺口网页搜索、AI 兜底顺序保持；
- [x] AI 兜底仍受每叶节点上限和独立质量审查约束；
- [x] 图谱、覆盖、来源、索引和发布原子性门禁保持；
- [x] 质量失败不创建新发布版本；
- [x] 任务成功结果包含 quality_score、leaf_coverage 和 published_version。

## 3. 自动化验证命令

### 后端

```bash
cd backend/src
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m pytest \
  tests/services/test_course_knowledge_application.py \
  tests/services/test_course_knowledge_proposals.py \
  tests/services/test_course_knowledge_graph_incremental.py \
  tests/services/test_course_knowledge_quality_gate.py \
  tests/chat/test_course_knowledge_agent_tools.py \
  tests/chat/test_harness_runtime.py \
  tests/chat/test_schemas_v2_api.py -q
```

### 前端

```bash
cd frontend
pnpm test
pnpm build
```

### 浏览器端到端

```bash
cd frontend
pnpm exec playwright test \
  tests/e2e/course-knowledge-agent-workflow.spec.ts \
  --project=desktop1366
```

## 4. 证据记录

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 后端聚焦回归 | 通过 | 92 passed、1 deselected；另 1 个 API 权限用例因共享 PostgreSQL fixture 缺少 `teacher-a` 用户触发外键错误，见限制 |
| 新增后端契约测试 | 通过 | 应用服务 6 passed；Agent 工具/状态映射/权限/Skill 合同 12 passed |
| 前端聚焦测试 | 通过 | 课程交接、目标课程队列幂等与当前知识库向导集成 11 passed |
| 前端全量单元测试 | 有条件通过 | 488 passed、1 failed；失败为既有 `ThemeAppearanceSettings.test.ts` 与当前 `App.tsx` 外观设置挂载不一致，与本功能文件无关 |
| 前端生产构建 | 通过 | Vite 5251 modules transformed，构建成功；仅有既有 chunk 体积与动态/静态导入告警 |
| 浏览器 E2E | 通过 | `desktop1366` 1 passed（7.1s 用例，整次 12.0s）；覆盖建课、单次消息、课程 scope、审核链接和指定 build 向导 |
| 新建课程 Agent 交接 | 通过 | E2E 断言 `#ai?course_id=course-agent-new`、唯一一次 SSE 请求及课程权威字段 |
| 增量基线保护 | 通过 | proposal、graph incremental、quality gate 与 builder 聚焦回归通过 |
| 权限与完成声明 | 通过 | 学生工具隐藏；无确认/发布工具；无 `published_version` 的 succeeded 映射为不可确认完成 |

## 5. 环境与限制

- 自动化 E2E 使用可控 API/SSE fixture 时，结论仅覆盖产品集成，不代表真实模型质量或真实外网抓取成功率；
- 本次未创建真实课程、未调用真实模型、未抓取真实外网，也未启动真实发布任务，避免污染现有课程数据；
- E2E 首次增加“唯一一次请求”断言时发现开发模式下交接消息可能重复消费；最终实现将消息与目标课程绑定、等待目标工作区初始化，并以原子 consume 保证同一消息只发送一次；
- `tests/test_course_knowledge_build_workflow.py` 的 14 个用例以及 proposal 文件中的 1 个 API 权限用例，在当前环境会连接共享 PostgreSQL；fixture 写入 `course_memberships` 前未创建 `teacher-a` 用户，统一以 `fk_course_memberships_user_id_users` 外键错误结束。该失败发生在被测路由之前；纯 repository/service 替身和浏览器链路均已通过；
- 前端全量单测的唯一失败为 `src/stitch/theme/ThemeAppearanceSettings.test.ts` 对 `App.tsx` 的既有源码断言，不涉及本次课程知识库改动；
- 真实模型检查必须使用临时测试课程，不能对生产课程启动构建；
- 任何数据库测试必须使用隔离数据库或 repository 替身，不能写入生产数据；
- 当前工作区存在其他未提交功能，本验收只归因于本设计列出的文件和测试。

## 6. 2026-09-11 填写提示复验

- 聚焦单元测试：6 passed；
- 修改文件 ESLint：通过；
- 前端生产构建：通过，保留既有 chunk 体积与动态/静态导入告警；
- Playwright `desktop1366`：3 passed，覆盖创建课程后的 Agent 交接，以及首次构建和增量补充两种详细 placeholder；
- 后端聚焦回归：92 passed、2 failed。其一仍为共享 PostgreSQL fixture 缺少 `teacher-a` 用户导致的外键错误，发生在被测权限路由之前；另一项是当前并行工作区的 generation-factory Harness 测试缺少 `organizations` 状态，与本次前端提示修改无关；
- 本节所述提示复验本身未执行真实模型、真实外网抓取和真实发布；后续已经补做[操作系统课程真实端到端验收](2026-09-11-course-knowledge-real-operating-systems-cn.md)，数据链路通过，但来源权威性与教师逐项需求满足度仍为有条件通过。
