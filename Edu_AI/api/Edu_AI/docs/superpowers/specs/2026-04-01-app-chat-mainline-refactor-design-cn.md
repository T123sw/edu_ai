# app/chat 主链路重构设计文档

**状态：** 已确认，可进入实施规划阶段

**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`

**目标：** 将 `app/chat` 重构为一套以工作流优先为核心、以轻量编排器为入口、显式区分快路径与慢路径、按需检索、仅在复杂任务中使用 agent 能力的主链路架构。

## 1. 背景

当前 `app/chat` 已逐渐演变成一个由超大 `service.py`、多层 agent 图、历史兼容状态和多种隐式规则拼接而成的系统，主要问题包括：

- 在真正回答用户前，存在过多模型调用，导致首响应慢。
- 路由、对话、报告生成、检索、工具授权、状态持久化等职责混杂。
- 报告链路同时存在 `report_runtime` 和 `universal_report_engine` 两套运行时，行为重叠。
- 图运行态状态与持久化状态之间出现字段漂移和契约分叉。
- 未来若继续接入 memory、缓存、更多产品动作，现有结构会越来越难维护。

本次重构不是局部修补，而是一次主链路层面的结构收敛。目标架构必须遵循以下原则：

- 普通对话与轻量改写走快路径。
- 结构化生成任务走 workflow-first。
- agent 只作为复杂、不确定或失败恢复场景下的兜底能力。
- `RAG` 默认关闭。
- `web` 默认关闭。
- `RAG/web` 只能由前端显式开关控制，并由后端继续做策略校验。
- 未来 memory 必须能作为基础设施自然接入，而不是挂在主 agent 上。

## 2. 硬性约束

本次重构必须同时满足以下条件：

- 保留 `app/chat` 当前已有的用户能力，不允许功能丢失。
- 可以做较大的 API 契约清理，但最终功能要保持等价承接。
- 主链路不再依赖“全局路由 agent”作为默认入口。
- 默认 `rag = off`。
- 默认 `web = off`。
- `rag` 与 `web` 的可用性由前端显式输入控制，不能默认由模型自行推断开启。
- 预留 memory 接入点，但本轮不落地完整 memory。
- 报告、教案、研究等生成能力继续保留，但移动到明确的工作流路径下。
- 需要考虑部署现实：当前远程服务器无法访问外网，因此后续部署方案不能依赖服务器在线拉取外部依赖或远程资源。

## 3. 总体设计摘要

新的 `app/chat` 主链路分为三层。

### 3.1 产品动作层

这一层面向用户能力，而不是面向模型意图标签。系统对外暴露的应是“用户可理解、可命名、可复用”的产品动作。

首批动作建议包括：

- `chat.reply`：普通对话回复
- `chat.rewrite`：改写、润色、纠错
- `generate.report`：生成报告
- `generate.lesson_plan`：生成教案
- `generate.quiz`：生成练习或试题
- `generate.flashcard`：生成记忆卡片
- `generate.ppt_outline`：生成课件提纲
- `research.lookup`：研究或检索型任务

说明：

- “继续未完成工作流”必须支持，但更适合作为编排层内部语义，而不是一级对外产品动作。
- 对外仍优先表现为 `generate.report`、`generate.lesson_plan`、`research.lookup` 等显式动作。
- orchestrator 内部负责判断这是“新建动作”还是“续接已有 workflow”。

这将替代当前主链路里混杂使用的：

- `intent_category`
- `response_type`
- `resource_type`
- dialogue skill 路由
- tool intent 路由

新的系统不再让这些概念在入口处相互覆盖和竞争。

### 3.1.1 动作与对象绑定

产品动作层不能只定义动作名称，还必须明确动作作用于哪个对象，否则后续仍会回退到“靠消息文本猜作用对象”的老路。

建议主链路显式建模以下对象：

- `Conversation`：当前会话本体
- `ActiveTask`：当前活跃任务
- `WorkflowState`：当前工作流状态
- `Artifact`：当前生成产物
- `SourceRef`：当前使用的数据来源或资源引用

典型绑定关系例如：

- `chat.rewrite` 作用于 `ActiveArtifact` 或最近一条可改写输出
- `generate.report` 作用于当前 `ConversationSnapshot + SourceRef`
- `research.lookup` 作用于当前查询目标，并输出消息或结构化资源结果

### 3.2 工作流编排层

这是新的主入口层，也是后端新的控制核心。

主要职责：

- 读取会话状态
- 读取前端请求参数与能力开关
- 判断当前请求应走快路径还是工作流路径
- 判断是否续接未完成工作流
- 构建执行上下文
- 派发到对应运行时
- 汇总结果并生成统一响应

这一层应当由显式 Python 编排实现，而不是再用主 agent 图承担入口调度。

同时必须满足一个额外原则：

- 最终只有 orchestrator 可以决定主链路走哪条路径。

任何 workflow、runtime、legacy compat 层都不应再执行第二套全局路由。

### 3.3 专用工作流层

这一层放复杂能力的稳定执行流程。

典型场景包括：

- 报告生成工作流
- 教案生成工作流
- research 工作流
- 未来 memory 写回工作流

这些工作流内部可以继续使用 LangGraph 或 agent，但它们不再是每条用户消息的默认入口。

另外，报告工作流必须在设计上尽早收敛到**单一事实入口**：

- 最终只保留 `workflows/report/runtime.py` 作为报告工作流唯一入口。
- `universal_report_engine` 在迁移期可以被包裹、吸收或拆分，但不能长期与新 runtime 并列为双入口。
- Phase 3 结束后，报告链路不允许继续存在“新壳套旧壳再套旧图”的长期结构。

## 4. 主请求生命周期

新的 `/api/chat` 请求处理顺序建议固定为：

1. 规范化请求
2. 读取会话状态
3. 读取 memory 预留接口
4. 检查是否存在待续接工作流
5. 检查显式动作提示、前端开关与用户输入命令
6. 决定执行路径
   - 快路径
   - 工作流路径
7. 构建执行上下文
8. 执行对应运行时
9. 统一格式化响应契约
10. 持久化会话状态与产物
11. 记录 trace、审计信息和评估元数据

这里的“检查待续接工作流”不是无条件劫持当前请求，而是必须经过打断规则判断。

## 5. 路由规则

### 5.1 快路径

快路径适用于：

- 普通聊天
- 顺着上下文继续解释
- 闲聊
- 简短改写、润色、纠错
- 不需要澄清即可直接回答的问题

快路径特征：

- 以单次主模型调用为主
- 默认不启用 RAG
- 默认不启用 web
- 默认不进入复杂工作流图
- 默认不额外调用 planner、intent classifier 或 need-type classifier

### 5.2 工作流路径

工作流路径适用于：

- 报告生成
- 教案生成
- 试题、练习、课件提纲等结构化产物生成
- 基于上文内容进行转产物
- research 类任务
- 任意处于进行中的结构化工作流续接

工作流路径特征：

- 结构化输入装配
- 检索按需启用
- 明确阶段流转
- schema-first 输出
- 可恢复、可续接、可持久化

### 5.3 路由输入来源

路由决策应按以下优先级顺序进行：

1. 已持久化的工作流状态
2. 前端显式动作与能力开关
3. 强规则命令识别
4. 轻量模型路由作为兜底

这意味着系统不会再对每条请求都先做一轮独立的 LLM 意图分类。

### 5.4 工作流打断与切换规则

续接工作流优先级虽然最高，但必须允许用户显式打断、取消、切换或基于当前上下文分叉。

建议定义以下内部调度语义：

- `interrupt_current_workflow`
- `cancel_current_workflow`
- `switch_to_new_action`
- `fork_from_current_context`

典型场景：

- “算了，先帮我出一份教案”
- “别继续这个报告了”
- “重新开始”
- “顺便查一下这个知识点”

编排层必须优先识别这类指令，避免“待续接工作流”劫持新任务。

因此，续接逻辑应为：

1. 存在工作流状态
2. 当前请求未命中打断规则
3. 当前请求未携带更高优先级显式动作
4. 才进入续接路径

## 6. RAG 与 Web 策略

RAG 和 web 都不再被视为主链路默认能力，而是由前端显式开启、后端策略限制、运行时按需暴露的能力。

### 6.1 请求字段建议

新的请求契约建议显式包含：

- `allow_rag: bool`
- `allow_web: bool`
- `selected_doc_ids: list[str]`
- `action_hint: str | null`

### 6.2 行为约束

- 当 `allow_rag = false` 时，运行时不得暴露任何 RAG 工具。
- 当 `allow_web = false` 时，运行时不得暴露任何 web 工具。
- 当 `allow_rag = true` 时，也必须是按需检索，而不是无条件检索。
- 当 `allow_web = true` 时，也只能在 workflow 或明确工具步骤里使用，而不是任由主链路默认推断触发。

### 6.3 设计意义

这样可以去掉当前“由模型推断是否需要工具，再转成授权追问”的复杂路径。前端负责表达用户允许使用哪些能力，后端负责最终策略控制，运行时只在有权限时暴露对应能力。

## 7. Memory 设计预留

本轮不直接落地完整 memory，但主架构必须为未来 memory 接入预留清晰边界。

### 7.1 Memory 类型

- 用户画像记忆
- 会话摘要记忆
- 长期教学资产记忆

### 7.2 Memory 接口

编排层依赖接口，不直接耦合具体存储。

建议预留：

- `MemoryReader`
- `MemoryWriter`
- `ConversationSummarizer`

同时，主链路还应显式建模当前活动对象：

- `active_task`
- `active_artifact`

这是解决“再正式一点”“继续”“换个说法”“加上案例”这类高频追改指令的关键。

### 7.3 读写时机

- 在路由前读取
- 在最终响应或产物完成后写回
- 重写、总结、抽取等重任务后续可异步化

## 8. 目标目录结构

`app/chat` 应按职责重组，而不是继续按历史文件演化路径堆叠。

### 8.1 建议结构

```text
app/chat/
  api/
    routes.py
    schemas.py

  application/
    chat_app_service.py
    request_normalizer.py
    response_builder.py

  domain/
    actions.py
    conversation_mode.py
    contracts.py
    policy.py
    route_decision.py
    workflow_state.py
    artifact_ref.py
    conversation_snapshot.py
    capability_policy.py

  orchestrator/
    main_orchestrator.py
    route_rules.py
    route_fallback_model.py
    context_builder.py
    workflow_resumer.py
    workflow_interrupts.py

  memory/
    ports.py
    adapters/

  retrieval/
    retrieval_policy.py
    retrieval_runtime.py
    web_runtime.py
    source_evaluator.py

  workflows/
    report/
      runtime.py
      state.py
      contracts.py
      assembler.py
    lesson_plan/
      runtime.py
      state.py
    research/
      runtime.py
      state.py

  runtime/
    fast_chat_runtime.py
    model_registry.py
    tool_registry.py

  persistence/
    conversation_store_adapter.py
    artifact_store_adapter.py

  observability/
    trace.py
    audit.py
    metrics.py

  legacy/
    compat_service.py
```

## 9. 保留 / 删除 / 重写清单

### 9.1 建议保留并复用

以下模块包含可复用的领域逻辑或生成价值：

- `app/chat/report_domain.py`
- `app/chat/agents/report_utils.py`
- `app/chat/agents/report_generation.py`
- `app/chat/tools/search_tools.py`
- `app/chat/tools/agent_tools.py`
- `app/chat/skill_manager.py`
- 现有 conversation storage 集成
- 现有 user profile storage 集成

这些能力应被迁移到更清晰的 runtime 或 port 背后，而不是继续由主链路直接调用。

### 9.2 建议暂时保留作为过渡资产

- `app/chat/agents/universal_report_engine.py`
- `app/chat/service.py` 中与当前响应契约有关的部分逻辑
- `routes.py` 中现有 SSE 流式输出行为

这些都只作为迁移桥接层，不作为最终架构保留。

`compat_service.py` 的职责必须被严格限制为：

- 旧请求到新请求的桥接
- 新响应到旧响应的桥接

不得新增业务策略，不得新增第二套路由，不得承载长期业务逻辑，否则它会演化成第二个 `service.py`。

### 9.3 迁移完成后建议删除

以下模块作为主链路结构价值较低，应在迁移完成后移除：

- `app/chat/agents/supervisor_agent.py`
- `app/chat/agents/router_agent.py`
- `app/chat/agents/chat_agent.py`
- `app/chat/agents/research_agent.py`
- `app/chat/agents/report_agent.py` 中旧报告图装配壳层
- 主链路直接依赖 `IntentRouter`
- 主链路直接依赖 `ResponsePlanner`
- 主链路直接依赖 `_detect_need_type`
- 当前 chat 循环中的默认工具授权追问路径

### 9.4 建议整体重写

以下文件不适合继续打补丁演化，应以新边界重写：

- `app/chat/service.py`
- `app/chat/graph_state.py`
- `app/chat/intent_router.py`
- `app/chat/resource_type_router.py`
- `app/chat/response_planner.py`
- `app/chat/reflection_engine.py` 的主链路耦合方式

## 10. 关键领域对象

为了避免本轮继续在多个 `dict` 之间漂移，主链路需要先定义统一领域对象草案。

### 10.1 RouteDecision

至少包含：

- `path = fast | workflow`
- `action`
- `workflow_name`
- `reason`
- `allowed_capabilities`
- `resume_target`

### 10.2 CapabilityPolicy

不能只用两个布尔值替代完整能力策略。

建议至少包含：

- 是否允许 rag
- 是否允许 web
- 是否允许 tool
- 允许哪些来源
- 最大工具步数
- 是否必须前端显式选择资料

### 10.3 ConversationSnapshot

编排层不要直接连多个 store 再拼散乱状态，而应统一读取快照对象。

建议包含：

- 最近消息
- 当前会话摘要
- 当前活跃任务
- 当前活跃产物
- 用户画像摘要
- 当前能力策略

### 10.4 WorkflowState

所有 workflow 应共享最小公共契约，而不是各自随意发明字段。

至少统一：

- `workflow_id`
- `workflow_type`
- `status`
- `stage`
- `required_slots`
- `filled_slots`
- `artifacts`
- `resume_token`

### 10.5 ArtifactRef

这是后续实现“根据上面内容生成 XXX”的核心对象。

如果没有产物引用，系统就会长期依赖消息历史猜测对象，导致快路径和工作流都不稳定。

## 11. API 契约方向

新的 API 契约应从“隐式 meta 大包”转向“显式字段语义”。

### 11.1 当前问题

- 顶层和 meta 中存在大量重叠字段
- 响应含义依赖内部 graph state 才能解释
- 工具授权、路由原因等内部逻辑渗透到用户侧流程
- 报告产物在多个分支中被特殊处理

### 11.2 目标响应结构

建议逐步收敛到以下顶层概念：

- `message`
- `conversation`
- `action`
- `artifacts`
- `workflow`
- `sources`
- `trace`

响应应该清晰表达：

- 执行了什么动作
- 当前工作流是否完成或等待继续
- 生成了什么产物
- 使用了哪些来源

而不是把 graph 节点细节当作业务契约的一部分暴露出来。

### 11.3 API 版本化

由于本次契约变化较大，建议显式做版本化，而不是只做字段替换。

建议迁移期并存：

- `v1`：旧契约兼容层
- `v2`：新主链路契约

### 11.4 SSE 事件协议统一

虽然迁移期会保留现有 SSE 表现，但背后运行时会发生变化，因此需要尽早统一事件协议。

建议标准化为：

- `message.delta`
- `workflow.status`
- `artifact.created`
- `artifact.updated`
- `source.used`
- `trace.meta`
- `error`
- `done`

## 12. 迁移顺序

### Phase 1：先稳定边界

- 引入新请求契约和新响应契约
- 建立 orchestrator 目录与主编排器
- 引入显式动作枚举和策略枚举
- 为请求增加 `allow_rag` 与 `allow_web`
- 旧 `service.py` 先作为兼容适配层存在

### Phase 2：先抽离快路径

- 建立 `fast_chat_runtime`
- 普通聊天直接走快路径
- 去掉 plain chat 对 planner 和默认意图分类器的依赖
- 保留现有 SSE 表现

### Phase 3：再抽离工作流路径

- 把报告入口迁到 `workflows/report/runtime.py`
- 用新 runtime 包裹或逐步迁移 `universal_report_engine`
- 统一工作流续接行为
- 明确报告工作流唯一入口 sunset plan

### Phase 4：隔离检索与 web 策略

- 把 retrieval 与 web 拆到独立、策略感知的 runtime
- 移除当前主聊天循环中的隐式工具授权逻辑
- 只接受“请求开关 + 后端策略”这条能力控制链

### Phase 5：统一持久化与 memory 接口

- 规范会话中的 workflow state 结构
- 增加 memory 读写接口
- 增加会话摘要钩子

### Phase 6：移除旧图主干

- 删除旧的 supervisor/router/chat/research graph 主入口
- 从对外契约中移除旧 route state 字段
- 仅保留确实有价值的 bounded workflow runtime

## 13. 测试策略

本次重构必须由三层测试共同保护。

### 13.1 契约测试

- 请求规范化
- 响应 schema 校验
- workflow 续接契约
- 产物输出契约

### 13.2 路由测试

- 普通聊天走快路径
- 显式报告请求走 workflow
- 续接工作流时跳过重新全量路由
- `allow_rag = false` 时禁用检索
- `allow_web = false` 时禁用 web
- 存在 workflow 时，显式打断指令可正确切换
- 存在 active artifact 时，轻量追改请求无需重新全局意图猜测

### 13.3 工作流测试

- 报告生成生命周期
- 大纲确认生命周期
- 缺槽位追问生命周期
- research 在 web 开启与关闭下的行为

## 14. 本轮不做的事

以下内容明确延期，不在本次 `app/chat` 主链路重构中一次做完：

- 完整 memory 实现
- 训练型 router 上线
- retrieval evaluator 模型优化
- `app/chat` 之外的推理栈迁移
- `report_service` 或 `pipeline` 包的重构
- 远程服务器无法访问外网条件下的完整离线部署打包方案

## 15. 最终决策

本次确认的重构方向是：

- 生成能力走 workflow-first
- 主链路入口使用轻量 orchestrator
- 普通聊天默认走快路径
- `RAG` 默认关闭
- `web` 默认关闭
- 前端按钮显式控制能力开放
- agent 仅作为复杂工作流或异常恢复中的辅助能力

这次重构是一次结构性重构，不是一次代码整理。
