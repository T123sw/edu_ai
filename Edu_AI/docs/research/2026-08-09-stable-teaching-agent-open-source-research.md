# 简单稳定教学 Agent 开源方案调研

> 日期：2026-08-09
> 目标：为教师端 Agent 能力优化提供设计依据，不在本阶段实施代码
> 关联基线：`docs/acceptance/2026-08-09-agent-capability-status.md`

## 1. 调研结论

本项目不需要追求通用自治 Agent，也不需要多 Agent 团队。教师端的主要任务是把一个短指令稳定地转换成可验证的工具链，例如：

```text
“帮我准备快速排序的教学材料”
→ 明确任务和默认材料包
→ 获取课程资料、网络资料和必要图片
→ 调用一个或多个资源生成工具
→ 检查工具顺序、任务状态、材料落库和证据使用
→ 向教师汇报结果
```

最适合本项目的架构不是“完全自由的 ReAct”，而是：

```text
确定性工作流（控制阶段、顺序、权限和终止）
    └── 有界 ReAct（只在当前阶段内选择工具或处理一次可恢复失败）
```

换句话说，工作流负责可靠性，模型负责理解自然语言和局部判断。现有 LangGraph 架构可以继续使用，无需迁移到另一套框架。

## 2. 当前系统与调研问题的对应关系

当前实现已经包含 Planner、Executor、Tools、Reflect、状态图和资源后台任务，且已真实验证 RAG、Web 和八类非 PPT 资源工具。现阶段主要缺口是：

1. Planner 仍可生成较自由的步骤和 `internal_action`，稳定性依赖后置修正函数。
2. “教学材料”这种组合意图缺少明确的默认材料包和统一计划模板。
3. Reflect 同时承担规则检查和模型评价，缺少统一的任务成功契约。
4. 资源生成工具虽然可调用，但还没有统一的幂等、重复提交防护和跨重启恢复契约。
5. 现有系统提示词偏通用助手，没有把教师端“帮教师完成备课”与学生端“引导学习”分成独立策略。
6. 能力验证以单次通过为主，缺少同一用例多次运行的稳定率、错误恢复率和角色语气评价。

## 3. 开源项目与设计思想

### 3.1 LangGraph：确定性工作流与 Agent 混合

LangGraph 官方将 workflow 定义为预先确定的代码路径，将 agent 定义为动态决定过程和工具使用的系统；它特别适合需要持久化、流式输出、人类确认和精细控制的状态型任务。

本项目吸收：

- 继续使用显式状态图和可观察节点；
- 将备课任务编译为少量固定工作流模板；
- 使用持久化 checkpoint 支持确认、恢复和长任务；
- 只在局部节点保留模型动态决策；
- 将 evaluator-optimizer 限制为有明确成功标准、最多一次修复的闭环。

不吸收：

- 不让模型任意创建长计划或动态图；
- 不为简单任务引入 supervisor、多 Agent 或深层计划树。

资料：

- [LangGraph 概览](https://langchain-ai.github.io/langgraph/index.html)
- [LangGraph workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph interrupts](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/breakpoints/)

### 3.2 ReAct：思考与行动交替，但必须限定边界

ReAct 的核心思想是让模型在推理、执行工具和观察结果之间交替，从外部环境获取信息并更新行动。它适合处理检索结果不足、工具失败或需要根据观察调整下一步的场景。

本项目吸收：

- 在“获取信息”阶段允许模型根据 RAG 结果决定是否需要 Web 补充；
- 在图片未命中时允许更换一次关键词；
- 在工具返回可恢复错误时允许一次局部重试或一次重规划；
- 每次行动后把结构化 Observation 写入状态，而不是只把长文本塞回上下文。

本项目限制：

- ReAct 不能改变强制阶段顺序；
- 不能绕过用户已选择的 RAG/Web/图片指令；
- 不能重复提交已经成功创建的资源任务；
- 单个阶段最多两次工具尝试，整次会话最多一次重规划；
- 不向用户展示内部思维链，只展示简洁计划、工具状态和结果依据。

资料：

- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [ReAct 项目页](https://react-lm.github.io/)

### 3.3 OpenAI Agents SDK：少量原语、工具护栏和完整追踪

OpenAI Agents SDK 使用 Agent、Tool、Guardrail、Session 和 Trace 等少量原语。其工具调用前后护栏、强制工具选择、运行级追踪对本项目很有参考价值。

本项目吸收：

- 每个工具设置输入护栏、输出护栏和允许调用阶段；
- 当前阶段必须调用某工具时，不使用完全自由的 `auto`；
- 记录模型轮次、工具调用、工具结果、护栏、自检和后台任务的完整 trace；
- 对敏感内容进行脱敏，不在日志中记录令牌和完整私有文档正文。

不要求引入 SDK 本身；这些能力可在现有 LangGraph 和工具执行器中实现。

资料：

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [工具护栏](https://openai.github.io/openai-agents-python/guardrails/)
- [Tracing](https://openai.github.io/openai-agents-python/tracing/)

### 3.4 PydanticAI：类型化契约、有限重试、预算和评测数据集

PydanticAI 强调依赖类型、结构化输出、参数验证、可配置重试和使用量限制；Pydantic Evals 使用 Dataset、Case、Experiment、Evaluator 管理概率性系统的重复评测。

本项目吸收：

- 将用户意图、计划、工具输入、Observation、自检结果定义为严格模型；
- 结构校验失败只允许有限重试，不让模型无限修 JSON；
- 为模型轮次、工具次数、重规划次数和总耗时设置预算；
- 建立可版本化的 Agent Eval Dataset；
- 规则类指标优先使用代码判定，语气与内容质量才使用 LLM Judge 或人工抽检。

资料：

- [PydanticAI Agents](https://pydantic.dev/docs/ai/core-concepts/agent/)
- [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/)
- [Durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)

### 3.5 Haystack Agent：状态模式、退出条件和最大步数

Haystack 的 Agent 以循环方式调用工具，并通过 `state_schema`、`exit_conditions` 和 `max_agent_steps` 明确运行状态与结束条件。

本项目吸收：

- 为每类计划定义成功、等待确认、已提交、失败和降级退出条件；
- 达到资源生成工具后，不再让模型继续调用其他生成工具，除非计划明确包含材料包；
- 达到步数、时间或失败预算后必须结束并给出可操作状态，不能静默循环。

资料：

- [Haystack Agent](https://docs.haystack.deepset.ai/docs/agent)

### 3.6 Semantic Kernel：只向模型暴露当前相关工具

Semantic Kernel 支持只向模型提供指定函数，也支持在函数调用前后检查、替换结果、重试和提前终止。其“上下文函数选择”思想说明，工具越多，越应该减少每轮暴露给模型的工具面。

本项目吸收：

- `retrieve` 阶段只暴露 RAG、Web、图片工具；
- `generate` 阶段只暴露计划中指定的资源工具；
- `verify` 阶段不暴露生成工具；
- 工具选择由计划编译器生成白名单，模型不能自行扩大权限。

资料：

- [Semantic Kernel function calling](https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/function-calling/)
- [Semantic Kernel filters](https://learn.microsoft.com/en-gb/semantic-kernel/concepts/enterprise-readiness/filters)

### 3.7 AutoGen：终止条件值得借鉴，多 Agent 不适合当前范围

AutoGen 官方明确建议简单任务先使用单 Agent，并通过最大轮次、超时、工具调用、外部停止等终止条件控制运行；只有单 Agent 不足时才升级到团队。

本项目吸收其终止条件设计，但不采用 RoundRobin、Selector、Swarm 或 critic team。为一个短备课任务引入多个相互对话的 Agent，会增加模型调用、状态同步和非确定性，不符合当前目标。

资料：

- [AutoGen Teams](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/teams.html)
- [AutoGen Termination](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/tutorial/termination.html)

### 3.8 smolagents：本项目应选择结构化 ToolCalling，而非 CodeAgent

smolagents 对两种方式的区分很适合本项目：CodeAgent 表达力强但更难预测且需要安全沙箱；ToolCallingAgent 使用结构化 JSON，更可靠、更安全，适合工具固定的调度器。

本项目的资源工具都是预定义业务能力，因此继续使用结构化工具调用，不增加代码执行能力。

资料：

- [smolagents guided tour](https://github.com/huggingface/smolagents/blob/main/docs/source/en/guided_tour.md)

### 3.9 Dify：工作流可以作为工具复用

Dify 同时提供 Workflow、RAG、Agent 和运行日志，并支持把工作流发布为 Agent 可调用工具。这与本项目“把资源生成封装成工具”的产品方向一致。

本项目吸收：

- 资源生成内部继续保持独立工作流；
- Agent 只调用稳定、版本化的资源入口，不进入每个生成器内部自由编排；
- 资源工作流与 Agent 工具协议分层，双方可独立测试和升级。

不迁移到 Dify，也不引入其运行时。

资料：

- [Dify GitHub](https://github.com/langgenius/dify)

## 4. 最终架构建议

### 4.1 采用

1. 单 Agent、单状态图。
2. 意图识别后编译固定计划模板。
3. 外层阶段固定为：理解任务 → 获取信息 → 准备/确认 → 生成 → 自检 → 汇报。
4. 内层只在检索、图片和失败恢复时使用有界 ReAct。
5. 每一阶段使用工具白名单和结构化成功条件。
6. 资源生成任务使用幂等键和持久任务账本。
7. 使用版本化评测集做多次重复实验，而不是只看单次通过。

### 4.2 不采用

1. 多 Agent 团队与 Agent 间讨论。
2. 让模型动态发明工具、节点或长计划。
3. CodeAgent 或任意代码执行。
4. 无限反思、无限重试和自动扩张任务范围。
5. 为每个角色复制一套编排代码；教师与学生只在 PersonaPolicy 和 InteractionPolicy 上分离。
6. 当前阶段更换 LangGraph 或重写资源生成器。

## 5. 对本项目的核心启示

Agent 能力不应以“看起来会思考”衡量，而应以以下事实衡量：

- 是否识别了正确的教师任务；
- 是否调用了必需工具且没有调用禁止工具；
- 是否严格遵守 RAG、Web、图片、确认和生成顺序；
- 是否只提交一次不可逆任务；
- 是否在失败、超时和重启后得到明确终态；
- 是否生成了真实可读取的教学材料；
- 是否以减轻教师备课负担的语气沟通；
- 同一输入重复运行时是否仍然稳定。

这些结论构成后续 SPEC、执行计划与验收方案的依据。
