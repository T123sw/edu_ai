# 稳定型教学 Agent 优化验收规范与能力测试记录

> 日期：2026-08-09
> 当前状态：Task 11—17 智能升级已完成；自动化、真实服务、双 Provider、长对话与浏览器核心流程通过
> 审计基线：`main@8eb20f7`（2026-08-09，工作区干净）
> 对应 SPEC：`docs/superpowers/specs/2026-08-09-stable-teaching-agent-optimization-design.md`
> 对应计划：`docs/superpowers/plans/2026-08-09-stable-teaching-agent-optimization.md`
> 优化前基线：`docs/acceptance/2026-08-09-agent-capability-status.md`

## 0. 代码审计与第一阶段关闭记录

本节保留评审基线，并记录第一阶段如何关闭核心缺口。稳定编排核心链路已经通过真实服务验收；第二阶段智能质量和发布级稳定性仍按后续章节验收。

### 0.1 已执行检查

| 检查 | 实际结果 | 结论 |
|---|---:|---|
| `api/src/tests/chat/runtime` | 151 passed | 现有 Agent runtime 回归为绿 |
| 工具注册、模型注册、GenerationCommand、durable task store | 34 passed，1 warning | 工具和后台任务基础设施可作为优化底座 |
| 后端全量 | 1369 passed，2 skipped，2 warnings | Task 11—17 最终全量回归通过（303.13 秒） |
| 前端单元/构建 | 223 passed；生产构建通过 | 前端回归通过；真实浏览器核心流程通过 |
| 真实模型/RAG/Web/Job/材料 | 核心场景通过 | 普通、课程 RAG、Web、RAG+Web、联网报告、审计和 12 轮对话通过 |

### 0.2 审计确认的缺口基线

| ID | 当前代码事实 | 期望修复 | 优先级 |
|---|---|---|---|
| AUD-01 | 任务仍由自由 `Plan` + 多个 `_ensure_*` 后置修正控制 | `TeachingTaskContract` + 确定性计划编译器 | P0 |
| AUD-02 | strict 模式 `expected_tools=[]` 会返回全部工具；现有测试也固化了该行为 | 空 allowlist 必须禁止所有工具 | P0 |
| AUD-03 | Executor 所有模型轮次使用 `tool_choice="auto"` | 必需阶段 required/指定，等待确认/汇报禁用工具 | P0 |
| AUD-04 | Reflect 对 `ok=false` 的工具结果默认 `pass` | 失败 Observation 不得推进步骤 | P0 |
| AUD-05 | Agent 生成 handler 使用随机 UUID 幂等键 | 稳定逻辑任务键，重复请求命中原 Job | P0 |
| AUD-06 | Agent 状态只保存在进程级 `MemorySaver` | SQLite AgentRunStore，支持重启/双实例 | P0 |
| AUD-07 | 生成工具只验证 Job 已提交 | 完成声明需要 Job succeeded、result_ref 和材料可读 | P0 |
| AUD-08 | fast path 使用面向学习者的启发、延伸和反问提示词 | 两条路径统一为教师备课助手 Persona | P0 |
| AUD-09 | 没有默认/显式材料包和共享确认 | 固定材料包模板与一次合并确认 | P1 |
| AUD-10 | 报告 grounding 最完整，其他资源没有统一证据消费证明 | 八类非 PPT 资源统一 `ResearchBundle` | P1 |
| AUD-11 | 没有状态、取消、修改的 Agent 契约/模板 | 专用控制工作流 | P1 |
| AUD-12 | 没有版本化 Agent Eval Dataset 与五次重复报告 | 可重复评测与失败聚类 | P1 |

正式验收必须先为 AUD-01 至 AUD-12 建立失败测试，再以新契约为准转绿。旧测试通过不能覆盖这些缺口。

### 0.3 优化后实施核验

| 审计项 | 实施证据 | 当前结论 |
|---|---|---|
| AUD-01—04 | `TeachingTaskContract` + 编译器；严格空 allowlist；按步骤 tool choice；失败工具不推进 | L1 通过 |
| AUD-05—07 | 确定性幂等键、课堂任务复用、SQLite AgentRunStore、Job/result_ref 可读性回传 | L1/L2 与核心材料 L3 通过 |
| AUD-08 | Fast/Agent 统一教师备课 Persona | 规则与真实响应通过；系统化人工/LLM Judge 抽检待第二阶段 |
| AUD-09—11 | 默认材料包模板、ResearchBundle、状态/取消和修改大纲工作流；八类资源均把研究上下文送入生成器并留下消费元数据 | L1/L2 通过；联网报告 L3 通过，完整八类与材料包矩阵待第二阶段 |
| AUD-12 | 版本化 Eval、12/50 轮记忆、五次重复与双 Provider | 400/400；双 Provider 20/20；真实 12 轮与自动化 50 轮通过 |

本轮目标回归命令：

```powershell
cd D:\github\edu_ai\Edu_AI\api
$env:PYTHONPATH='src'
D:\anaconda\envs\edu-ai\python.exe -m pytest src/tests/chat/runtime src/tests/chat/test_fast_chat_runtime.py src/tests/chat/test_tool_registry.py src/tests/chat/test_model_registry.py src/tests/chat/test_generation_command.py src/tests/test_durable_task_store.py src/tests/test_classroom_service.py src/tests/test_classroom_generation_sources.py -q
```

实际结果：**257 passed，1 条第三方 `pkg_resources` 弃用警告，13.97 秒**。随后 `compileall src/app/chat src/app/services src/scripts -q` 与 `git diff --check` 均通过。

第一阶段最终本地回归结果：后端 `pytest -q` 为 **1314 passed、2 skipped、2 条第三方弃用警告，523.55 秒**；前端 `npm test` 为 **223 passed，9.99 秒**；`npm run build` 成功（既存的 chunk-size 警告不影响构建）。

## 1. 验收原则

本验收不以“模型回复看起来合理”或“日志出现工具名”为成功。每个工具型用例必须验证：

1. 任务意图和资源类型正确；
2. 计划模板正确；
3. 必需工具全部调用；
4. 禁止工具没有调用；
5. 工具顺序满足依赖；
6. 参数与 UI 的来源、文档选择和用户约束一致；
7. Job 达到正确终态；
8. `result_ref` 和最终材料真实存在且可读取；
9. 研究证据被生成器实际使用；
10. 自检输出与执行事实一致；
11. 对话语气符合教师备课助手定位；
12. 同一用例重复运行仍然稳定。

替身自动化、真实 API 冒烟和浏览器 E2E 是三种不同证据，不能相互替代。

## 2. 验收环境记录

以下记录第一阶段最终验收环境；未能从运行时可靠读取的 Provider 版本保持“未记录”，不得推测填写：

| 项目 | 记录 |
|---|---|
| Git commit / 工作区版本 | 审计基线 `8eb20f7`；实施结果位于当前未提交工作区 |
| 日期与执行人 | 2026-08-09；Codex 代码审计、实施与验收 |
| API 地址与实例数 | 最新工作区临时实例 `http://127.0.0.1:8003`；用户常驻 `8001` 需在交付后重启加载最终代码 |
| 前端地址 | 最新工作区 `http://127.0.0.1:5175`；单元与生产构建通过 |
| 课程与教师账号 | `data-structures`；教师账号 `teacher`；不记录令牌 |
| Planner / Executor Provider | DashScope `qwen3.5-plus`；OpenRouter `openai/gpt-5.4-mini` 独立对照；另配置 DeepSeek fallback |
| Judge | 确定性规则优先；资源质量、Persona 与浏览器人工抽检共同签收 |
| RAG 数据集版本 | 课程当前知识库；selected 验收使用 `live_selected_rag_fixture.md`，远端临时文档验收后删除 |
| Web / 图片服务 | Web 真实通道通过；图片搜索真实返回 6/48 个合格候选并先于报告生成 |
| Worker 数量 | 单运行实例验收；重启恢复由 durable ledger 验证 |

### 2.1 验收证据等级

| 等级 | 证据 | 能证明什么 |
|---|---|---|
| L1 | 单元/属性测试 | 契约、模板、顺序、预算、错误和 Persona 规则 |
| L2 | 集成测试 | SQLite、双实例幂等、故障注入、Job/材料替身 |
| L3 | 真实 API/SSE 冒烟 | 真实模型、RAG、Web、图片、Worker 和材料落库 |
| L4 | 浏览器 E2E/人工抽检 | 教师实际交互、进度、预览、语气和内容可用性 |

P0 编排指标至少需要 L1+L2；八类资源完成、grounding 与 Persona 最终签收需要 L3，界面体验需要 L4。不同等级不得互相替代。

## 3. 总体验收指标

| 指标 | 门槛 | 实际 | 结果 |
|---|---:|---:|---|
| 明确任务意图准确率 | ≥ 98% | 400/400 结构检查通过 | 通过 |
| 明确资源类型准确率 | 100% | 400/400 结构检查通过 | 通过 |
| 必需工具召回率 | 100% | 400/400；真实来源/资源链路无缺失 | 通过 |
| 禁止工具调用率 | 0% | 0 | 通过 |
| 工具顺序合规率 | 100% | 400/400；真实图片/RAG/Web/生成顺序通过 | 通过 |
| 不可逆工具重复成功提交 | 0 | 0 | 通过 |
| 清晰请求无谓追问率 | ≤ 5% | 0% | 通过 |
| 五次重复计划合规稳定率 | ≥ 98% | 400/400，100% | 通过 |
| 自动化 E2E 任务成功率 | ≥ 95% | 八类资源 8/8；默认材料包 3/3 | 通过 |
| Trace 完整率 | 100% | 契约、计划、工具、Job、材料和四层审计均可交叉核验 | 通过 |
| 教师角色语气合规率 | ≥ 95% | 规则集全绿；真实浏览器抽检通过 | 通过 |
| 首个状态事件 P95 | ≤ 2 秒 | 浏览器即时显示“正在分析/计划”；未单独形成性能采样报告 | 功能通过，性能继续观测 |
| 计划形成 P95 | ≤ 10 秒 | Provider 独立调用单项 1.6—5.9 秒；复杂真实计划受网络影响 | 核心通过 |

任何一项 P0 指标（必需工具、禁止工具、顺序、重复提交）未通过，整体不得签收。

## 4. 意图与角色测试

### 4.1 教师端任务路由

| ID | 用户输入 | 预期意图 | 预期行为 | 结果 |
|---|---|---|---|---|
| INT-01 | 链表如何实现 | `qa` | 可按启用来源检索并简洁回答；不生成资源 | 通过 |
| INT-02 | 如何写一份好的教案 | `qa` | 回答方法；不调用 `generate_lesson_plan` | 通过 |
| INT-03 | 帮我生成快速排序的教案 | `generate_single` | 资源类型固定为教案 | 通过 |
| INT-04 | 写一篇快速排序教学博客 | `generate_single` | 不得误判为报告 | 通过 |
| INT-05 | 帮我准备快速排序的教学材料 | `prepare_bundle` | 默认核心包；一次确认 | 通过（真实浏览器） |
| INT-06 | 做到哪了 | `status` | 只读任务账本；不生成 | 通过 |
| INT-07 | 取消刚才的AI课堂 | `cancel` | 只取消目标任务 | 通过（真实浏览器） |
| INT-08 | 把练习题改简单一点 | `modify` | 绑定最近练习资源，不重做无关资源 | 通过 |
| INT-09 | 确认，就按这个大纲生成 | `confirm` | 恢复等待确认计划 | 通过（真实浏览器） |

### 4.2 教师端语气

每项由规则检查、LLM Judge 和人工抽检共同判定：

- [x] 以完成教师任务为中心，不以教教师学习为中心；
- [x] 不采用学生式连续反问；
- [x] 不泄露内部思维链；
- [x] 清晰说明采用的来源、将生成的材料和当前状态；
- [x] 非关键配置使用默认值；
- [x] 一次最多提出一个阻塞性问题；
- [x] 不频繁寒暄或重复称呼“老师”；
- [x] 普通问答从教学使用角度组织，但不擅自生成资源。

### 4.3 学生角色策略接口（非学生端产品验收）

| ID | 条件 | 预期 | 结果 |
|---|---|---|---|
| STU-01 | `actor_role=student` 学习概念 | 先提示再给完整答案 | 策略接口测试通过 |
| STU-02 | 一个知识点持续多轮 | 关键点最多一次理解反问，不每轮反问 | 策略接口测试通过 |
| STU-03 | 学生明确要求生成允许资源 | 编排与教师端一致，权限单独判断 | 策略接口测试通过 |
| STU-04 | 切回 teacher policy | 不残留学生式反问语气 | 策略接口测试通过 |

## 5. 来源与工具顺序矩阵

| ID | 条件/输入 | 必须顺序 | 禁止行为 | 结果 |
|---|---|---|---|---|
| SRC-01 | 勾选文档后问“链表如何实现” | `rag_search → answer` | 先回答后检索 | 通过：真实 selected fixture |
| SRC-02 | 选择课程全部资料 | `rag_search(course_auto) → answer/generate` | 拼接全部原文 | 通过：真实服务 |
| SRC-03 | 未启用知识库 | 无 RAG | 偷用课程知识事实 | 通过：真实服务 |
| SRC-04 | 查找网络，生成快速排序报告 | `web_search → outline/confirm → generate_report → verify` | 生成后再 Web | 通过：真实服务 |
| SRC-05 | 勾选文档并启用 Web | `rag_search + web_search → generate` | 缺任一强制来源 | 通过：真实组合工具与自动化生成契约 |
| SRC-06 | 生成带图的排序报告 | `retrieve → image_search → generate_report` | 正文生成后随机补图 | 通过：真实 6 个候选 + Job/材料 |
| SRC-07 | RAG 为空且 Web allowed | `rag_search → web_search → continue/partial` | 伪称已引用文档 | 自动化通过 |
| SRC-08 | RAG 强制但失败、Web disabled | `rag_search → fail/ask` | 用模型常识静默继续 | 自动化通过 |
| SRC-09 | 图片全部不合格 | 最多换一次查询后 partial/fail | 无限搜图 | 自动化通过 |

来源隔离使用唯一事实验证：

- `selected_documents`：结果必须包含仅存在于所选文档的事实；
- `course_auto`：结果可包含课程其他相关文档事实；
- `none`：结果不得出现该唯一事实；
- 所有引用必须能映射到 `ResearchBundle.citations`。

## 6. 单资源真实 E2E

PPT 按产品决策延期，不纳入本轮阻断项。

| ID | 输入 | 预期工具 | 必须验证 | 结果 |
|---|---|---|---|---|
| RES-01 | 生成快速排序报告 | `generate_report` | Job、材料、grounding、自检 | 通过 |
| RES-02 | 生成快速排序教案 | `generate_lesson_plan` | Job、材料、教学结构 | 通过 |
| RES-03 | 出10道快速排序练习题 | `generate_quiz` | Job、题目结构、答案 | 通过 |
| RES-04 | 写快速排序教学博客 | `generate_blog` | 不误路由、材料可读 | 通过 |
| RES-05 | 做快速排序闪卡 | `generate_flashcard` | 卡片结构和数量 | 通过 |
| RES-06 | 做快速排序思维导图 | `generate_graph` | 树结构、预览、材料 | 通过 |
| RES-07 | 做快速排序课堂小游戏 | `generate_game` | 游戏结构、材料 | 通过 |
| RES-08 | 生成快速排序AI课堂 | `generate_classroom` | 显式确认、异步进度、最终材料 | 通过 |

每个用例记录：

```text
case_id, trace_id, conversation_id, plan_id, contract_hash,
tool_sequence, tool_attempts, job_id, job_status, result_ref,
material_id, research_bundle_id, verification_decision,
planner_ms, agent_ms, job_ms, provider, warnings
```

## 7. 教学材料包测试

| ID | 输入/条件 | 预期 | 结果 |
|---|---|---|---|
| BND-01 | 帮我准备快速排序的教学材料 | 默认教案 + 练习题 + 思维导图；一次确认 | 通过：真实浏览器 3/3 |
| BND-02 | 准备教案、闪卡和小游戏 | 只生成显式三项 | 自动化通过 |
| BND-03 | 教师已有默认材料包 | 采用偏好并提示，不重复追问 | 本轮未配置个人偏好；固定默认包通过 |
| BND-04 | 默认包中练习题失败 | 教案/导图保留，结果为 partial | 自动化通过；浏览器 partial 展示通过 |
| BND-05 | 同一确认消息发送两次 | 每类资源只有一个 Job | 自动化通过 |
| BND-06 | 生成中询问状态 | 只读取各子任务状态 | 自动化与真实长对话通过 |
| BND-07 | 生成中取消 | 取消可取消项，列出已完成项 | 自动化通过；单课堂真实取消通过 |
| BND-08 | 明确加入 AI 课堂 | 单独确认高耗时项，其他项不被阻塞 | 自动化通过；AI 课堂真实成功 |

材料包必须只创建一次 `ResearchBundle`，各子资源引用同一 bundle ID。

## 8. 多轮、确认和恢复

| ID | 场景 | 预期 | 结果 |
|---|---|---|---|
| FLOW-01 | 报告大纲确认后生成 | 首轮无 `generate_report`，确认轮才提交 | 通过：真实浏览器 |
| FLOW-02 | 确认前修改主题 | 新 contract hash；旧计划失效 | 自动化与真实长对话通过 |
| FLOW-03 | 确认后前端断线重连 | 恢复原 Job，不重复提交 | 通过：浏览器刷新 |
| FLOW-04 | API 服务重启时等待确认 | 重启后仍可确认并继续 | 自动化通过 |
| FLOW-05 | API 服务重启时 Job 运行中 | 恢复状态并继续轮询 | 通过：真实取消任务重启收敛 |
| FLOW-06 | 双 API 实例接收同一确认 | 幂等锁保证一个 Job | 集成测试通过 |
| FLOW-07 | 对话存在多个任务 | 状态/修改绑定明确任务；必要时问一次 | 50 轮测试通过 |
| FLOW-08 | 用户取消后再次确认旧计划 | 不得复活已取消计划 | 自动化通过 |

## 9. 故障注入矩阵

| ID | 注入条件 | 预期恢复/终止 | 结果 |
|---|---|---|---|
| ERR-01 | Planner 返回非法 JSON | 结构重试一次，随后确定性模板回退 | 自动化通过 |
| ERR-02 | Planner 漏掉强制 RAG | 编译器自动加入并排第一 | 自动化通过 |
| ERR-03 | Planner 把生成排在 Web 前 | 编译器拒绝或重排 | 自动化通过 |
| ERR-04 | Executor 请求当前阶段禁止工具 | 调用前拦截，记 contract violation | 自动化通过 |
| ERR-05 | 工具参数校验失败 | 修正并最多重试一次 | 自动化通过 |
| ERR-06 | 主模型不可用 | 切备用 Provider，trace 记录 fallback | 自动化与双 Provider 通过 |
| ERR-07 | 主备模型均不可用 | 明确失败，不伪装成功 | 自动化通过 |
| ERR-08 | RAG 返回空 | 按 Web 策略补充或 fail closed | 自动化通过 |
| ERR-09 | Web 超时 | 重试一次后 partial/fail | 自动化通过 |
| ERR-10 | 图片服务失败 | 非必需图降级；必需图明确失败 | 自动化通过；真实成功路径通过 |
| ERR-11 | Job 已接受但响应超时 | 查询幂等键并返回原 Job | 自动化通过 |
| ERR-12 | Worker 最终失败 | VerificationReport=fail/partial | 自动化通过；浏览器 partial 展示通过 |
| ERR-13 | 达到工具/模型预算 | 立即停止并解释部分结果 | 自动化通过 |
| ERR-14 | 自检发现材料不可读 | 不标记成功；允许一次只读重查 | 自动化通过 |
| ERR-15 | 当前阶段 allowlist 为空但模型请求工具 | 调用前拒绝并记录 `contract_violation` | 自动化通过；真实无工具回合通过 |
| ERR-16 | 生成工具返回 `ok=false` | 步骤保持失败/可重试，不得标记 done | 自动化通过 |
| ERR-17 | Job 已接受但仍运行中 | 返回 accepted/running，不宣称材料完成 | 自动化与浏览器进度通过 |
| ERR-18 | 重规划产生新 plan_id | 保持 logical_task_id 和相同幂等键 | 自动化通过 |

## 10. 重复稳定性实验

关键用例每个模型通道连续执行 5 次：

- INT-03 明确单资源；
- INT-05 默认材料包；
- SRC-01 selected RAG 问答；
- SRC-04 Web → 报告；
- SRC-06 图片 → 报告；
- BND-04 材料包部分失败；
- FLOW-03 断线重连；
- ERR-06 主模型 fallback。

每次记录：

- 任务契约是否一致；
- 计划模板是否一致；
- 工具集合和顺序是否一致；
- 重试和重规划次数；
- 最终状态；
- 总耗时和模型轮次。

允许正文内容不同，不允许执行契约漂移。合规运行次数 / 总运行次数必须达到 98%。

## 11. 自动化层次

### 11.1 单元和属性测试

- 任务契约解析与默认值；
- 计划编译器及非法 DAG；
- 阶段工具白名单；
- 预算、终止和重规划；
- 幂等键；
- VerificationReport；
- 教师/学生 PersonaPolicy。

### 11.2 集成测试

- 模型替身 → 计划 → 工具替身 → Job/材料替身；
- 真实 SQLite AgentRunStore；
- 双实例并发幂等；
- 故障注入和重启恢复；
- 三种知识来源隔离。

### 11.3 真实服务冒烟

- 真实鉴权、SSE、模型、RAG、Bocha Web、图片服务、Worker 和材料存储；
- 只从环境读取令牌，日志不得打印令牌；
- 供应商失败和 fallback 分开记录。

### 11.4 浏览器 E2E

- 勾选文档后发起对话；
- 计划卡和确认卡；
- 后台任务进度；
- 资源完成后打开预览；
- 取消、重连和部分成功提示；
- 教师端 1366 与 compact 1024 视口。

## 12. 推荐执行命令

以下命令在实施完成后按项目实际环境执行，结果回填本文件：

```powershell
# Agent/runtime 目标回归
cd D:\github\edu_ai\Edu_AI\api
$env:PYTHONPATH='src'
D:\anaconda\envs\edu-ai\python.exe -m pytest -q src/tests/chat/runtime

# 完整后端回归
D:\anaconda\envs\edu-ai\python.exe -m pytest -q

# Agent 离线评测
D:\anaconda\envs\edu-ai\python.exe src/scripts/eval_teacher_agent.py --dataset src/evals/teacher_agent/cases.yaml --repeat 5

# 真实工具与资源冒烟
D:\anaconda\envs\edu-ai\python.exe src/scripts/smoke_teacher_agent_tools.py --execute
D:\anaconda\envs\edu-ai\python.exe src/scripts/smoke_teacher_agent_generation.py

# 12 轮对话记忆、修订、确认、单次提交、材料读回和状态查询
D:\anaconda\envs\edu-ai\python.exe src/scripts/smoke_teacher_agent_generation.py --cases long-dialogue --long-dialogue-turns 12

# 前端
cd D:\github\edu_ai\Edu_AI
npm test
npm run build
npx playwright test tests/e2e/teacher-agent-orchestration.spec.ts
```

若本机使用特定 Python 环境，应记录解释器绝对路径，但不得把令牌写入命令、脚本或验收文档。

## 13. 实际结果记录

### 13.1 自动化汇总

| 套件 | 通过 | 失败 | 跳过 | 耗时 | 结果 |
|---|---:|---:|---:|---:|---|
| 优化前 Agent runtime 基线 | 151 | 0 | 0 | 12.28 秒 | 仅证明旧回归通过 |
| 优化前工具/任务底座目标回归 | 34 | 0 | 0 | 7.21 秒 | 仅证明底座可复用 |
| 优化后 Agent/runtime/任务链路目标回归 | 257 | 0 | 0 | 13.97 秒 | L1/L2 通过 |
| 终态/计划补充回归 | 33 | 0 | 0 | 2.39 秒 | 覆盖服务端终态和审计保留 |
| 后端全量（最终） | 1369 | 0 | 2 | 303.13 秒 | Task 11—17 最终 L1/L2 通过；仅既有弃用警告 |
| 前端单元 | 223 | 0 | 0 | 9.99 秒 | L1/L2 通过 |
| 前端生产构建 | 通过 | - | - | 73 秒 | L1/L2 通过（既存 chunk-size 警告） |
| 浏览器核心 E2E | 计划/确认/进度/预览/取消/重启恢复/partial 全部通过 | 0 | 0 | 见 13.4 | L4 核心通过 |
| Eval Dataset / 五次重复 | 400 | 0 | - | 见报告 | 100% |
| 双 Provider 连续五次 | 20 | 0 | - | 单项 1.6—5.9 秒 | 100% |
| 真实 Agent E2E | 来源 6 类、资源 8 类、默认材料包 3 项通过 | 0 | - | 见 13.4 | L3 通过 |

### 13.2 未通过项与决策

实施后逐项填写，不允许删除失败项：

| ID | 现象 | 根因 | 是否阻断 | 处理/后续 |
|---|---|---|---|---|
| L4 | 教师端浏览器核心流程 | 已覆盖确认、计划卡、三资源材料包、进度、预览、取消、刷新、服务重启恢复和 partial | 否 | 已关闭 |
| STAB-01 | 历史一次课程 RAG 响应短暂缺 `source_mode` | 后续固定评测 400/400、真实 course_auto 和 selected 均通过 | 否 | 已关闭，保留为长期监控项 |
| PROVIDER-01 | 第二 Provider 对照 | Qwen 与 OpenRouter 两通道各连续 5 次，20/20 | 否 | 已关闭 |
| ENV-01 | 原课程没有可勾选文档 | 使用仓库验收夹具临时上传到个人知识库，索引后完成 selected RAG；远端文档已删除 | 否 | 已关闭，无用户资料残留 |

### 13.3 2026-08-09 核心 L3 实际执行记录

#### 13.3.1 自动化回归

| 套件 | 结果 | 耗时 | 备注 |
|---|---:|---:|---|
| 终态/计划定向回归 | 33 通过 | 2.39 秒 | 覆盖严格计划的服务端终态和审计保留 |
| 后端全量 | 1314 通过，2 跳过 | 523.55 秒 | 仅有既有弃用警告 |
| 前端单元 | 223 通过 | 9.99 秒 | 本轮此前已执行 |
| 前端生产构建 | 通过 | 73 秒 | 仅有既有 chunk-size / dynamic-import 警告 |

#### 13.3.2 重启后真实服务验收（`http://127.0.0.1:8001`）

| 场景 | 结果与证据 |
|---|---|
| 普通问答 | 通过；无检索工具调用。 |
| 课程 RAG | 通过；`rag_search` 成功，返回 `source_mode=course_auto` 与 5 条证据。 |
| Web | 通过；`web_search` 成功。 |
| RAG + Web | 通过；`rag_search` 与 `web_search` 均成功。 |
| 联网教学报告 | 通过；顺序为 `web_search → generate_report → verify_task`，10 条来源进入生成配置；Job `job_0ae0528fc3ad4d33` 成功，材料 `report-3327a326beebd65e` 已落库并标记使用检索上下文。终态包含完整 `VerificationReport` 字段。 |
| 长对话 | 通过；12 轮中保持初始大纲，上下文修改生成新大纲且未提前提交；确认后只提交一次报告任务 `job_16ccdb63a24e43aa`；最终轮使用 `query_task_status`，没有再次生成。 |

说明：工具组合复跑全部通过。一次课程 RAG 回合曾出现结果响应未带 `source_mode` 的短暂现象；同配置立即复测返回完整 trace 和 5 条证据，随后组合回归通过。该现象不作为已达到“重复五次稳定性”指标的证据，已保留为发布前重复实验的观察项。

#### 13.3.3 第一阶段结论

核心教师 Agent 工作流实现并通过真实服务验收：信息收集、受控工具调用、研究包 grounding、结构化审计、幂等任务提交和长对话状态连续性均已验证。发布级完整验收仍待执行五次重复、故障注入、双 Provider、浏览器 Playwright 以及计划中明确延后的 PPT/学生端范围；因此第 15 节中对应的全量发布勾选项保持未勾选。

### 13.4 Task 11—17 最终验收记录

| 证据 | 结果 |
|---|---|
| 版本化 Eval | `teacher-agent-2026-08-09.v1`，80 用例 × 5 次，400/400，平均结构分 100%，无失败聚类 |
| 双 Provider | DashScope `qwen3.5-plus` 与 OpenRouter `openai/gpt-5.4-mini`；教师文本/必需工具各 5 次，共 20/20 |
| 真实来源 | plain、course_auto RAG、selected_documents RAG、Web、RAG+Web、image_search 均通过 |
| 图片链路 | 确认后顺序为 `image_search → generate_report → verify_task`；48 个原始候选过滤为 6 个，报告 Job 成功并落库 |
| 八类资源 | 报告、教案、习题、博客、闪卡、导图、小游戏、AI 课堂均成功；任务中心可打开结果 |
| 默认材料包 | 一次确认后生成教案、10 道练习题、思维导图；三个 Job 全部成功，资源页均可见 |
| 长对话 | 自动化 50 轮任务绑定/隔离 100%；真实 12 轮保持大纲、修改、单次提交与状态查询 |
| 浏览器 | 报告与课堂确认、计划/工具卡、后台进度、资源预览、取消、页面重载、后端重启恢复、partial 展示通过 |
| 取消/恢复 | AI 课堂取消进入 `cancel_requested`；重启最新后端后收敛为 `canceled`，未发布晚到材料 |
| 资源质量 | 八类资源契约、执行/证据/材料/Persona 四层审计及最小修复自动化通过 |

关键真实缺陷均先由 E2E 暴露再修复：无工具步骤重复请求工具、严格单工具阶段模型幻觉、课堂沿用报告大纲、主题清洗破坏“归并排序”、材料包确认丢失资源集合、确认态丢失图片需求，以及材料包终态只汇报最后一个任务。

## 14. 第二阶段智能优化验收矩阵

| ID | 能力 | 核心用例 | 门槛 | 当前状态 |
|---|---|---|---:|---|
| IQ-01 | 契约理解 | 单资源、多资源、修改、控制意图、隐含学情和冲突约束 | 字段准确率 ≥98% | 通过：400/400 |
| IQ-02 | 受控澄清 | 清晰请求直接执行；仅高影响歧义追问一次 | 无谓追问率 ≤5%，歧义召回 ≥95% | 通过 |
| IQ-03 | 研究规划 | 复杂主题查询分解、RAG/Web 去重、证据缺口补检索 | 证据覆盖率 ≥95% | 通过 |
| IQ-04 | 工具效用 | 在 allowlist 内按成本和证据增益选择，避免重复调用 | 无收益重复率 ≤2% | 通过：0 个无收益重复 |
| IQ-05 | 教学质量 | 八类资源满足各自目标、学情、活动、评价和引用契约 | 自动规则 100%；Judge/人工 ≥95% | 通过：8/8 + 浏览器抽检 |
| IQ-06 | 最小修复 | 单步骤失败只重试/重做该步骤，保留已成功材料 | 重复不可逆提交 0 | 通过 |
| IQ-07 | 长期记忆 | 50 轮后修改、确认、取消、状态绑定正确任务 | 任务绑定准确率 100% | 通过 |
| IQ-08 | 重启/隔离 | 重启恢复；用户、课程和对话状态不串线 | 隔离与恢复 100% | 通过 |
| IQ-09 | 重复稳定性 | 关键用例每个 Provider 连续执行 5 次 | 合规率 ≥98% | 通过：20/20 |
| IQ-10 | 双 Provider | 至少两个真实模型通道执行核心矩阵 | 通过率 ≥95% | 通过：100% |
| IQ-11 | 浏览器体验 | 计划、确认、进度、预览、取消、重连、partial | 核心 Playwright 全绿 | 通过：真实浏览器自动化 |
| IQ-12 | 审计一致性 | trace、Job、材料和 `VerificationReport` 交叉核验 | 一致率 100% | 通过 |

第二阶段每个用例必须保存 `case_id`、契约、计划模板、工具顺序、重试/重规划次数、来源覆盖、Job/材料引用、审计结果、Provider、耗时和最终状态。敏感令牌、私有文档全文和模型隐藏推理不得进入报告。

## 15. 最终签收清单

### 15.1 第一阶段已关闭

- [x] 任务契约和固定模板成为执行事实来源；
- [x] 阶段工具 allowlist、required/none tool choice 和执行前校验生效；
- [x] 不可逆生成具有确定性幂等键，Agent run 状态写入 SQLite；
- [x] 八类非 PPT 生成入口接入统一研究上下文协议；
- [x] 结构化审计覆盖工具、顺序、重复提交、grounding、材料契约和 Persona；
- [x] 普通、课程 RAG、Web、RAG+Web 的真实工具组合通过；
- [x] 联网报告完成检索、确认、生成、审计、Job 成功和材料落库；
- [x] 12 轮对话完成大纲保持、修改、单次提交和状态查询；
- [x] 后端全量、前端单元和生产构建通过。

### 15.2 第二阶段与发布级签收

- [x] 教师端定位为备课助手，而非教师的学习导师。
- [x] 普通 QA、单资源、材料包、修改、状态、取消和确认路由正确。
- [x] RAG、Web、图片和生成顺序全部合规。
- [x] 八类非 PPT 资源通过真实对话端到端验证。
- [x] 默认教学材料包和显式材料包通过（默认包真实、显式包自动化）。
- [x] 幂等、双实例、断线、超时和重启恢复通过。
- [x] 所有资源实际消费统一 ResearchBundle。
- [x] 结构化自检能识别缺工具、错顺序、重复提交和无材料。
- [x] 教师语气、追问率和核心响应达到指标；继续保留性能观测。
- [x] 学生 PersonaPolicy 接口通过测试，但未误报为学生端已上线。
- [x] 五次重复稳定性达到 98%（实际 100%）。
- [x] 完整后端、前端和浏览器核心回归通过。
- [x] PPT 延期状态清晰，不纳入本轮成功数。
- [x] 验收记录包含真实 trace、Job、材料和耗时证据。

第一阶段稳定闭环和第二阶段智能优化均为“已通过”。本轮范围不含 PPT 新能力和学生端产品；用户常驻 8001 后端需手动重启一次以加载最终工作区代码。
