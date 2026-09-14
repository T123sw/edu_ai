# 生成工厂统一接入 Agent 与极简需求输入：实施计划

> 配套设计：[2026-09-10-generation-factory-agent-entry-design-cn.md](../specs/2026-09-10-generation-factory-agent-entry-design-cn.md)  
> 配套验收：[2026-09-10-generation-factory-agent-entry-acceptance-cn.md](../../acceptance/2026-09-10-generation-factory-agent-entry-acceptance-cn.md)

**目标：** 将生成工厂的八类资源按钮改为静默 Agent 快捷入口，以一个自然语言需求框替代大型逐字段配置表单；工厂提交不进入对话，报告等资源跳过用户大纲确认并直接生成，普通对话流程保持原确认规则。

**实施原则：** 先用测试锁定请求契约和入口行为，再接共享队列与 ChatPanel，随后收口后端 hint 与质量策略，最后删除生成工厂的旧直达依赖。不得先删除 direct API；不得用字符串事件或 DOM 查询绕过共享状态。

**执行状态（2026-09-10）：** 第 1–8 节及静默直达修订已完成。生成工厂已断开 direct 提交并统一进入带 `entry_mode=generation_factory` 的 Chat V2；极简弹窗、工作区隔离、八类 hint、后端同轮规划提交、会话持久化隔离和响应式 E2E 已落地。旧表单与 direct 客户端仍作为兼容代码保留。

下方复选框保留为实施前批准的原始清单，当前完成状态以本节和验收记录中的逐项结果为准。

已完成的核心交付：

- 八类按钮到 `action_hint` 的单一映射，思维导图规范化为 `generate.graph`；
- 一个自然语言输入框、动态浅色示例、折叠资料范围、草稿恢复、焦点圈定与窄屏聊天引导；
- 单请求队列、幂等消费、来源/课程/用户快照与跨工作区恢复，以及不依赖普通聊天忙碌状态的静默发送；
- 后端共享 hint allowlist，文字中的暂停、否定和改类型优先于按钮提示；
- 工厂请求不写入聊天气泡、会话历史或长期记忆；报告、教案和课堂在内部形成方案后同轮提交；
- Agent 资源统一 `review_policy=required`，发布前绑定内容摘要和审阅记录；
- 浏览器五档视口 25/25 通过，前端生产构建通过，定向前后端测试通过；
- 隔离目录中的真实模型方案、任务、审阅和材料回读证据。

## 0. 实施前基线

- [ ] 记录当前 `git status --short`，保留用户已有未提交改动。
- [ ] 重跑资源相关后端测试并记录已有失败；当前已知 `test_harness_resources.py` 与 `test_generation_preflight.py` 存在测试契约漂移，不能把旧失败算作本功能引入。
- [ ] 重跑前端全量 Node 测试，先修复或在验收记录中隔离现有静态源码断言失败。
- [ ] 确认八类资源在教师和学生工具目录中的权限清单，以服务端返回为准。

基线命令：

```bash
cd /home/zxqs_ep/Edu_AI
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m pytest -q \
  backend/src/tests/chat/test_harness_resources.py \
  backend/src/tests/chat/test_harness_runtime.py \
  backend/src/tests/chat/test_generation_preflight.py

cd /home/zxqs_ep/Edu_AI/frontend
PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH pnpm test
```

## 1. 定义资源类型与 Agent 请求纯函数

**文件：**

- Create: `frontend/src/components/generation/generationAgentRequest.ts`
- Create: `frontend/src/components/generation/generationAgentRequest.test.ts`
- Modify: `frontend/src/components/generation/generationRegistry.ts`
- Modify: `frontend/src/components/generation/generationRegistry.test.ts`

- [ ] 为八类前端资源建立唯一的 canonical type 与 `generate.*` hint 映射；`mind_map` 明确映射为后端 `graph`。
- [ ] 为每类资源定义标题、帮助文案和动态 placeholder，文字使用设计文档中的示例。
- [ ] 实现 `normalizeGenerationBrief`：只 trim 用户输入，不解析关键词、不拼接 placeholder。
- [ ] 实现 `buildQueuedAgentRequest`：接收认证用户、工作区、资料选择和当前对话能力设置，生成不可变请求快照。
- [ ] 对空需求、无课程、知识点 scope 缺 ID、selected_documents 无 ID 给出前端可读错误。
- [ ] 测试 placeholder 从不出现在 `text` 或序列化 payload 中。
- [ ] 测试八类按钮的 hint、canonical type 和展示名称一一对应且不重复。

验证：

```bash
cd /home/zxqs_ep/Edu_AI/frontend
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/node --import tsx --test \
  src/components/generation/generationAgentRequest.test.ts \
  src/components/generation/generationRegistry.test.ts
```

## 2. 将共享消息队列升级为结构化 Agent 请求

**文件：**

- Modify: `frontend/src/store/teacher/useStore.ts`
- Create: `frontend/src/store/teacher/queuedAgentRequest.test.ts`
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
- Modify: `frontend/src/components/teacher/chatHistoryRecovery.ts`（仅在现有恢复守卫需要扩展时）

- [ ] 新增 `QueuedAgentRequest`、`queuedAgentRequest`、`enqueueAgentRequest`、`consumeAgentRequest` 和 `clearQueuedAgentRequest`。
- [ ] 队列最多保留一个请求；已有请求未消费时返回冲突结果，不覆盖旧请求。
- [ ] 保留读取旧 `queuedMessage` 的兼容迁移，停止由生成工厂写入旧字段。
- [ ] 消费时核对 owner、course、scope；不匹配时保留用户文字并返回工作区变化提示。
- [ ] request ID 消费幂等；React effect 重跑不能重复发送。
- [x] 工厂请求独立发送，不等待 ChatPanel 当前对话结束；队列仍保证同一待处理请求只消费一次。
- [ ] 用户登出、新建会话、切换课程和切换知识点的处理分别写测试，不能让旧请求进入新范围。

验证：

```bash
cd /home/zxqs_ep/Edu_AI/frontend
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/node --import tsx --test \
  src/store/teacher/queuedAgentRequest.test.ts \
  src/components/teacher/chatHistoryRecovery.test.ts
```

## 3. 让 ChatPanel 使用请求快照发送独立的静默 Agent 流

**文件：**

- Modify: `frontend/src/services/teacher/chatV2.ts`
- Modify: `frontend/src/services/teacher/chatV2.retrieval.test.ts`
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
- Create: `frontend/src/components/teacher/generationAgentHandoff.test.ts`

- [x] `BuildChatReplyPayloadOptions` 增加 `actionHint` 和 `entryMode`，原样写入 `action_hint` 与 `entry_mode`。
- [x] 新增独立静默发送函数，使用 source、scope 和 hint 快照；普通 `handleSendMessage` 行为不变。
- [x] 不创建用户消息或 AI 进度消息，不采用当前会话 ID，也不切换用户正在查看的会话。
- [x] 后端使用临时执行会话维持 Agent 工具状态和幂等，但不写对话历史或长期记忆。
- [x] 报告、教案、博客和课堂在同一轮完成内部方案并提交；任务进度进入生成工厂和全局任务中心。
- [x] 请求开始时幂等消费队列；启动失败时恢复原资源类型的输入草稿并提示重试。
- [ ] 测试 selected_documents、course_auto、none 三种来源，及 Web 开关的继承。

验证：

```bash
cd /home/zxqs_ep/Edu_AI/frontend
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/node --import tsx --test \
  src/services/teacher/chatV2.retrieval.test.ts \
  src/components/teacher/generationAgentHandoff.test.ts
```

## 4. 用极简需求弹窗替换生成工厂配置表单

**文件：**

- Modify: `frontend/src/components/generation/GenerationFactory.tsx`
- Modify: `frontend/src/components/generation/generationFactory.css`
- Create: `frontend/src/components/generation/GenerationPromptDialog.tsx`
- Create: `frontend/src/components/generation/generationPromptDialog.test.ts`
- Modify: `frontend/src/components/teacher/StudioPanel.tsx`
- Modify: `frontend/src/stitch/student/tools/StudentGenerationFactory.tsx`

- [ ] 新弹窗默认只显示资源名称、带标签的 textarea、资料范围摘要、取消和“交给 AI”。
- [ ] placeholder 按资源类型动态变化；输入为空时按钮禁用并有可访问错误提示。
- [ ] 资料范围放入默认折叠区，复用 `GenerationSourceSelector`，不复制文档加载与权限逻辑。
- [ ] 默认来源按设计文档计算：选中文档优先，否则沿用当前 ChatPanel RAG/Web 设置。
- [x] 点击提交构建 `QueuedAgentRequest`，成功入队后关闭弹窗；窄屏可返回聊天区但不会显示本次工厂输入。
- [x] 提交时短暂显示“正在提交后台生成”，重复点击不重复排队。
- [ ] 草稿按 owner、course、scope、resource type 保存；发送成功后清理该草稿。
- [ ] 保留最近生成列表和原位预览，不再调用 `useGenerationSubmission`。
- [ ] 教师和学生共用相同弹窗；按钮目录继续由后端权限清单过滤。
- [ ] 删除 `GenerationFactory` 对 `ConfigForm`、definitions serializer 和 direct preflight 的运行依赖。

响应式检查：1440×1000、1366×768、1280×800、1024×768、390×844。

验证：

```bash
cd /home/zxqs_ep/Edu_AI/frontend
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/node --import tsx --test \
  src/components/generation/generationPromptDialog.test.ts \
  src/components/generation/generationAgentRequest.test.ts
```

## 5. 扩展后端八类 action hint 契约

**文件：**

- Modify: `backend/src/app/chat/domain/contracts.py`
- Modify: `backend/src/app/chat/api/schemas_v2.py`
- Modify: `backend/src/app/chat/api/routes_v2.py`
- Modify: `backend/src/app/chat/application/request_normalizer.py`
- Modify: `backend/src/app/chat/harness/runtime.py`
- Modify: `backend/src/app/chat/harness/root-role.md`
- Modify: `backend/src/tests/chat/test_request_normalizer.py`
- Modify: `backend/src/tests/chat/test_routes_v2.py`
- Modify: `backend/src/tests/chat/test_harness_runtime.py`
- Modify: `backend/src/tests/chat/test_harness_resources.py`

- [ ] 建立共享 action hint allowlist，包含八类规范 hint 与现有 chat/research hint；路由、schema 和 Harness 使用同一来源。
- [ ] `_is_workflow_intent_from_reply` 不再只识别报告、教案和习题。
- [ ] Harness 收到按钮 hint 时将其作为当前目标类型上下文；仍要求模型读取 `current_user_message` 并尊重否定、暂停和跨类型切换。
- [ ] root role 明确“按钮确定初始目标类型，文本决定具体要求”，不得把 placeholder 或前端默认值视作用户事实。
- [ ] 参数数量、受众、风格等仍由模型交给对应 Skill 和工具 schema，不新增关键词解析器。
- [ ] 未知或角色无权使用的 hint 在执行工具前返回稳定错误。
- [ ] 参数化验证八类 hint 都进入 Harness，并得到正确资源类型或正确方案交互。

验证：

```bash
cd /home/zxqs_ep/Edu_AI
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m pytest -q \
  backend/src/tests/chat/test_request_normalizer.py \
  backend/src/tests/chat/test_routes_v2.py \
  backend/src/tests/chat/test_harness_runtime.py \
  backend/src/tests/chat/test_harness_resources.py
```

## 6. 显式统一质量审阅策略

**文件：**

- Modify: `backend/src/app/services/generation_command.py`
- Modify: `backend/src/app/services/generation_task_handlers.py`
- Modify: `backend/src/app/services/classroom_service.py`
- Modify: `backend/src/app/chat/harness/tools.py`
- Modify: `backend/src/tests/chat/test_generation_command.py`
- Modify: `backend/src/tests/chat/test_harness_resources.py`
- Modify: `backend/src/tests/test_classroom_job_service.py`

- [ ] 在内部 GenerationCommand/config 中使用明确的 review policy 或等价受控字段；不让公开客户端绕过质量门槛。
- [ ] Agent 创建的八类可发布资源统一要求版本绑定的审阅记录。
- [ ] 普通资源生成器和课堂后处理依据 review policy 执行，不再仅用 `harness_outline_id` 或 `harness_config` 的存在判断。
- [ ] 发布前继续校验资源 hash、类型、完整审阅维度和逐题/逐场景覆盖。
- [ ] 失败、取消、重试和 sidecar 复用保持现有幂等与权限边界。
- [ ] direct API 暂留原行为并明确记录兼容策略；如果也切换到 reviewed policy，需补充性能和兼容验收后单独启用。

验证：

```bash
cd /home/zxqs_ep/Edu_AI
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m pytest -q \
  backend/src/tests/chat/test_generation_command.py \
  backend/src/tests/chat/test_harness_resources.py \
  backend/src/tests/test_classroom_job_service.py
```

## 7. 断开生成工厂 direct API，并清理可确认的死代码

**文件：**

- Modify: `frontend/src/components/generation/useGenerationSubmission.ts` 或删除（需先确认无调用）
- Modify/Delete: `frontend/src/components/generation/forms/*`
- Modify: `frontend/src/components/generation/definitions/*`
- Modify: 对应 definitions/form 测试

- [ ] 用 `rg` 确认 `useGenerationSubmission`、各表单和 serializer 是否还有生成工厂之外的调用者。
- [ ] 无调用者的 UI 表单与样式删除；仍被其他页面使用的 definitions 只保留领域映射，不再供生成工厂提交。
- [ ] 保留 direct API 的类型定义和客户端函数，直到确认没有外部/旧页面调用。
- [ ] 删除失效测试，改为行为测试；不得用源码正则断言替代用户交互和请求验证。
- [ ] `rg` 确认 GenerationFactory 不再引用 `/report/direct`、`/quiz/direct`、`/graph/direct`、`/classrooms/generate` 等路径。

检查：

```bash
cd /home/zxqs_ep/Edu_AI
rg -n "useGenerationSubmission|/direct|classrooms/generate" frontend/src/components/generation frontend/src/stitch/student/tools
```

## 8. 浏览器端到端验收

**文件：**

- Create: `frontend/tests/e2e/generation-factory-agent-entry.spec.ts`
- Modify: `frontend/tests/e2e/fixtures/apiRoutes.ts`
- Modify: `frontend/tests/e2e/generation-factory-shell.spec.ts`
- Modify: `frontend/tests/e2e/harness-resources.spec.ts`

- [ ] 对八类按钮参数化验证：打开正确弹窗、显示对应 placeholder、只出现一个主输入框。
- [ ] 拦截网络并断言提交只调用 `/api/chat/v2/stream`，不调用任何 direct 生成接口。
- [ ] 断言请求含正确 action_hint、原始用户文字、课程/scope、source_mode 和文档 ID；不含 placeholder 文本。
- [x] 验证八类请求均含 `entry_mode=generation_factory`，报告等资源不展示方案确认并直接返回 task ID。
- [x] 验证提交原文和 Agent 进度均不进入聊天 DOM，请求不携带当前 `conversation_id`。
- [ ] 验证重复点击幂等、切换课程不误发、启动失败恢复草稿及刷新后任务恢复。
- [ ] 验证教师和学生按钮 allowlist、个人资源可见性及学生无发布权限。
- [ ] 在五种视口验证焦点、Escape、无横向溢出和窄屏聊天引导。

验证：

```bash
cd /home/zxqs_ep/Edu_AI/frontend
PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH pnpm exec playwright test \
  tests/e2e/generation-factory-agent-entry.spec.ts \
  tests/e2e/harness-resources.spec.ts \
  --project=desktop1366 --project=compact1024
```

## 9. 真实模型与真实任务验收

- [ ] 使用隔离教师、学生、课程和存储目录，不复用生产数据。
- [ ] 八类资源至少各跑一条生成工厂请求，保存完整 HTTP/SSE、tool trace、job、material 和截图证据。
- [ ] 抽查 Agent 是否提取示例中的受众、数量、难度、风格、篇幅、课时、语音/图片要求。
- [ ] 抽查否定优先：“先讨论，不要生成”不得提交任务。
- [ ] 抽查来源边界：指定文档只使用选中范围，跨课程文档被拒绝，无资料模式不假称引用资料。
- [ ] 结果必须能从全局任务完成通知和右侧最近生成列表打开；版本绑定审阅验证通过。
- [ ] 记录生成阶段、审阅轮次、总耗时和失败重试，不把最终重试成功改写成首次成功。

可复用并扩展：

```bash
cd /home/zxqs_ep/Edu_AI
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python \
  scripts/verify-harness-resources.py --output <隔离证据目录>
```

## 10. 全量回归与交付

- [ ] 后端资源、会话、修改、权限、任务恢复测试全绿。
- [ ] 前端全量 Node 测试全绿，不保留与本次改造相关的旧源码正则断言。
- [ ] 前端生产构建通过。
- [ ] 关键 Playwright 桌面与紧凑视口通过。
- [ ] 按验收文档逐项填写结果与证据路径。
- [ ] 更新 `项目总览地图.md`、`docs/README.md` 和验收索引状态；只有真实证据齐全后才能把“待验收”改为“通过”。

最终命令：

```bash
cd /home/zxqs_ep/Edu_AI
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m pytest -q backend/src/tests

cd /home/zxqs_ep/Edu_AI/frontend
PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH pnpm test
PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH pnpm build
```

## 11. 回退方案

若 Agent 入口在真实环境中不可用，回退仅恢复 GenerationFactory 对现有 `useGenerationSubmission` 的调用和旧配置弹窗。不要删除已创建的会话、任务、资源或审阅记录；不要回滚数据库。保留新结构化队列代码但停止写入，确保旧客户端和 direct API 仍可工作。回退原因、影响范围和失败证据必须写入验收记录。
