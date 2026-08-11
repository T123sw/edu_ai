# Task 7 实施报告：真实双账号 E2E 与 Agent 行为门禁

## Status

实现完成并已提交前验证。真实 teacher → student → teacher 数据闭环、隔离持久化、权限/幂等/单调性、重启重登、历史恢复失败及双端确定性 Agent 领域选择均通过。根据验收签字规则，整体人工验收仍为“不通过”，原因是本次没有真实外部模型凭据/人工验收、完整 `npm test`、旧库迁移、重名资源和单课程摘要局部降级证据。

## 实现

- 新建单用例双 context Playwright 场景。教师通过真实 UI 创建并发布 `E2E-LOOP2-` 任务；学生首页发现任务、打开真实共享资源进入 1%、确认自报口径并完成；教师看到 1/1、100% 和“学生自报完成”。
- 同一用例通过真实 API 验证学生创建/读取班级汇总和教师代写事件均为 403、重复 `event_id` 不增加证据、完成后迟到 `started` 不回退。
- 在同一场景重启隔离后端并重新获取教师/学生 token，再清空浏览器认证并双端重新登录；重启前后汇总做深比较。
- 注入 `deterministic-learning-e2e` SSE 网关验证 Agent 工具与结构化事实：教师只用 `get_course_learning_progress`，学生只用 `get_my_learning_progress`；trace 不含 generation status 工具，学生回答含本人 `lt_` 且不含 `job_`。
- 学生历史列表注入 stale conversation，详情固定返回 500；验证友好恢复提示、可新建对话且旧 `job_` 不进入新回答。
- 修复发现的真实 UI race：初始 history 请求现在带 ConversationAsyncGuard load generation；用户快速发送后，迟到空列表不能 `setMessages([])` 清除新消息。新增可控 Promise 单元测试。
- 后端 acceptance/runtime 测试增加角色事实、工具 trace、隐私边界、幂等/单调/重启和 HTTP 权限门禁。

## RED / GREEN

1. 后端初始 RED：目标测试 13 passed / 1 failed。原因是测试用 `"job_" not in prompt` 过宽，系统策略文字合法提到 `job_` 前缀；收紧为实际 ID 正则 `job_[a-z0-9]+` 后 GREEN：14 passed。
2. E2E RED 逐步暴露并修复：旧前端 API host 未完全转发导致隔离失误；随后固定独立 frontend/backend 端口。教师 SSE 首帧过早采用新 conversation id 触发 guard；改为 final result 采用。更重要的是初始 history 响应会在快速发送后清空消息，修复产品 generation guard 并补单测。学生历史 fixture 又因 React StrictMode 首个旧 effect 消耗一次性 stale 响应，改为每次初始化稳定返回同一 stale 会话。
3. 最终 GREEN：Playwright `1 passed (1.2m)`，用例主体 46.8s，retries=0。

## 服务与数据隔离

- 前端：`http://127.0.0.1:15173`，fixture 独立 Vite 进程，`VITE_API_BASE_URL=http://127.0.0.1:18001`。
- 后端：`http://127.0.0.1:18001`，fixture 独立 uvicorn 进程。
- 最终证据 worker：`Edu_AI/test-results/learning-loop/worker-0-1786379881521`。
- 学习库：worker 内独立 `learning.db`/WAL/SHM；账号、membership、storage 也指向 worker artifact。真实课程共享资源仅只读使用，未修改课程创建/加入链路。
- fixture teardown：每个 child 先 SIGTERM，最多 8 秒；再 SIGKILL，最多 3 秒。最终核验 15173/18001 均无监听。
- 自动化只创建 `E2E-LOOP2-` 任务，不清理真实用户数据库行。

## 实际命令与输出

- `npx.cmd playwright test tests/e2e/teacher-student-learning-loop.spec.ts --project=desktop1440 --workers=1`
  - PASS：1 passed (1.2m)，test 46.8s，retries=0。
- `D:\anaconda\envs\edu-ai\python.exe -m pytest -q tests/learning/test_learning_loop_acceptance.py tests/chat/runtime/test_learning_task_domain.py --basetemp=...`
  - PASS：14 passed in 2.75s。
- 扩展后端命令（`tests/learning`、learning context/domain/tools、teaching contract、planner、agent tools/memory restore）
  - PASS：96 passed，5 个既有 `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings。
- `node --import tsx src/components/teacher/chatHistoryRecovery.test.ts`
  - PASS：17 passed。
- `npm.cmd run lint`
  - PASS：exit 0，0 errors；存在仓库既有 warnings，含 ChatPanel 既有 exhaustive-deps warnings。
- `npm.cmd run build`
  - PASS：built in 54.89s；存在既有 dynamic import/chunk size warnings。
- `npm.cmd test`
  - 未实际执行：受控环境要求额外 spawn 权限，审批等待被中断；不记为成功。

## 证据位置

- 最终截图：`Edu_AI/test-results/e2e/teacher-student-learning-l-477a7-oop-with-role-scoped-agents-desktop1440/attachments/01-...png` 至 `07-...png`。
- 持久证据副本：`Edu_AI/test-results/learning-loop/worker-0-1786379881521/01-teacher-published.png` 至 `07-student-agent-history-recovery.png`。
- API 服务摘要：同 worker 的 `backend.log`；隔离 DB 为 `learning.db`。
- 失败迭代证据由 Playwright `trace.zip`/screenshots 保留到下一次运行；最终 PASS 使用 list reporter，trace 策略为 `retain-on-failure`。

## 自动化模型与真实模型的边界

自动化 Agent 验收通过的是确定性网关：它证明页面可用、领域工具名正确、结构化学习事实正确、teacher/student 数据投影与 trace 断言正确。它不证明真实外部模型的自然语言稳定性、可用性或供应商链路。本次没有可可靠使用的真实模型凭据，因此双端真实模型人工验收未执行，验收表据此明确标为“不通过”，没有虚报。

## 隔离失误与外部残留

早期调试时，旧 Vite 前端实际请求 `127.0.0.1:8001`，而最初转发只覆盖 `localhost:8001`，导致一次 `E2E-LOOP2-` 任务误写入外部 8001 数据库：`lt_9dbeb1159aec4bc0ad0ee435f8d04af4`。正式 API 没有删除能力，且任务约束禁止直接删除真实用户数据库行，因此没有删除该记录。之后改为 fixture 自启 15173 并通过 `VITE_API_BASE_URL` 绑定 18001；最终日志与端口核验确认所有闭环业务请求进入 18001，未再发生外部写入。

## 文件与自查

- `Edu_AI/tests/e2e/fixtures/learningLoop.ts`
- `Edu_AI/tests/e2e/teacher-student-learning-loop.spec.ts`
- `Edu_AI/api/src/tests/learning/test_learning_loop_acceptance.py`
- `Edu_AI/api/src/tests/chat/runtime/test_learning_task_domain.py`
- `Edu_AI/src/components/teacher/ChatPanel.tsx`
- `Edu_AI/src/components/teacher/chatHistoryRecovery.test.ts`
- `Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md`
- `.superpowers/sdd/2026-08-10-teacher-student-interaction-loop-phase2/task-7-report.md`

自查：未修改课程创建/加入链路；retries=0；最终端口无监听；只使用独立学习 DB；真实模型与确定性模型结论严格分开；外部残留已明确披露且未直接删库。
