# app/chat v2 前后端对齐重建设计

**状态：** 已确认，可进入实施计划阶段  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`

## 1. 目标

本轮不再继续深修旧 `POST /api/chat` 的兼容链路，而是直接重建一套面向前端的新 `v2` 接口。

重建目标如下：

- 为前端提供两个清晰入口：
  - `reply`，用于默认对话
  - `report`，用于报告生成按钮
- 默认走对话链路
- 对话链路中如果识别到报告意图，则切入报告工作流
- `RAG` 和 `web` 不再作为一级接口，而是作为受控工具能力存在
- 报告按钮对应的“配置式生成报告”先预留输入位置，本轮不完成完整实现
- 旧 `/api/chat`、旧 `service.py`、旧 graph/router/planner/agent 壳层不再作为主开发目标

## 2. 核心判断

当前继续围绕旧接口做兼容式重构，边际收益已经很低。主要时间会消耗在：

- 兼容旧 `answer + intent_category + meta`
- 兼容旧 SSE 事件名
- 兼容旧 `service.py` 里混杂的主入口职责
- 兼容旧 graph/planner/router 壳层

这些工作不会直接改善“对话响应速度”和“报告生成体验”。

因此，本轮采用的新原则是：

- 保留已经拆出的可复用运行时和领域能力
- 停止继续深挖旧主接口
- 直接新建面向前端的 `v2` API

## 3. 产品形态

### 3.1 前端入口

前端统一收敛为两个产品入口：

- 默认对话入口
- 报告生成按钮入口

两者是同一能力体系下的两种进入方式：

- 对话入口适合自然语言连续交互
- 报告入口适合用户显式发起报告生成

后续报告按钮还会支持“配置式生成报告”，但本轮只预留 `report_config` 位置，不实现完整配置工作流。

### 3.2 一级接口与二级能力

一级接口只保留：

- `reply`
- `report`

二级能力只作为运行时工具存在：

- `rag_search_tool`
- `web_search_tool`

也就是说，`research/web` 不是一级 HTTP 主接口，而是：

- 由前端按钮授权
- 由后端 capability policy 控制
- 由运行时在需要时调用

## 4. 接口设计

### 4.0 最小领域对象契约

为避免实现阶段再次退回到松散 `dict`，本阶段先固定以下最小对象契约。

#### `ConversationSnapshot`

最小字段：

- `conversation_id: str`
- `recent_messages: list[dict]`
- `workflow_state: WorkflowState | null`
- `active_task: str | null`
- `active_artifact: ArtifactRef | null`
- `capability: CapabilityPolicy`

#### `WorkflowState`

最小字段：

- `workflow_id: str`
- `workflow_type: str`
- `status: str`
- `stage: str`
- `artifacts: list[dict]`

#### `ArtifactRef`

最小字段：

- `artifact_id: str`
- `artifact_type: str`
- `title: str | null`

#### `CapabilityPolicy`

最小字段：

- `allow_rag: bool`
- `allow_web: bool`
- `selected_doc_ids: list[str]`

#### `ChatResultV2`

最小字段：

- `message: dict`
- `conversation: dict`
- `action: dict`
- `artifacts: list[dict]`
- `workflow: dict | null`
- `sources: list[dict]`
- `trace: dict`

### 4.1 `POST /api/chat/v2/reply`

用途：

- 普通对话
- 基于上下文追问
- 轻量改写
- 在对话中识别到“生成报告”意图时切入报告工作流

建议请求体：

```json
{
  "question": "根据以上内容帮我整理成报告",
  "conversation_id": "conv_xxx",
  "model_id": "optional",
  "course_id": "optional",
  "artifact_id": "optional",
  "allow_rag": false,
  "allow_web": false,
  "selected_doc_ids": [],
  "action_hint": null
}
```

说明：

- `action_hint` 在 `reply` 中通常为空
- 当用户在对话中自然表达“生成报告”时，由后端识别并切换到 report workflow
- `allow_rag` 和 `allow_web` 默认都为 `false`

建议响应体：

```json
{
  "message": {
    "role": "assistant",
    "content": "..."
  },
  "conversation": {
    "conversation_id": "conv_xxx"
  },
  "action": {
    "name": "chat.reply"
  },
  "workflow": null,
  "artifacts": [],
  "sources": [],
  "trace": {
    "path": "fast"
  }
}
```

如果在 `reply` 中切到了报告工作流，则：

- `action.name = "generate.report"`
- `workflow.type = "report"`
- `trace.path = "workflow"`

#### `reply` 请求字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `question` | `str` | 是 | 用户输入 |
| `conversation_id` | `str \| null` | 否 | 会话 ID，不传则后端创建 |
| `model_id` | `str \| null` | 否 | 指定模型 |
| `course_id` | `str \| null` | 否 | 课程上下文 |
| `artifact_id` | `str \| null` | 否 | 当前活跃产物 ID |
| `allow_rag` | `bool` | 否 | 默认 `false` |
| `allow_web` | `bool` | 否 | 默认 `false` |
| `selected_doc_ids` | `list[str]` | 否 | RAG 白名单文档 |
| `action_hint` | `str \| null` | 否 | 默认 `null`，保留显式动作提示 |

#### `reply` 响应字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `message.role` | `str` | 是 | 固定为 `assistant` |
| `message.content` | `str` | 是 | 回复文本 |
| `conversation.conversation_id` | `str` | 是 | 会话 ID |
| `action.name` | `str` | 是 | `chat.reply`、`chat.rewrite` 或 `generate.report` |
| `workflow` | `dict \| null` | 否 | workflow 信息 |
| `artifacts` | `list[dict]` | 是 | 默认空数组 |
| `sources` | `list[dict]` | 是 | 默认空数组 |
| `trace.path` | `str` | 是 | `fast` 或 `workflow` |

### 4.2 `POST /api/chat/v2/report`

用途：

- 前端点击报告按钮时显式进入报告工作流
- 不再通过旧 chat 主链路兜转

建议请求体：

```json
{
  "question": "帮我生成一份课堂观察报告",
  "conversation_id": "conv_xxx",
  "model_id": "optional",
  "course_id": "optional",
  "allow_rag": false,
  "allow_web": false,
  "selected_doc_ids": [],
  "report_config": null
}
```

说明：

- `report_config` 本轮先预留
- 第一阶段先支持“基于当前输入 + 会话上下文”生成报告
- 第二阶段再补完整的配置式报告生成

#### `report_config` 最小约束

- `report_config` 允许为 `null`
- 若非空，本阶段只允许作为透传字段存在，不驱动最终生成逻辑
- 第一阶段允许的最小字段：
  - `topic: str | null`
  - `audience: str | null`
  - `goal: str | null`
  - `length: str | null`
- 对于第一阶段尚未消费的字段：
  - 不报错
  - 原样写入 `trace.input.report_config`
  - 不承诺影响生成结果

建议响应体与 `reply` 统一，只是 `action` 和 `workflow` 不同：

```json
{
  "message": {
    "role": "assistant",
    "content": "..."
  },
  "conversation": {
    "conversation_id": "conv_xxx"
  },
  "action": {
    "name": "generate.report"
  },
  "workflow": {
    "type": "report",
    "status": "running"
  },
  "artifacts": [],
  "sources": [],
  "trace": {
    "path": "workflow",
    "workflow_name": "report"
  }
}
```

#### `report` 请求字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `question` | `str` | 是 | 报告生成需求 |
| `conversation_id` | `str \| null` | 否 | 会话 ID |
| `model_id` | `str \| null` | 否 | 指定模型 |
| `course_id` | `str \| null` | 否 | 课程上下文 |
| `allow_rag` | `bool` | 否 | 默认 `false` |
| `allow_web` | `bool` | 否 | 默认 `false` |
| `selected_doc_ids` | `list[str]` | 否 | RAG 白名单文档 |
| `report_config` | `dict \| null` | 否 | 第一阶段仅透传保留 |

#### `report` 响应字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `message.role` | `str` | 是 | 固定为 `assistant` |
| `message.content` | `str` | 是 | 当前报告阶段回复 |
| `conversation.conversation_id` | `str` | 是 | 会话 ID |
| `action.name` | `str` | 是 | 固定为 `generate.report` |
| `workflow.type` | `str` | 是 | 固定为 `report` |
| `workflow.status` | `str` | 是 | 见状态枚举 |
| `artifacts` | `list[dict]` | 是 | 轮次产生的产物 |
| `sources` | `list[dict]` | 是 | 本轮使用的来源 |
| `trace.path` | `str` | 是 | 固定为 `workflow` |

### 4.3 `GET /api/chat/v2/stream`

本轮只预留，不作为第一阶段必须完成项。

第一阶段优先级：

- 先把非流式 `reply/report` 跑通
- 确认前端已经能切到新接口
- 再做 `v2 stream`

### 4.4 通用响应约束

#### `workflow.status` 枚举

第一阶段统一为：

- `running`
- `awaiting_confirm`
- `completed`
- `interrupted`
- `failed`

#### `trace.path` 枚举

第一阶段统一为：

- `fast`
- `workflow`

#### `artifacts` 最小字段

每个 artifact 至少包含：

- `artifact_id: str`
- `artifact_type: str`
- `content: Any | null`
- `title: str | null`

#### `sources` 最小字段

每个 source 至少包含：

- `source_id: str | null`
- `title: str | null`
- `kind: str | null`
- `uri: str | null`

### 4.5 错误响应模型

第一阶段统一错误响应结构：

```json
{
  "error": {
    "code": "capability_denied",
    "message": "当前请求未授权使用 web 搜索",
    "retryable": false
  },
  "conversation": {
    "conversation_id": "conv_xxx"
  },
  "trace": {
    "path": "fast"
  }
}
```

第一阶段约定的错误码：

- `invalid_request`
- `capability_denied`
- `context_insufficient`
- `workflow_failed`
- `conversation_not_found`

错误处理原则：

- 参数错误返回 `400`
- 能力未授权返回 `403`
- conversation 不存在但允许重建时，返回 `200` 并创建新会话
- 上下文不足优先返回 `200` 的引导式回复，而不是直接 `4xx`
- workflow 执行异常返回 `500`，错误码为 `workflow_failed`

## 5. 路由规则

### 5.1 `reply` 路由

处理顺序固定为：

1. 读取会话快照
2. 检查是否存在未完成 workflow
3. 检查是否命中 interrupt / switch 规则
4. 检查是否命中“生成报告”意图
5. 否则走 fast chat

### 5.2 `report` 路由

处理顺序固定为：

1. 读取会话快照
2. 直接进入 report workflow runtime
3. 不再经过旧 chat 主入口的 planner/router/graph

### 5.3 报告意图识别

本轮不使用重型前置 LLM classifier。

优先顺序：

1. 前端显式入口
2. 显式 `action_hint=generate.report`
3. 轻量规则命中，如“生成报告”“整理成报告”“根据以上内容生成报告”
4. 其余情况继续普通对话

这意味着：

- “报告按钮”是最高优先级
- 自然语言识别报告意图只作为对话链路中的切换机制
- 不再把“意图提取器”做成每轮必跑的 LLM 前置步骤

### 5.4 reply 与 report 的状态语义

#### 继续

- 当前存在 `workflow_state`
- 当前请求未命中 interrupt / switch
- 当前请求未携带更高优先级显式入口
- 则继续当前 report workflow

#### 中断

出现“算了”“别继续”“重新开始”等中断语义时：

- `workflow.status = interrupted`
- 清空 `active_task`
- 保留最近一次 `active_artifact` 供后续引用

#### 从 reply 切 report

当 `reply` 中命中报告意图时：

- `action.name` 切换为 `generate.report`
- `workflow.type = report`
- `active_task = generate.report`
- 若当轮生成了 outline 或 report，则写回 `active_artifact`

#### 基于已有报告继续修改

当存在 `active_artifact` 且用户输入为“根据刚才那个报告再改一下”“再正式一点”这类追改时：

- 优先视为对当前 artifact 的修改请求
- 不新建独立 report workflow
- 由 report runtime 或后续 rewrite 逻辑消费该 artifact

## 6. 能力控制

### 6.1 原则

- `RAG` 默认关闭
- `web` 默认关闭
- 前端必须显式传入授权
- 后端继续做最终策略校验

### 6.2 行为

- 当 `allow_rag = false` 时，不允许暴露 `rag_search_tool`
- 当 `allow_web = false` 时，不允许暴露 `web_search_tool`
- 即使授权开启，也只在运行时按需调用，不做默认检索

### 6.3 工具层策略

本轮工具层只保留“可直接复用的纯能力工具”，不再让旧 graph tool 包装继续担任新主链路基础。

优先保留：

- `app/chat/tools/agent_tools.py`

不再作为新主链路核心：

- `app/chat/tools/search_tools.py`

原因：

- `agent_tools.py` 更接近普通 Python 工具注册表
- `search_tools.py` 明显更偏旧 graph / LangChain tool 包装

### 6.4 外部检索工具与内部工具的区分

第一阶段明确区分两类工具：

- 外部检索工具：
  - `rag_search_tool`
  - `web_search_tool`
- 内部工具：
  - outline 组装
  - report 内容生成
  - artifact 处理

约束：

- `allow_rag / allow_web` 只控制外部检索工具
- 内部工具不受前端授权开关限制
- 不引入新的总开关 `allow_tools` 来混淆两类能力

## 7. 运行时设计

### 7.1 对话运行时

对话运行时继续复用：

- `app/chat/runtime/fast_chat_runtime.py`

职责：

- 组装系统提示
- 拼接最近历史
- 单次主模型调用
- 输出统一 `v2` 结果

### 7.2 报告运行时

报告运行时继续复用：

- `app/chat/workflows/report/runtime.py`

但要做一个重要改造：

- 不再通过 legacy `ChatService.get_report_engine()` 间接拿 engine
- 改为在 `v2 report service` 中直接构建 `universal_report_engine`

也就是说，本轮目标不是继续“新 runtime 包旧 ChatService”，而是：

- `ReportWorkflowRuntime`
- 直接连 `universal_report_engine`

### 7.3 会话与上下文

继续复用：

- `app/chat/persistence/conversation_store_adapter.py`

用于：

- 读取最近消息
- 读取会话状态
- 写回消息
- 写回 workflow 状态
- 写回 active task / active artifact

### 7.4 持久化写回规则

#### reply 成功后

- 写入用户消息
- 写入助手消息
- 更新 `active_task = chat.reply` 或 `chat.rewrite`
- 如果无产物生成，则不写 `active_artifact`

#### reply 切入 report 后

- 写入用户消息
- 写入当前轮助手消息
- 写入 `workflow_state`
- 写入 `active_task = generate.report`
- 若已有 outline/report 产物，则写入 `active_artifact`

#### report 运行中

- 每轮都写回最新 `workflow_state`
- 当状态进入 `awaiting_confirm` 时保留当前 artifacts
- 当前轮若生成了 outline 或 report 内容，则覆盖更新 `active_artifact`

#### report 完成后

- `workflow.status = completed`
- `active_task` 保持为 `generate.report`，直到用户显式切换
- `active_artifact` 指向最新 report 产物

#### report 中断后

- `workflow.status = interrupted`
- 清空 `active_task`
- 保留 `active_artifact`

## 8. 代码结构目标

建议最终形成以下主路径：

```text
app/chat/
  api/
    routes_v2.py
    schemas_v2.py

  application/
    reply_service_v2.py
    report_service_v2.py
    response_builder_v2.py

  orchestrator/
    main_orchestrator.py
    route_rules.py
    context_builder.py
    workflow_interrupts.py

  runtime/
    fast_chat_runtime.py

  workflows/
    report/
      runtime.py

  tools/
    agent_tools.py

  persistence/
    conversation_store_adapter.py
```

第一阶段允许旧文件继续存在，但不再让它们承担新接口主职责。

### 8.1 共享组件原则

为防止 `reply` 和 `report` 两条链路逐渐漂开，第一阶段必须共享以下组件：

- 同一 `response_builder_v2`
- 同一 `context_builder`
- 同一 `conversation_store_adapter`
- 同一 `ReportWorkflowRuntime`
- 同一 capability policy 解析逻辑

禁止出现：

- `reply` 自己拼一套 report 响应
- `report` 自己维护另一套写回规则
- 两条链路分别维护不同的 artifact 结构

## 9. 保留与放弃

### 9.1 保留

- `app/chat/runtime/fast_chat_runtime.py`
- `app/chat/workflows/report/runtime.py`
- `app/chat/agents/universal_report_engine.py`
- `app/chat/tools/agent_tools.py`
- `app/chat/agents/report_generation.py`
- `app/chat/agents/report_utils.py`
- `app/chat/persistence/conversation_store_adapter.py`
- 已经形成的新 `orchestrator` 和 `domain` 基础结构

### 9.2 冻结

- 旧 `POST /api/chat`
- 旧 `GET /api/chat/stream`
- `legacy/compat_service.py`
- `legacy/legacy_chat_runtime.py`

冻结的意思是：

- 可以保留运行
- 不再继续作为主演进方向

### 9.3 不再深修

- `app/chat/service.py`
- 旧 `intent_router`
- 旧 `response_planner`
- 旧 `graph_state`
- 旧 `supervisor/chat/research/router` agent 壳层

## 10. 第一阶段实现边界

本轮必须完成：

- `POST /api/chat/v2/reply`
- `POST /api/chat/v2/report`
- `reply` 到 `report workflow` 的轻量切换
- `report` 直连 `universal_report_engine`
- `rag/web` 工具按前端授权受控暴露
- 前后端统一使用 `v2` 响应结构

本轮明确不完成：

- 配置式报告生成的完整逻辑
- `lesson_plan / quiz / flashcard / ppt_outline`
- 完整 memory
- 旧接口的彻底删除
- `v2 stream` 的最终定版

## 10.1 前端对接约束

前端第一阶段按如下规则对接：

- 普通发送消息统一调 `POST /api/chat/v2/reply`
- 报告按钮统一调 `POST /api/chat/v2/report`
- 报告按钮调用时不必再通过 `reply` 模拟
- 若后续补配置式报告，则在 `report` 请求中填充 `report_config`

前端展示约束：

- 若响应中 `workflow != null`，前端进入 workflow 展示模式
- 若响应中 `artifacts` 非空，前端应预留右侧面板或附件位展示产物
- 若 `workflow.status = awaiting_confirm`，前端应允许用户继续在当前会话中确认或修改
- 第一阶段不要求前端维护完整 artifact 面板系统，但必须能消费 `workflow` 和 `artifacts`

## 11. 验收标准

满足以下条件才算本轮完成：

- 前端能直接调用 `v2/reply`
- 前端能直接调用 `v2/report`
- 普通对话不再依赖旧 `/api/chat` 兼容链
- 报告按钮不再依赖旧 `/api/chat` 主入口
- 对话中出现“整理成报告”时可进入 report workflow
- `allow_rag=false` 时不会触发 RAG
- `allow_web=false` 时不会触发 web
- `v2` 响应结构稳定统一
- 旧接口仍可暂时保留，但不再是主开发路径

## 12. 下一步

这份 spec 确认后，下一步只做一件事：

- 基于本 spec 写一份 `v2` 接口实施计划

实施计划将重点覆盖：

- 新 `schemas_v2`
- 新 `routes_v2`
- `reply_service_v2`
- `report_service_v2`
- report engine 直连改造
- 工具能力注册与 capability gate
- 面向前端的回归测试
