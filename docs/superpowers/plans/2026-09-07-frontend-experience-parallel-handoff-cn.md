# 前端三项体验设计：三个 Agent 并行执行说明

日期：2026-09-07｜状态：A/C 已交付，B 已接入并完成分层验证；完整端到端组合仍有待验项。

需求来源：[本次对话纪要](../specs/2026-09-07-frontend-experience-conversation-design-cn.md)。最新用户澄清优先于历史方案：**首页显示课程名称＋一个继续按钮；“为当前课程生成资料”围绕当前所在知识点，不明确必须追问。** 用户“3 暂时没有”指没有第三条补充，不是取消已有资料修改需求。

## 1. 任务包

| 执行者 | 任务 | 设计 | 计划 | 验收 |
| --- | --- | --- | --- | --- |
| Agent A | 首页继续备课／学习 | [A 设计](../specs/2026-09-07-home-resume-design-cn.md) | [A 计划](2026-09-07-home-resume-plan-cn.md) | [A 验收](../acceptance/2026-09-07-home-resume-acceptance-cn.md) |
| Agent B | 知识点上下文、澄清及共享集成 | [B 设计](../specs/2026-09-07-knowledge-context-design-cn.md) | [B 计划](2026-09-07-knowledge-context-plan-cn.md) | [B 验收](../acceptance/2026-09-07-knowledge-context-acceptance-cn.md) |
| Agent C | 已有资料的 Agent 修改更新 | [C 设计](../specs/2026-09-07-artifact-revision-design-cn.md) | [C 计划](2026-09-07-artifact-revision-plan-cn.md) | [C 验收](../acceptance/2026-09-07-artifact-revision-acceptance-cn.md) |

每位 Agent 先读仓库 AGENTS.md、项目总览地图、本说明和自己的三份文档。不要展开本轮明确排除的目录重构和整体视觉改版。细节工程默认值在分项设计中标明；与用户后续指令冲突时按用户最新指令修订。

## 2. 并行方式与文件所有权

建议三个 Agent 从同一基线提交建立独立分支／worktree。交付 commit 标识、变更清单和验收记录，避免三个进程操作同一工作区的 checkout／reset。本文产生的文档如尚未提交，启动者应先让三个工作区都能读取同一文档版本，不能仅创建基于旧 HEAD 的 worktree 后遗漏这些文件。

| 文件／区域 | 唯一写入者 | 其他人如何接入 |
| --- | --- | --- |
| 首页、recentLearning、新 resume 模块、App.tsx／StudentApp.tsx | A | B／C 提供必要挂载请求，A 写入 |
| AIWorkspace、workspaceScope、ChatPanel、chatV2、teacher useStore | B | C 新建独立组件／类型，向 B 提供接入说明 |
| 共享后端请求 schema、normalize、reply／route service、context builder、主 runtime 调度 | B | C 提供修改服务，B 统一调用和映射响应 |
| 生成工厂、StudioPanel、CourseResources、新 artifactRevision UI | C | B 提供 scope 透传补丁，C 写入 |
| artifact_reference 领域模型、report edit runtime、新修改服务／类型适配／版本存储 | C | B 只消费公开服务和类型；新增存储文件先登记路径 |
| 分项新增测试、各自验收文档 | 对应 Agent | 不替他人填写通过 |
| 公共索引、本文、最终集成记录 | B（实施阶段） | A／C 在分项文档交付，不并发改索引 |

未列出的共享文件先明确负责人再编辑；该协调属于 Agent 之间的实现协作，不应反复要求用户确认常规代码调整。同一文件即使不同位置也尽量保持单一写入者。

## 3. 最小共享契约

### 3.1 导航和范围

- 保持现有 hash 和 `course_id`、`scopeType`／`scopeId` 解析兼容；A 只记录允许字段，B 解析真实知识点，不另造彼此不识别的 URL 参数。
- 请求沿用 `course_id`、`scope_type`、`scope_id`；服务端真实身份、课程、知识点关系是权威来源。
- 页面当前知识点是新生成默认主题。“当前课程”不能推导为整门课程。
- C 已定位资料的原始归属和基准版本决定修改目标，不能被新的页面 scope 覆盖。

### 3.2 B／C 服务边界

B 交付可信 context 与统一待处理操作机制，C 交付资料定位、读取、修改、验证和保存服务。目标语义为：

```text
B: resolve workspace → route operation
C: resolve artifact → read → clarify or revise → validate → save
B: map reply/SSE → render clarification or result
```

C 的服务结果区分 `not_applicable / needs_clarification / completed / conflict / failed`。B 的范围解析区分 `resolved / needs_clarification / invalid`。这些是待实现的逻辑约定，优先适配现有类型；不可声称已有接口支持。

B 在早期提交实际函数签名、字段和事件映射；C 回传类型覆盖及引用扩展。B 是共享协议唯一编辑者，C 拥有资料引用领域类型。新字段增量兼容，禁止用 `any` 强行越过前后端不一致。

只有一个待处理操作，按认证主体＋会话绑定。范围不明由 B 追问，目标资料／意见不明由 C 追问；彼此保留原始操作及用户补充，不重复弹出两套问题。

### 3.3 UI 集成

C 可导出独立 EditReference／RevisionResult 组件及 revision intent 构造函数，B 接到 ChatPanel 的引用区／结果区；不再创建一个平行聊天页面。C 保留原生成流程，并接入 B 给出的知识点 props／请求字段。

函数名称不是强制新增 API，允许复用现有实现；但必须在交接记录写明实际名称、参数、返回值和调用位置，不能停留在伪接口。

## 4. 分阶段并行与集成

1. 三者并行做调用链／现有能力审计。A 可直接开发；B／C 首先用小提交冻结上述实际契约。
2. A 完成首页；B 实现范围解析和澄清；C 实现资料服务、版本及独立 UI。C 可先用契约测试替身开发，但替身不算生产集成完成。
3. C 提交可合入模块及最小接入清单；B 合入后完成共享 ChatPanel／协议／调度接入，C 应用生成工厂 scope 透传。
4. A 交付独立提交；B 负责在最终集成分支组合三者，解决边界冲突并运行组合验收。B 等待 C 期间继续自身测试和 A 集成，不重复实现 C 模块。
5. 每个 Agent 更新自己的验收表；最终 B 核对各表和组合结果。未完成项保留待验证，不因各自模块测试通过就宣布全部完成。

接口变更应同步更新契约记录并通知另一方。用户负责分发任务，不需要承担手工拼接代码的工作。

## 5. 测试环境与隔离

- 前端测试真实目录为 `frontend/src/**/*.test.ts`、`frontend/tests/e2e/`；旧 `frontend/tests/frontend` 不被默认测试命令覆盖。
- 后端测试在 `backend/src/tests/`，不是 `backend/tests/`。在 `backend/src/` 使用项目已配置 Python 环境执行 pytest。
- 浏览器默认项目 desktop1366 存在，mobile 项目不存在；窄屏用测试内 viewport 设置。
- A／B／C 并行 E2E 建议设置 `PLAYWRIGHT_PORT` 为 5181／5182／5183，使用各自 worktree 服务，避免复用 5173 的不确定代码。后端测试使用独立临时存储；真实模型测试使用专用课程副本。
- `pnpm build` 不是 tsc；按实际改动运行类型检查或记录现有基线问题，不能把未跑项目写成通过。新增行为测试不能只匹配源码字符串。
- 不升级依赖、不改锁文件，除非功能确需且由单一负责人处理；不访问或修改真实用户资料作为验收样本。

## 6. 组合验收（B 负责回填）

| ID | 路径 | 必须满足 | 状态 |
| --- | --- | --- | --- |
| I01 | A 继续数组备课 → B 为当前课程生成报告 | 首页显示正确课程，恢复数组；实际生成归属数组 | 分层通过：浏览器恢复到 B 请求＋真实生成归属；未跑一条全真首页链 |
| I02 | B 无知识点生成 → 追问 → 数组 → C 修改结果 | 原生成意图续接，C 读取刚生成报告并保存新版 | 通过：真实 ReAct 追问续接→生产报告 handler→C SSE 修改 v2（保留大纲确认） |
| I03 | C 修改意见不明确 → 追问 → 用户补充 | 不重新问已确定知识点，不丢目标、版本与意见 | 分层通过：C 续接确定性测试＋共享入口测试；完整真实模型追问修改链待验 |
| I04 | 运行任务时切换课程／账号，再从 A 继续 | 不串资料、不泄漏名称、不覆盖其他范围记录 | 部分通过：迟到响应／主体隔离分项测试；跨课跨账号完整链待验 |
| I05 | C 修改已发布资料 → 学生 A 继续学习 | 学生仍学习原发布版本，直到教师主动发布 | 部分通过：C 发布快照与 A 学生继续分项测试；全真发布到学生链待验 |

最终提交：A `6ad477dd`／`deca3498`，C `f73cd1ca`；B 集成仍在共享工作区，尚未单独提交。组合环境：本地 edu-ai、Chromium、隔离 JSON／SQLite 资料；浏览器使用模拟 API，另有真实模型服务链。证据及最终判断见 [A／B／C 总结验收](../acceptance/2026-09-07-frontend-experience-integration-acceptance-cn.md)。结论：部分通过，完整端到端及各类型使用仍有待验项。

## 7. 可直接分发的任务说明

### 给 Agent A

实现首页紧凑继续入口。读取本说明及 A 设计、计划、验收文档，遵循文件所有权。首页必须直接显示上次课程名称并只有一个继续操作；完成师生端、记录隔离和恢复验证。交付独立提交与真实验收结果给 Agent B 集成，不修改共享聊天文件。

### 给 Agent B

实现知识点上下文与澄清，并负责三项最终集成。读取本说明及 B 三份文档，首先向 C 交付实际上下文／澄清契约。用户说“为当前课程生成资料”按所处知识点执行，不明确必须追问。拥有共享聊天协议及调度入口，接入 C 服务与组件，合入 A 提交后完成组合验收。不要只改提示词或只测旧 runtime。

### 给 Agent C

实现已有资料的 Agent 修改。读取本说明及 C 三份文档，先与 B 确定实际服务和引用契约。完成按钮与自然语言入口、真实原文读取、不明确时追问、版本保存和各类型覆盖。不要将报告示例擅自缩为唯一支持类型。共享 ChatPanel／请求层由 B 接入，你提供独立模块、接入清单和真实验收结果。

B 集成证据与限制：[B 验收记录](../acceptance/2026-09-07-knowledge-context-acceptance-cn.md)。C 原记录的跨页引用竞态已由 B 在共享入口修复，后续两尺寸浏览器测试通过；未改写 C 原始验收记录。
