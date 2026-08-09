# 学生端引导式教学 Agent 与真实能力优化执行计划

> 日期：2026-08-10
> 状态：待实施
> 对应 SPEC：`docs/superpowers/specs/2026-08-10-student-guided-learning-agent-capability-optimization-design.md`
> 验收文档：`docs/acceptance/2026-08-10-student-guided-learning-agent-capability-optimization-acceptance.md`
> 问题基线：`docs/acceptance/2026-08-10-student-capability-real-e2e.md`

## 0. 阶段原则

1. **每项工作先查教师端。** 先找页面、接口、服务、测试和真实验收证据，再决定直接复用、抽到 shared 或补角色适配。
2. **共享内核，不建学生分叉。** 不新增 StudentPlanner、StudentExecutor、StudentRAG 或学生专用资源生成器。
3. **先修数据事实，再优化对话。** 个人知识、深度研究和 RAG 范围未正确前，不用 Persona 结果掩盖数据问题。
4. **资源生成只回归，不重写。** 现有页面闪卡和 Agent 闪卡/小游戏已经真实通过；除非失败证据指向生成器，否则不改生成正文能力。
5. **角色来自认证。** 客户端角色、文档 owner、课程范围均不能成为服务端授权事实。
6. **测试先行。** 每个 P0/P1 先建立失败测试，再实现，再跑教师与学生双角色回归。
7. **真实 E2E 才能签收。** Mock、工具名称出现、HTTP 200 或 Job accepted 都不等于能力完成。

## 1. 执行顺序

```text
教师端复用审计与基线冻结
→ 个人知识索引修复
→ 深度研究个人归档
→ RAG 范围强隔离
→ 认证角色贯通与学生 Persona
→ 共享前端状态修复
→ 学生 Agent 智能评测
→ 真实 E2E、教师回归与发布验收
```

前三项为知识数据平面 P0，必须在 Persona 和视觉优化前完成。

## 2. 通用 Teacher-first 检查清单

每个 Task 开始前填写：

- [ ] 教师端对应页面/组件在哪里？
- [ ] 教师端对应 API/服务在哪里？
- [ ] 教师端已有单元、集成、真实 E2E 是什么？
- [ ] 可以直接复用哪些代码？
- [ ] 哪些代码应从 teacher 目录移动到 shared，而不是复制？
- [ ] 学生真正不同的是 Persona、权限、来源还是页面文案？
- [ ] 计划新增的文件是否会形成第二套业务实现？
- [ ] 教师端回归命令和通过证据是什么？

每个 Task 的提交说明必须附一段“复用结论”。没有复用结论不得合并。

## Task 0：冻结真实基线并建立复用台账

**目标：** 固定当前通过/失败事实，形成逐能力教师端复用地图。

**Review：**

- `docs/acceptance/2026-08-10-student-capability-real-e2e.md`
- `docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`
- `docs/acceptance/2026-08-09-grounded-agent-and-multimodal-resource-generation.md`
- `src/stitch/student/StudentApp.tsx`
- `src/stitch/pages/AIWorkspace.tsx`
- `api/src/app/chat/`
- `api/src/app/services/personal_knowledge_service.py`
- `api/src/app/services/deepsearch_service.py`

**Create：**

- `docs/architecture/student-teacher-capability-reuse-ledger.md`
- `api/src/tests/chat/runtime/fixtures/student_agent_cases.yaml`

**步骤：**

- [ ] 记录当前 commit、服务配置、可用 Provider 和已有真实任务证据。
- [ ] 将 AI 问答、课程知识、AI课堂、资源管理、个人知识、深度研究逐项映射到教师/shared 实现。
- [ ] 标出硬编码教师角色、学生包装层、重复旧学生组件和无范围旧数据。
- [ ] 为 STU-E2E-001—011 建立 issue-to-test 映射。
- [ ] 先运行教师 Agent 目标回归和学生现有权限/资源回归，保存基线数字。
- [ ] 建立 60+ 学生 Agent 用例骨架，本 Task 不调整期望以制造通过。

**完成证据：** 复用台账覆盖全部范围；每个问题都有目标测试；优化前基线可重复。

## Task 1：修复个人知识库索引与错误收口

**目标：** 关闭 STU-E2E-001，使个人资料真实可检索，并保留具体失败原因。

**先查教师端：** 复用课程知识文档的生命周期、任务状态、索引重试和 RAG resolver；只改变个人访问域，不复制索引器。

**重点文件：**

- Modify: `api/src/app/services/personal_knowledge_service.py`
- Modify: `api/src/app/services/knowledge_document_service.py`
- Modify: `api/src/app/services/platform_task_handlers.py`
- Modify: `api/src/app/services/durable_task_executor.py`
- Modify: `api/src/app/api/personal_knowledge.py`
- Modify: `src/stitch/api/personalKnowledge.ts`
- Modify: `src/stitch/student/pages/StudentPersonalKnowledge.tsx`
- Modify: `api/src/tests/services/test_personal_knowledge_service.py`
- Modify: `api/src/tests/test_personal_knowledge_api.py`
- Create: `api/src/tests/services/test_personal_knowledge_index_lifecycle.py`

**步骤：**

- [ ] 写测试证明个人文档持久化为 `library_type=personal`、`scope_type=personal`、`scope_id=personal:<owner>`。
- [ ] 用唯一事实 Markdown 写真实索引测试，要求 ready、chunk_count > 0、index key 可解析。
- [ ] 写索引异常测试，要求文档和 Job 都保存 `RAG_INDEX_FAILED`，durable executor 不覆盖原错误。
- [ ] 修复 `scope_type="course"` 等错误元数据。
- [ ] 收敛 `run_index_job` 与 `_completed_public_result` 的终态：业务失败不能再次变成通用执行失败。
- [ ] 修复失败重试，确保同一 document ID 产生新 attempt，不复制文档。
- [ ] 验证删除同时清理个人索引，且课程索引不受影响。
- [ ] 运行教师课程文档索引回归，证明共享生命周期未退化。

**完成证据：** 学生真实上传文档可被唯一问题命中；错误注入能显示真实原因；教师课程索引回归通过。

## Task 2：把深度研究统一归档到个人知识库

**目标：** 关闭 STU-E2E-002、007、008，使研究结果可管理、可索引、可用于个人 RAG。

**先查教师端：** 保留现有 Bocha/Tavily 搜索、rerank、抽取、图片本地化和 SourcePanel 流程；只替换归档服务与状态契约。

**重点文件：**

- Modify: `api/src/app/services/deepsearch_service.py`
- Modify: `api/src/app/deepsearch_importer.py`
- Modify: `api/src/app/api/deepsearch.py`
- Modify: `api/src/app/schemas/deepsearch.py`
- Modify: `src/services/deepsearch.ts`
- Modify: `src/components/teacher/SourcePanel.tsx`
- Modify: `api/src/tests/chat/test_deepsearch_service_websearch.py`
- Modify: `api/src/tests/chat/test_deepsearch_importer.py`
- Create: `api/src/tests/chat/test_deepsearch_personal_archive.py`

**步骤：**

- [ ] 写测试证明 authenticated owner 不可由请求覆盖。
- [ ] 把成功抓取结果转换为个人知识文档，复用 Task 1 的 PersonalKnowledgeService 和索引任务。
- [ ] 返回 personal document IDs、index job IDs、成功/失败来源和质量摘要。
- [ ] 禁止新研究结果继续写入无 scope 的旧 RAG 文档目录。
- [ ] 对 min_sources、官方来源、抽取成功数和 provider 降级生成 succeeded/partial/failed 终态。
- [ ] 修复 crawl result/history 的 owner 过滤，其他用户不能通过 batch ID 读取研究结果。
- [ ] SourcePanel 展示搜索、抽取、归档、索引四阶段；完成后保留结果和个人知识入口。
- [ ] 已完成任务关闭弹窗不再显示“已取消”。
- [ ] 教师端运行同一深度研究流程，确认其结果也进入教师个人知识库而不是课程库。

**完成证据：** 学生与教师研究结果分别只进入自己的个人知识库；结果满足或明确报告来源约束；页面状态与后端一致。

## Task 3：建立严格的课程/个人 RAG 范围

**目标：** 关闭 STU-E2E-003、009、010，消除知识污染和越权检索。

**先查教师端：** 复用现有 RAG resolver、课程知识索引和 selected documents 校验；把范围解析收敛到 shared 服务，不新建学生 RAG。

**重点文件：**

- Modify: `api/src/app/chat/domain/capability_policy.py`
- Modify: `api/src/app/chat/application/request_normalizer.py`
- Modify: `api/src/app/integrations/rag_client.py`
- Modify: `api/src/app/chat/tools/agent_tools.py`
- Modify: `api/src/app/chat/runtime/fast_chat_runtime.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/retrieval.py`
- Modify: `api/src/modules/rag_v2/rag_main/system.py`
- Modify: `src/components/teacher/SourcePanel.tsx`
- Modify: `src/components/teacher/ChatPanel.tsx`
- Create: `api/src/tests/chat/test_rag_access_scope.py`
- Create: `api/src/tests/chat/runtime/test_student_rag_scope.py`

**步骤：**

- [ ] 扩展并测试 `none/course_auto/personal_auto/selected_documents` 四种显式范围。
- [ ] `course_auto` 只允许当前课程发布知识；`personal_auto` 只允许当前 owner 个人知识。
- [ ] selected documents 对每个 ID 执行课程成员/个人 owner 校验，允许合法显式组合。
- [ ] 空/未知 scope 文档 fail closed，不能进入任何 auto 检索。
- [ ] 引用按文档 ID/URL 去重，并标注课程、个人、网络来源。
- [ ] 强制 RAG 无相关证据时返回“资料不足”，不展示无关引用。
- [ ] 课程知识标签隐藏个人上传按钮；个人标签保留个人上传。
- [ ] 写 T1/S1/S2 和跨课程负向测试，包括猜测文档 ID、无 scope 旧文档和伪造 course_id。
- [ ] 执行存量文档范围 dry-run 审计；不自动迁移无法判断的数据。

**完成证据：** 课程 RAG 绝不命中个人文档；个人 RAG 绝不命中课程文档；显式组合只返回有权文档；负向用例全部拒绝。

## Task 4：贯通认证角色并启用学生 Persona

**目标：** 让 Fast 和 Agent 两条真实路径都按认证角色选择 Persona，学生成为引导式教学助手，教师行为不变。

**先查教师端：** 复用现有 `PersonaPolicy`、FastChatRuntime、ReActAgent、任务契约和验证器；删除角色硬编码，不复制运行时。

**重点文件：**

- Modify: `api/src/app/chat/api/routes_v2.py`
- Modify: `api/src/app/chat/domain/contracts.py`
- Modify: `api/src/app/chat/domain/persona_policy.py`
- Modify: `api/src/app/chat/application/request_normalizer.py`
- Modify: `api/src/app/chat/runtime/planning/task_contract_extractor.py`
- Modify: `api/src/app/chat/runtime/fast_chat_runtime.py`
- Modify: `api/src/app/chat/runtime/nodes/prompts.py`
- Modify: `api/src/app/chat/runtime/react_agent.py`
- Modify: `api/src/app/chat/runtime/verification/plan_verifier.py`
- Create: `api/src/tests/chat/runtime/test_persona_policy.py`
- Create: `api/src/tests/chat/runtime/test_authenticated_actor_role.py`
- Create: `api/src/tests/chat/runtime/test_student_guided_dialogue.py`

**步骤：**

- [ ] 先写测试证明当前 student 实际得到 teacher contract/prompt。
- [ ] HTTP 层从 token 注入 owner 和 system_role；忽略客户端 actor_role。
- [ ] `ChatRequestV2` 和 `TeachingTaskContract` 保留认证派生的 actor_role。
- [ ] Fast Chat 从 request 选择 persona，不再固定 `BASE_TEACHER_SYSTEM_PROMPT`。
- [ ] ReAct system content 从 request 选择 persona，不再固定教师 `AGENT_SYSTEM_PROMPT`。
- [ ] 实现 explain/coach/check/task 响应策略和三级提示状态；不改变工具计划。
- [ ] task 模式的明确资源任务直接执行，不触发教学反问。
- [ ] Persona audit 检查多余反问、错误教师称呼、明确任务阻塞、无内容式提示和执行事实冲突。
- [ ] 对同一输入分别以 teacher/student 运行，断言工具轨迹一致、语气策略不同。
- [ ] 运行教师 80 例及现有真实 Agent 基线，确认教师 Persona 无漂移。

**完成证据：** student/teacher 由认证角色确定；Fast/Agent 均正确；共享工具轨迹不因 Persona 分叉；教师回归通过。

## Task 5：修复共享前端状态与学生权限呈现

**目标：** 关闭 STU-E2E-004、005、006、009、011，使页面状态与共享后端事实一致。

**先查教师端：** AIWorkspace、SourcePanel、ChatPanel、StudioPanel、AgentActivityPanel、CourseShell、资源和课堂页面均从教师主线复用；修改共享组件的角色参数和状态收口，不另写学生版。

**重点文件：**

- Modify: `src/stitch/student/shell/StudentShell.tsx`
- Modify: `src/stitch/pages/AIWorkspace.tsx`
- Modify: `src/components/teacher/ChatPanel.tsx`
- Modify: `src/components/teacher/SourcePanel.tsx`
- Modify: `src/components/teacher/StudioPanel.tsx`
- Modify: `src/components/teacher/AgentActivityPanel.tsx`
- Modify: `src/services/teacher/chatV2.ts`
- Modify: `src/store/teacher/useStore.ts`
- Create/Modify: 对应组件测试和 `tests/e2e/student-*` 用例

**步骤：**

- [ ] 用稳定 course ID/summary 比较修复 StudentShell 重复 setSelectedCourse。
- [ ] RAG 开关与发送使用同一原子 capability snapshot；立即点击发送也正确。
- [ ] `result/done/error/cancelled` 统一收口计划和工具状态；最终答案出现时不再显示进行中。
- [ ] SourcePanel 根据认证角色和当前 tab 显示上传/管理能力。
- [ ] 课程只读页面不渲染学生写操作，教师端操作保持可用。
- [ ] 深度研究完成后刷新个人知识，失败/partial 保留具体来源结果。
- [ ] 消除 `Maximum update depth exceeded`、重复请求和首次瞬时 fetch 失败。
- [ ] 用真实角色分别运行教师/学生同一组件 E2E，而不是维护两套选择器和模拟页面。

**完成证据：** 学生页面无 React 循环；能力、计划、研究状态稳定；教师共享页面无回归。

## Task 6：建立学生 Agent 智能评测与最小优化循环

**目标：** 用版本化评测证明 Agent 足以完成学生学习任务，而不是只证明提示词存在。

**先查教师端：** 复用 `api/src/app/chat/evals/` runner、结构化 evaluator、五次重复和双 Provider 脚本；新增学生数据集和 Persona evaluator，不复制 runner。

**重点文件：**

- Modify: `api/src/app/chat/evals/`
- Create: `api/src/app/chat/evals/student/cases.yaml`
- Create: `api/src/app/chat/evals/student/evaluators.py`
- Create: `api/src/scripts/eval_student_agent.py`
- Create: `api/src/scripts/smoke_student_agent_tools.py` 或将教师脚本参数化为通用角色脚本
- Create: `api/src/tests/chat/runtime/test_student_agent_eval_evaluators.py`

**步骤：**

- [ ] 优先参数化教师 eval/smoke 脚本；只有无法合理参数化时才建立薄学生入口。
- [ ] 完成至少 60 个版本化用例和类别配额。
- [ ] 规则评分：工具、范围、引用、反问数、任务阻塞、完整答案满足、角色称呼和终态事实。
- [ ] LLM Judge 只评价解释清晰度、提示有效性、误解诊断和教学适切性。
- [ ] 建立 explain/coach/check/task 四模式对照和提示等级多轮用例。
- [ ] 运行 5 次重复，失败按角色、知识范围、工具、记忆、生成和供应商聚类。
- [ ] 在两个可用 Provider 上运行核心子集。
- [ ] 运行 30 轮混合对话：概念解释 → 学生尝试 → 提示升级 → 资源生成 → 状态查询，验证绑定和权限。
- [ ] 只针对失败聚类做最小策略/契约修改；不通过增加冗长提示词掩盖问题。

**完成证据：** 达到 SPEC 第 11 节全部门槛；报告保留重复实验、Provider、失败聚类和修改前后对照。

## Task 7：真实端到端验收与发布门禁

**目标：** 在真实启动服务、真实账号、真实文件、真实 Provider 和真实浏览器中证明完整能力可用。

**重点文件：**

- Modify: `docs/acceptance/2026-08-10-student-guided-learning-agent-capability-optimization-acceptance.md`
- Modify/Create: `tests/e2e/student-guided-agent.spec.ts`
- Reuse/Parameterize: `api/src/scripts/smoke_teacher_agent_tools.py`
- Reuse/Parameterize: `api/src/scripts/smoke_teacher_agent_generation.py`
- Reuse: `tests/fixtures/student-e2e-personal-knowledge-20260810.md`

**步骤：**

- [ ] 启动真实前端和后端，确认健康、Provider、RAG 和 Worker 状态。
- [ ] S1 上传唯一事实文档，等待 ready，并通过个人 RAG 命中唯一短语。
- [ ] T1、S2 和非课程成员均不能读取 S1 文档。
- [ ] S1 发起要求官方/至少 3 来源的深度研究，检查 succeeded/partial、个人归档和引用。
- [ ] 用深度研究结果继续个人 RAG，证明研究闭环。
- [ ] 课程 RAG 回答课程唯一事实，引用中不得出现任何个人文档。
- [ ] selected documents 显式组合本人个人资料和当前课程资料，来源标注正确。
- [ ] 真实验证普通、RAG、Web、RAG+Web Agent 工具轨迹。
- [ ] 真实验证 explain/coach/check/task 和提示升级多轮对话。
- [ ] 页面与 Agent 各生成一个代表性学生资源；补回归闪卡、小游戏和一个通用资源，不全量重跑昂贵生成器除非共享生成代码发生变化。
- [ ] 教师确认学生资源不可见；课程共享数量不变；学生教案/博客接口 403。
- [ ] 重载页面和重启后端，确认会话、计划、Job 和材料状态可恢复。
- [ ] 运行教师 Agent、课程知识、资源和课堂真实回归。
- [ ] 填写真实耗时、trace、Job、材料、文档和来源证据；清理或明确保留测试数据。

**完成证据：** 验收文档所有 P0/P1 为通过；没有以模拟替代真实能力；教师回归无新增失败。

## 3. 建议提交边界

为降低共享代码风险，建议按以下独立提交：

1. `fix: make personal knowledge indexing authoritative`
2. `fix: archive deep research into personal knowledge`
3. `fix: enforce explicit rag access scopes`
4. `feat: apply authenticated student persona to shared agent`
5. `fix: converge student shared workspace state`
6. `test: add student guided-agent evaluation suite`
7. `test: record student capability release acceptance`

每个提交只包含相应测试与文档更新。真实运行产生的索引、Job、材料和缓存文件不得进入提交。

## 4. 阶段停止条件

出现以下任一情况，停止进入下一 Task：

- 个人索引仍不能返回真实唯一事实；
- 深度研究仍产生无 scope 文档；
- 课程 RAG 能命中个人资料；
- actor role 仍可由客户端伪造；
- 为学生新增了重复的 Planner/Executor/生成器；
- 教师端目标回归出现未解释失败；
- Agent 最终声明与 Job/材料事实不一致；
- 真实 Provider 不可用却准备以 Mock 结果签收。

## 5. 最终交付物

- [ ] 教师/学生能力复用台账；
- [ ] 知识数据迁移 dry-run 报告；
- [ ] 个人知识、深度研究、RAG 范围修复及测试；
- [ ] 认证角色贯通和学生 Persona；
- [ ] 共享前端状态修复；
- [ ] 60+ 用例版本化学生 Agent 数据集；
- [ ] 五次重复、双 Provider、30 轮对话报告；
- [ ] 真实端到端验收记录；
- [ ] 教师端回归记录；
- [ ] 测试数据清理或保留清单。
