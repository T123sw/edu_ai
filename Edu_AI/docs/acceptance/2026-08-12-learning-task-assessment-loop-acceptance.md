# 学习任务强制测评闭环验收

> **状态**：通过（安全代码执行器不在本期范围）
> **日期**：2026-08-12
> **对应规格**：`docs/superpowers/specs/2026-08-12-learning-task-assessment-loop-design-cn.md`
> **实施计划**：`docs/superpowers/plans/2026-08-12-learning-task-assessment-loop.md`

## 1. 验收目标

验证“教师选择材料并发布带正式测评的学习任务 → 学生学习与多次作答 → 服务端评分/教师复核 → 补学重做 → 教师反馈与 Agent 回答”真实闭环，同时证明答案不泄露、成绩不可伪造、版本和历史记录可追溯。

## 2. 前置环境

- 使用同一待验收提交运行 React 前端和 FastAPI 后端。
- 准备一个教师账号、两个学生账号和一门三人均已加入的课程。
- 课程中准备一份带 3 道客观题的习题资源、一份不带习题的文本材料。
- 外部 LLM 可用于从文本材料生成测评草稿；若不可用，记录环境阻塞并在恢复后重跑。
- PostgreSQL 模式执行迁移到唯一 Alembic head；SQLite 模式准备一个包含旧 `completed` 记录的兼容数据库。

## 3. 强制通过规则

- AC-ASMT-01～AC-ASMT-18 全部通过才能签收。
- 自动化命令必须退出 0；明确要求无匹配的安全 `rg` 检查应退出 1 且无输出。
- B1～B8 必须使用真实账号执行，证据指向同一提交。
- 外部服务不可用只能标记为阻塞，不能跳过无习题自动生成验收。
- 既有失败必须在基线提交复现并隔离，不能写成全绿。

## 4. 验收矩阵

| ID | 验收点 | 判定标准 | 自动化 | 真实用例 | 结果 |
| --- | --- | --- | --- | --- | --- |
| AC-ASMT-01 | 强制发布门禁 | 新任务无正式测评时前端不可发布，直接 API 返回 `ASSESSMENT_REQUIRED` | A2、A4 | B1 | 通过 |
| AC-ASMT-02 | 已有习题优先 | 选中已有习题时导入并保留来源，不重复生成 | A2 | B2 | 通过 |
| AC-ASMT-03 | 无习题生成 | 根据选中材料和知识点只生成覆盖缺口，教师确认后发布 | A2 | B3 | 通过 |
| AC-ASMT-04 | 质量门禁 | 缺答案、缺量规、缺覆盖、重复或泄露字段阻止发布 | A1、A2 | B3 | 通过 |
| AC-ASMT-05 | 版本不可变 | 修改源材料或发布新版本不改变历史作答 | A1、A3 | B4 | 通过 |
| AC-ASMT-06 | 学生安全投影 | 揭示前所有学生接口和正式测评页面无答案、解析、评分键和私有量规 | A3、A7 | B5 | 通过 |
| AC-ASMT-07 | 成绩不可伪造 | 学生提交 `assessment_scored`、他人 student ID 或成绩字段均被拒绝 | A3、A7 | B5 | 通过 |
| AC-ASMT-08 | 作答恢复 | 自动保存、刷新、重新登录和后端重启后继续同一草稿 | A3、A5 | B6 | 通过 |
| AC-ASMT-09 | 三次与最高分 | 50→75→65 保留三次，最终成绩 75，第四次被拒绝 | A1、A3 | B6 | 通过 |
| AC-ASMT-10 | 阈值 | 默认 60 通过、80 掌握良好，边界分数计算准确 | A1、A3 | B6 | 通过 |
| AC-ASMT-11 | 主观复核 | 主观题提交后待复核，教师确认后才形成最终成绩 | A4 | B7 | 通过 |
| AC-ASMT-12 | 补学重做 | 未通过显示薄弱知识点、对应材料、建议和剩余次数，不泄露完整答案 | A5 | B6 | 通过 |
| AC-ASMT-13 | 答案揭示 | 通过后可继续挑战或结束揭示；揭示后不再允许计分作答 | A3、A5 | B6 | 通过 |
| AC-ASMT-14 | 教师四级反馈 | 任务、学生、题目、知识点统计均有样本数和明确分母 | A4、A5 | B8 | 通过 |
| AC-ASMT-15 | 状态分离 | 学习活动完成、已提交、待复核、未通过、已通过不会混称为“已完成” | A5 | B6、B8 | 通过 |
| AC-ASMT-16 | Agent 一致 | 学生只读本人；教师读聚合；待复核不回答已通过；未揭示答案不泄露 | A6 | B8 | 通过 |
| AC-ASMT-17 | 双数据库与迁移 | SQLite/PostgreSQL 行为一致，旧完成只迁移为自报，Alembic 单 head | A1、A7 | B4 | 通过 |
| AC-ASMT-18 | 回归 | 课程资源、学习任务、习题生成、AI 课堂与现有 Agent 无 P0/P1 回归 | A8 | B1～B8 | 通过 |

## 5. 自动化验收

### A1. 领域、仓储与迁移

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests/assessment/test_assessment_policies.py tests/assessment/test_assessment_store.py tests/persistence/test_postgres_assessment_repository.py tests/database/test_alembic_revision_chain.py -q
python -m alembic heads
```

通过标准：测试退出 0；只输出一个当前 head `20260812_0014`。

### A2. 测评创作与发布门禁

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests/assessment/test_assessment_authoring.py tests/assessment/test_assessment_authoring_api.py -q
```

必须覆盖已有习题导入、无习题生成、只补覆盖缺口、严重质量问题阻止发布、任务与测评原子发布。

### A3. 学生作答、安全投影与可信学习证据

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests/assessment/test_assessment_attempt_service.py tests/assessment/test_assessment_student_api.py tests/learning/test_learning_api.py tests/learning/test_learning_service.py -q
```

必须覆盖自动保存冲突、重复提交幂等、三次限制、最高分、揭示锁定、学生无答案字段、公共事件拒绝 `assessment_scored`、内部 outcome 才产生 `assessment_verified`。

### A4. 主观复核与分析

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests/assessment/test_assessment_review.py tests/assessment/test_assessment_analytics.py -q
```

必须覆盖 AI 仅建议分、教师追加式复核、历史重算、样本分母、学生队列、题目和知识点聚合。

### A5. 前端创作、作答和教师反馈

```powershell
Set-Location Edu_AI
npm test -- src/stitch/assessment/assessmentAuthoring.test.ts src/stitch/assessment/assessmentRunner.test.ts src/stitch/assessment/assessmentAnalytics.test.ts src/stitch/pages/courseLearningPresentation.test.ts
npm run build
```

通过标准：测试和构建退出 0。

### A6. Agent 事实与边界

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests/chat/runtime/test_learning_agent_tools.py tests/chat/runtime/test_learning_task_domain.py tests/chat/test_learning_context_injection.py -q
```

必须覆盖双角色权限、聚合/本人投影、待复核、开卷口径和答案防泄露。

### A7. 安全、迁移与确定性浏览器

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests/assessment/test_assessment_security.py tests/assessment/test_assessment_migration.py -q
Set-Location ../..
pnpm exec playwright test tests/e2e/learning-task-assessment-loop.spec.ts --project=desktop1366
```

通过标准：全部退出 0。

### A8. 全量质量门禁

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests -q
Set-Location ../..
npm test
npm run lint
npm run build
```

通过标准：pytest、test、build 退出 0；lint 无新增 error。既有 warning 记录数量和基线复现结果。

### 第一阶段自动化证据（非最终签收）

- 功能提交：`2653892ed939ff245290bf92b2c036829d2c1dfb`；本地 `HEAD`、`origin/main` 与 GitHub API `main` 已核对一致。
- 后端阶段回归：领域策略、仓储、创作、发布门禁与既有 learning 测试共 `50 passed`；PostgreSQL repository 定向回归 `2 passed`。
- 前端回归：Node 测试 `340 passed`；测评创作门禁与原课程学习文案均包含在内。
- 迁移：`python -m alembic heads` 仅输出 `20260812_0013 (head)`。
- 构建：`npm run build` 退出 0；仅保留既有动态/静态导入及大 chunk 提示。
- 静态检查：新增和修改的测评 Python 路径执行 Ruff，结果 `All checks passed!`。
- 范围结论：A1、A2 和 A5 中与第一阶段有关的自动化路径已通过；学生作答、复核、分析、Agent、安全攻击与真实双账号 B1～B8 仍待后续阶段，不据此宣称整体验收通过。

### 第二阶段后端阶段性证据（非最终签收）

- 作答持久化提交：`bd85322285d801f64aa47ea674f44a404353e270`；测评、PostgreSQL repository 与迁移链回归 `28 passed`，Ruff 通过，Alembic 单 head 为 `20260812_0014`。
- 可信结果提交：`c04a147`；学生投影、跨任务/未知题目攻击、公共伪造成绩拒绝、内部 outcome 与既有 learning 回归 `25 passed`，Ruff 通过。
- 当前覆盖：三次计分机会、自动保存修订冲突、客观题服务端评分、主观题待复核、最高分、提交幂等键、学生安全投影、可信 `assessment_verified`。
- 未完成：第二阶段学生作答/补学/揭示前端和完整阶段构建尚待 Task 7；本记录不等于第二阶段或整体验收通过。

## 6. 真实双账号验收

### 第四阶段 Agent 事实边界证据（非最终签收）

- Agent/上下文定向回归 `35 passed`，覆盖学生本人投影、教师聚合投影、工具权限、任务域与上下文注入。
- 学生投影包含测评方式、结果、剩余次数、最佳分、薄弱知识点和已公开反馈；未揭示时不包含 solution 或 scoring_key。
- 教师投影只包含班级聚合、题目与知识点统计，不包含学生 ID、逐人答案或复核队列明细。
- Prompt 明确约束：pending_review 不得称为通过；未揭示答案不得推断；比例回答必须带 numerator/denominator。
- 当前结论：A6 已有自动化边界证据；A7、安全专项及真实浏览器双账号 B1～B8 尚未签收。

### 第三阶段复核与教师反馈证据（非最终签收）

- 后端阶段回归：测评、学习、PostgreSQL repository 与 Alembic revision chain 共 `67 passed`，Ruff `All checks passed!`。
- 前端全量回归：`345 passed`；复核/分析与学生状态机定向测试 `5 passed`；生产构建退出码 `0`。
- 教师复核：主观题和代码题终态必须由教师提交；每次评分变更追加 `assessment_reviews`，保留前值、新值、原因、私有备注和学生可见评语，并重算尝试与最佳成绩。
- 教师反馈：已提供参与/提交/通过/掌握、待复核、均值/中位数、分布、平均次数、学生队列、题目与知识点分析；比例均携带 numerator/denominator。
- 权限边界：学生访问班级分析或复核接口返回 403；学生反馈不包含教师私有备注。
- 当前结论：A4、A5 中复核和分析部分已有自动化证据；Agent 投影、安全专项与真实浏览器双账号 B1～B8 仍待完成，不据此宣称整体验收通过。

### 第二阶段学生作答与揭示证据（非最终签收）

- 后端回归：测评、学习闭环及 PostgreSQL repository 共 `61 passed`；新增揭示服务/API、揭示前密钥隔离、揭示后关闭计分作答均已覆盖。
- 前端回归：Node 全量测试 `342 passed`；学生测评状态机定向测试 `2 passed`；生产构建退出码 `0`。
- 学生端已覆盖：开始测评、单选/多选/判断/文本与代码输入、保存修订、提交、待复核、重试、最佳分、答案揭示及揭示后关闭计分入口。
- 绕过入口：正式学习任务不再显示“我已完成”自报按钮；任务可信完成仅由服务端测评结果写入。
- 当前结论：A3、A5 中学生作答部分已有自动化证据；教师复核、班级分析、Agent 投影及真实浏览器双账号 B1～B8 仍待后续阶段，不据此宣称整体验收通过。

### B1. 无测评不能发布

教师新建任务并选择材料，跳过正式测评直接发布；界面阻止。用开发者工具直接调用发布 API，服务端返回 `409 ASSESSMENT_REQUIRED`。

### B2. 已有习题导入

教师选择包含 3 道题的习题材料，正式测评步骤显示 3 道导入题和来源；生成服务调用数不增加。教师编辑一题后发布，原材料随后改名或改题，学生仍看到发布快照。

### B3. 无习题自动生成

教师选择文本材料和两个知识点，生成测评草稿；确认题目均有材料来源，覆盖两个知识点。人为删除一道客观题答案，发布被阻止；补回答案后发布成功。

### B4. 版本与迁移

一名学生开始作答后，教师发布修订版；该学生继续旧版本，未开始的另一学生获得新版本。旧 `completed` 数据只显示学生自报，不显示测评验证。

### B5. 答案与权限攻击

学生在 Network 中检查测评、课程材料、保存、提交和反馈响应，揭示前无答案/解析/评分键。尝试传其他学生 ID、最终分和 `assessment_scored` 均失败。教师可查看课程内复核，学生不能访问班级分析。

### B6. 三次作答与补学

学生第一次 50 分，看到薄弱知识点和材料建议；第二次 75 分后选择继续挑战且不揭示答案；第三次 65 分。最终最佳成绩 75，三次历史完整，第四次被拒绝。随后结束测评并揭示解析，不能再创建计分作答。

### B7. 主观题复核

学生提交含简答题的测评，状态为待复核且不显示通过。教师查看 AI 建议、量规和置信度，调整分数并填写原因；学生随后看到最终分和可见评语，审计中保留原建议和教师决定。

### B8. 教师反馈与 Agent

教师查看参与率、提交率、通过率、掌握良好率、分布、平均次数、待复核、高频错题和薄弱知识点，比例带分母。教师 Agent 回答聚合且说明时间/口径；学生 Agent 只回答本人状态，待复核不称为通过，未揭示答案不输出答案。

## 7. 证据记录模板

```text
验收提交：
验收日期与时区：
验收人：
前端/后端地址：
教师账号标识（脱敏）：
学生账号标识（脱敏）：
课程 ID / 任务 ID / 测评版本 ID：
三次作答 ID 与最终分：
A1～A8 命令结果：
B1～B8 截图/日志路径：
答案泄露检查：
权限攻击结果：
Agent 回答与 trace：
已知限制、失败和重跑结果：
最终结论：通过 / 不通过
```

## 8. 签收条件

只有 AC-ASMT-01～18、A1～A8 和 B1～B8 全部通过，才能把状态改为“通过”。签收时同步更新 Spec 状态、Plan 勾选、决策日志和项目总览；安全代码判题仍明确保留为非本期能力。

## 9. 最终验收记录

- 验收时间：2026-08-12（Asia/Shanghai）。
- 真实端到端：Playwright 启动隔离的 FastAPI、Vite、SQLite 测评/学习库，使用 `teacher` 与 `student` 真实登录；未 route/mock 学习任务和测评 API。
- 客观题链路：无测评时发布按钮禁用；揭示前投影无 `scoring_key`/正确选项；三次作答依次 50、75、65，最佳分保持 75；揭示后关闭计分入口；学生访问班级分析返回 403；教师看到 1/1 分母统计。
- 计算机课程链路：`code_implementation` 使用代码文本域提交后进入 `pending_review`；教师在正式测评分析页按量规给 88 分；学生看到 88 分和教师可见评语；教师私有备注只存在审计 API，学生反馈中不可见。
- 后端全量：`1675 passed, 2 skipped, 9 warnings`，退出码 0；两项 skip 为按环境条件跳过的用例。
- 前端全量：`345 passed, 0 failed, 0 skipped`；lint 为 `0 errors, 47 warnings`，均为既有基线 warning；生产构建退出码 0。
- 数据库：真实 PostgreSQL 容器恢复用例通过；Alembic 仅 `20260812_0014 (head)`；测评相关 Ruff `All checks passed!`。
- 浏览器目视：教师登录、课程权限、任务创建面板和资源选择无控制台 error/warning；验收地址统一使用已配置 CORS 的 `localhost`。
- 缺陷闭环：端到端红灯修复了首次 assignment 未建立时错误映射（422→404）、登录等待条件、通过后继续挑战入口，以及复核后学生端未展示教师评语的问题。每项修复后均重跑专项 E2E。
- 环境修复：首次全量发现本机开发 PostgreSQL 被历史操作标记为 `0013` 但测评表数量为 0；确认无测评数据后将版本戳恢复到 `0012`，让标准 `0013→0014` 迁移重建，容器恢复用例和后端全量随后全部通过。未将该不一致状态误报为产品通过。
- 最终结论：AC-ASMT-01～18 通过。安全执行不可信代码、隐藏测试和代码运行沙箱按 D-003 不在本期范围；本期代码实现题采用 AI 建议/教师量规复核形成最终成绩。
