# 稳定型教学 Agent 能力优化 SPEC

> 日期：2026-08-09
> 状态：设计完成，尚未实施
> 优先范围：教师端 Agent；学生端仅定义可复用角色策略，不实施学生端产品
> 调研依据：`docs/research/2026-08-09-stable-teaching-agent-open-source-research.md`
> 现状基线：`docs/acceptance/2026-08-09-agent-capability-status.md`
> 执行计划：`docs/superpowers/plans/2026-08-09-stable-teaching-agent-optimization.md`
> 验收规范：`docs/acceptance/2026-08-09-stable-teaching-agent-optimization-acceptance.md`

## 1. 产品定位

### 1.1 教师端

教师端 Agent 是“帮助教师完成备课工作的教学助手”，不是“教教师学习知识的老师”。它的首要职责是减少教师查资料、组织内容、填写配置和等待资源生成的负担。

教师端应表现为：

- 先理解教师要完成的工作，再行动；
- 能自己采用合理默认值，不把资源配置表改写成连续追问；
- 明确告诉教师正在准备什么、还需要什么确认、最终生成了什么；
- 对普通知识问题给出简洁、面向教学使用的答案，不采用学生式循循善诱；
- 不重复讲解显然属于教师专业常识的基础概念；
- 不频繁使用“老师您好”“让我们一步步学习”等增加距离或误判角色的话术；
- 只有缺少会显著改变结果或产生高成本任务的信息时才追问，一次最多问一个问题。

建议语气：

```text
我会先结合已选课程资料梳理快速排序的教学重点，再补充必要案例，
为你准备教案、练习题和一张思维导图。开始生成前我会先给你确认材料结构。
```

不建议语气：

```text
老师，让我们先来学习什么是快速排序。你知道它为什么叫快速排序吗？
```

### 1.2 学生端预留

学生端未来复用同一套意图、计划、工具和验证内核，但切换为“引导式教师”角色：

- 对学习问题优先给提示、示例和检查理解的问题；
- 在一个知识点的关键位置进行反问，而不是每句话都反问；
- 根据学生回答调整提示深度，再给完整结论；
- 资源工具调用规则与教师端一致，但受学生权限和可见资源范围限制。

本阶段不实现学生页面、学生权限或学生 Agent，只建立 `PersonaPolicy` / `InteractionPolicy` 接口和单元测试，避免未来复制整套编排。

## 2. 设计目标

1. 明确任务路由：正确区分普通对话、单资源生成、教学材料包、修改、任务状态、取消和确认。
2. 稳定工具规划：RAG、Web、图片和资源生成按照用户选择与固定依赖顺序执行。
3. 降低模型自由度：模型不再生成任意流程，只填充结构化任务契约；代码将契约编译成模板计划。
4. 有界 ReAct：只在当前阶段内处理观察、补充检索和一次错误恢复。
5. 工具调用可靠：阶段白名单、严格参数、幂等提交、超时、重试和终止条件齐全。
6. 统一研究证据：同一次备课任务只构建一份 `ResearchBundle`，供全部资源生成器复用。
7. 结果可验证：每一步都有机器可判定的成功条件，最终材料必须真实落库且可读取。
8. 角色一致：教师端以完成备课为中心，学生端未来以引导学习为中心。
9. 可评测：建立固定数据集、多次重复实验、故障注入和真实端到端验收。

## 3. 非目标

- 不建设通用自治 Agent、开放式研究 Agent 或代码执行 Agent。
- 不引入 supervisor、critic team、swarm 等多 Agent 架构。
- 不让模型创建新工具、任意 DAG 或长期目标。
- 不追求复杂任务分解、跨天自主执行或无人监督的循环改进。
- 不在本轮实施 PPT 新能力；PPT 继续按产品决策后置。
- 不在本轮实施学生端产品。
- 不更换 LangGraph，不迁移到 Dify、AutoGen、PydanticAI 或其他运行时。

## 4. 总体架构

### 4.1 “工作流在外，Agent 在内”

```mermaid
flowchart LR
    A["用户消息 + UI能力选择"] --> B["任务契约提取"]
    B --> C["确定性计划编译器"]
    C --> D["获取信息阶段"]
    D --> E["准备与确认阶段"]
    E --> F["资源生成阶段"]
    F --> G["结构化自检"]
    G -->|通过| H["结果汇报"]
    G -->|可恢复且未超预算| I["局部 ReAct 恢复"]
    I --> D
    G -->|不可恢复或超预算| J["明确失败/部分成功"]
```

外层阶段和依赖由代码控制；ReAct 只能在当前允许阶段内选择工具。模型不能把生成提前到检索之前，也不能在自检阶段再次提交资源。

### 4.2 单 Agent，而非多 Agent

系统只保留一个面向用户的 Agent。Planner、Retriever、Generator、Verifier 是图节点或服务职责，不是互相对话的独立人格。这样可以减少：

- 模型调用次数；
- 上下文复制；
- 状态同步错误；
- 角色冲突；
- 终止条件不清；
- 调试和验收成本。

## 5. 核心领域契约

### 5.1 `TeachingTaskContract`

模型只负责从自然语言提取以下结构，之后由代码校验和补默认值：

```text
schema_version
actor_role: teacher | student
intent: qa | generate_single | prepare_bundle | modify | confirm | status | cancel
topic
resource_types[]
audience?: string
lesson_duration?: integer
teaching_goals[]
constraints{}
source_mode: selected_documents | course_auto | none
selected_document_ids[]
web_policy: required | allowed | disabled
image_policy: required | allowed | disabled
confirmation_policy: required | optional | none
conversation_refs{}
```

约束：

- `source_mode`、文档 ID、Web 和图片开关以 UI 能力状态为权威，模型不能关闭用户已启用能力；
- 用户明确说出的资源类型覆盖模型分类；
- 模型不得虚构受众、课时和教学目标；缺失时使用课程默认或资源默认；
- 只有高影响缺失项才触发追问；明确单资源任务不得因非必填参数追问。

### 5.2 `CompiledPlan`

计划不再以自由文本步骤为事实来源，而使用固定字段：

```text
plan_id
template_id
contract_version
steps[]:
  step_id
  kind: retrieve_rag | retrieve_web | retrieve_images | prepare_outline |
        await_confirmation | generate_resource | verify | report_result
  required: bool
  depends_on[]
  tool_allowlist[]
  success_predicate
  failure_policy: retry | supplement | partial | stop
  max_attempts
  timeout_seconds
  state: pending | running | awaiting_user | succeeded | failed | skipped
  input_refs[]
  output_refs[]
budgets{}
```

所有计划在执行前通过编译器校验：

- 步骤类型必须属于枚举；
- 依赖必须无环；
- 检索必须先于依赖证据的生成；
- 图片必须先于需要图片的正文/资源组装；
- 确认必须先于需要确认的生成任务；
- 自检必须在所有生成任务之后；
- 每个生成步骤只能包含一个明确资源工具；
- 相同幂等键的生成步骤不能重复。

### 5.3 `ResearchBundle`

一次备课任务共享一份研究包：

```text
topic
course_evidence[]
web_evidence[]
visual_assets[]
citations[]
source_mode
queries[]
quality_summary
missing_evidence[]
created_at
```

所有资源生成器读取同一研究包，而不是各自重新检索或只在命令快照中保存未使用的上下文。

### 5.4 `VerificationReport`

自检输出必须结构化：

```text
plan_compliance
required_tools_satisfied
forbidden_tools_absent
tool_order_valid
duplicate_submission_absent
grounding_valid
artifact_contract_valid
artifact_readable
persona_valid
warnings[]
decision: pass | partial | retry | fail
```

## 6. 意图与计划模板

### 6.1 意图优先级

按以下顺序判定：

1. 取消、状态、确认、修改等工作流控制指令；
2. 用户明确说出的资源类型；
3. “教学材料/备课材料/整套材料”等组合意图；
4. 普通知识或教学设计问答；
5. 仍然模糊时才调用结构化意图模型。

明确关键词由代码规则确定，避免“教学博客”再次被模型误判为报告。

### 6.2 普通问答模板

```text
可选 RAG/Web 获取信息 → 证据检查 → 面向教学使用的简洁回答
```

教师端回答结束可提供一个轻量下一步，例如“需要的话我可以把它整理成课堂讲解提纲”，但不得擅自创建资源。

### 6.3 单资源模板

```text
解析参数
→ 按能力获取 RAG/Web
→ 如资源或用户要求配图则获取图片
→ 如该资源要求确认则准备结构并等待确认
→ 调用唯一资源工具
→ 等待 Job 终态并读取材料
→ 自检
→ 汇报
```

### 6.4 教学材料包模板

用户只说“帮我准备快速排序的教学材料”时，采用低成本默认核心包：

- 教案；
- 练习题；
- 思维导图。

理由：三者覆盖课堂组织、学习检查和知识结构，且不会默认启动耗时很长的 AI 课堂。报告、博客、闪卡、小游戏、AI 课堂需要用户明确提出，或课程偏好中已保存为默认包。

执行过程：

```text
获取共享 ResearchBundle
→ 给出一条简洁材料包确认（核心包、主题、来源）
→ 教案生成
→ 练习题与思维导图可并行生成
→ 逐项自检
→ 汇报全部成功、部分成功或失败项
```

如果教师已保存个人默认材料包，可以直接采用该偏好，并在状态卡中显示“按你的默认材料包准备”，不再追问。

### 6.5 明确的 Web/RAG/图片顺序

- 勾选文档：`rag_search` 是强制步骤，且只检索所选文档；
- 选择课程全部资料：`rag_search` 是强制步骤，在全课程中按主题检索；
- 未选择知识库：不调用 RAG；
- 用户说“查找网络/参考最新资料”：`web_search` 是强制步骤；
- 用户要求配图，或资源模板声明必须有图：`image_search` 在生成前执行；
- RAG 证据不足且 Web 仅为 `allowed`：可执行一次 Web 补充；
- 任何强制检索失败都不得静默用模型常识伪装成检索结果。

## 7. 有界 ReAct 设计

### 7.1 循环结构

```text
Observe（结构化状态与上一步结果）
→ Decide（只在当前 allowlist 中选择下一行动）
→ Act（执行一个或一组无依赖冲突的工具）
→ Verify（代码规则优先）
→ Continue / Retry once / Replan once / Stop
```

### 7.2 预算

默认预算：

- 普通问答：最多 2 个模型轮次、2 次工具调用；
- 单资源：最多 4 个模型轮次、4 次前台工具调用；后台生成 Job 不计入模型轮次；
- 材料包：最多 5 个模型轮次；
- 单步骤最多重试 1 次；
- 整体最多重规划 1 次；
- 不可逆生成工具每个资源最多成功提交 1 次；
- 达到预算时返回部分结果和明确原因，不继续循环。

### 7.3 重规划触发条件

只允许以下情况重规划：

- RAG 返回空结果且 Web 被允许；
- 图片结果全部不合格且存在备用查询；
- 工具明确返回可恢复参数错误；
- 某个材料包子任务失败，但其他子任务仍可继续。

模型回答质量一般、写作风格不理想或“觉得还可以更好”不触发自动重规划。

## 8. 工具契约与执行护栏

### 8.1 阶段工具白名单

| 阶段 | 允许工具 |
|---|---|
| 获取信息 | `rag_search`、`web_search`、`image_search` |
| 准备结构 | `draft_outline` |
| 等待确认 | 无工具 |
| 生成 | 当前计划指定的一个或多个 `generate_*` |
| 自检 | 只读任务/材料读取，不暴露生成工具 |
| 汇报 | 无工具 |

### 8.2 幂等和重复提交防护

每个生成工具调用必须携带：

```text
idempotency_key = conversation_id + plan_id + resource_type + contract_hash
```

- 相同键已存在成功或运行中 Job：返回原 Job，不重复创建；
- 超时只表示前台等待结束，不表示任务失败，不得重新提交；
- 用户修改主题、资源类型或关键配置后生成新的 contract hash；
- 工具结果必须返回 `job_id`、`accepted_at`、`result_ref` 或明确错误码。

### 8.3 错误分类

- `validation_error`：修正参数后重试一次；
- `transient_provider_error`：按现有模型 fallback 和退避策略重试；
- `retrieval_empty`：按策略补 Web 或向用户说明；
- `permission_denied`：立即停止，不重试；
- `job_timeout`：转后台并给任务入口，不重复提交；
- `job_failed`：显示资源类型和失败原因，材料包其他项继续；
- `contract_violation`：停止并记录为系统缺陷。

## 9. 自检策略

自检采用“代码规则优先、模型评价补充”：

### 9.1 必须由代码判定

- required tool 是否全部执行成功；
- 实际工具顺序是否满足依赖；
- 是否出现未授权或非当前阶段工具；
- 是否重复提交；
- Job 是否达到合法终态；
- `result_ref` 是否存在；
- 材料是否可读取；
- RAG/Web/图片证据是否被目标生成器实际消费；
- 输出是否符合资源 schema。

### 9.2 可由模型或人工抽检

- 教学目标与内容是否一致；
- 练习难度是否适合受众；
- 图片与段落是否语义匹配；
- 教师端语气是否简洁、行动导向；
- 学生端未来是否体现提示、反问和渐进式教学。

LLM 自检最多一次，不因风格评分自动重做整份资源。

## 10. 对话与确认策略

### 10.1 不追问的情况

- “生成一份快速排序报告”；
- “按已选文档生成链表教案”；
- “查找网络并生成二分查找的思维导图”；
- 缺少篇幅、难度等有安全默认值的可选配置。

### 10.2 需要一次确认的情况

- 泛化的“准备教学材料”，且教师没有保存默认材料包；
- 报告、教案等需要先确认内容结构的资源；
- 启动 AI 课堂等高耗时任务；
- 用户同时要求多个可能冲突的资源或范围。

确认信息必须合并成一条简洁卡片，不能逐字段提问。

### 10.3 修改、取消和状态

- “把练习题改简单一些”：绑定最近成功或运行中的练习任务，不重新规划无关资源；
- “取消”：取消当前可取消 Job，并返回哪些任务已经完成、哪些已取消；
- “做到哪了”：读取任务账本，不调用生成工具；
- 多个候选任务时只问一次“你指的是哪一项”。

## 11. 角色策略

### 11.1 教师 `PersonaPolicy`

```text
goal: complete_teaching_preparation
default_style: concise_action_oriented
clarification_budget: 1
socratic_mode: off
offer_next_action: true
avoid_basic_tutoring_tone: true
```

教师端响应模板：

- 开始：说明将完成什么和采用哪些来源；
- 等待确认：只展示关键结构和可调整项；
- 运行中：展示任务和进度，不输出内部思维；
- 完成：列出材料、入口、来源使用和警告；
- 失败：说明失败项、已完成项和可执行下一步。

### 11.2 学生 `PersonaPolicy` 预留

```text
goal: guide_learning
default_style: encouraging_guided
clarification_budget: 1
socratic_mode: checkpoint
hint_before_full_answer: true
reflection_question_budget_per_topic: 1
```

学生策略只改变沟通与最终回答，不改变工具执行事实、权限、来源和自检标准。

## 12. 状态持久化与可观察性

当前进程级 MemorySaver 不能跨服务重启保留确认和计划状态。优化后至少持久化：

- `TeachingTaskContract`；
- `CompiledPlan` 与步骤状态；
- `ResearchBundle` 引用；
- 用户确认点；
- Job 与材料引用；
- 重试、重规划和预算消耗；
- 最终 `VerificationReport`。

每次运行产生统一 trace：

```text
trace_id, conversation_id, actor_role, intent, template_id,
model/provider attempts, plan steps, tool calls, durations,
guardrail decisions, job_ids, material_ids, verification, final_status
```

日志默认不保存令牌、完整私有文档正文或不必要的模型隐藏推理。

## 13. 性能与可靠性指标

### 13.1 核心指标

| 指标 | 目标 |
|---|---:|
| 明确任务意图准确率 | ≥ 98% |
| 明确资源类型准确率 | 100% |
| 必需工具召回率 | 100% |
| 禁止工具调用率 | 0% |
| 工具顺序合规率 | 100% |
| 不可逆工具重复成功提交 | 0 |
| 清晰请求无谓追问率 | ≤ 5% |
| 同一用例五次运行计划合规稳定率 | ≥ 98% |
| 自动化 E2E 任务成功率 | ≥ 95% |
| Trace 完整率 | 100% |
| 教师角色语气合规率 | ≥ 95% |

### 13.2 响应目标

- 首个状态事件：本机环境 P95 ≤ 2 秒；
- 任务契约与计划形成：可用模型条件下 P95 ≤ 10 秒；
- 后台资源任务提交后立即返回任务状态，不同步等待 AI 课堂完成；
- 外部供应商耗时单独统计，不与 Agent 编排耗时混为一个指标。

## 14. 关键决策记录

| 决策 | 选择 | 原因 |
|---|---|---|
| Agent 数量 | 单 Agent | 当前任务短且工具固定，多 Agent 增加不稳定性 |
| 编排方式 | 固定模板 + 有界 ReAct | 同时保留自然语言适应性和确定性 |
| 框架 | 保留 LangGraph | 当前代码和测试已建立，无迁移收益 |
| 工具调用 | 结构化 Tool Calling | 比代码执行更安全、可验证 |
| 默认教学材料包 | 教案 + 练习题 + 思维导图 | 覆盖备课核心且避免默认高成本任务 |
| 高成本任务 | 显式请求并确认 | AI 课堂耗时长，不能因模糊意图自动启动 |
| 自检 | 规则优先，LLM 补充 | 降低随机性和循环重做 |
| 学生端 | 共享内核、分离角色策略 | 防止未来复制和行为漂移 |

## 15. 完成定义

只有同时满足以下条件，Agent 优化才可签收：

1. 本 SPEC 的契约、模板、工具护栏、幂等和自检全部落地；
2. 教师端语气通过规则、LLM Judge 和人工抽检；
3. 固定评测集在至少两个可用模型通道上达到指标；
4. 所有真实 E2E 用例验证实际工具、Job 终态、材料落库和内容证据；
5. 故障注入覆盖 RAG 空结果、Web 失败、模型 fallback、参数错误、超时、重启和部分任务失败；
6. 同一关键用例至少重复五次，稳定性指标达标；
7. PPT 延期与学生端未实施不计为本轮失败，但不得被误报为已支持；
8. 验收文档填写真实结果、任务/材料证据、耗时和未通过项，不允许只写“工具已调用”。
