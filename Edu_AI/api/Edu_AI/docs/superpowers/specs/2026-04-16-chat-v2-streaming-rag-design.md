# Chat V2 主系统流式对话接入设计

日期：2026-04-16

## 目标

将主系统当前的 `chat v2` 对话链路改造成“仿照 `rag/query_stream` 的流式输出模式”，同时保留主系统已经具备的能力：

- 普通对话
- RAG / Web / 图片 / 视频检索
- 状态卡
- 历史消息与会话状态写回
- 报告 / PPT / 教案 / 测验等工作流
- 多模态输入（图片、视频）

目标不是把主系统切换成纯 `rag/query_stream`，而是让主系统具备同类的流式交互体验：

1. 检索先完成
2. 检索结果先推送给前端
3. 正文增量流式输出
4. 最终结果统一落盘并刷新状态

## 非目标

- 不替换现有 `chat v2` 的业务编排
- 不重写 `rag_v2` 的检索逻辑
- 不在本阶段实现工作流内部每个子步骤都逐 token 输出
- 不移除旧 `/api/chat/stream`

## 现状

### 1. `rag/query_stream`

`/api/rag/query_stream` 的核心特点是：

- 手动拆开“检索”和“生成”
- 先做 query rewrite、embedding、allowed_sources 过滤、hybrid search
- 先返回一帧 `metadata`
- 再调用 `_call_llm(..., stream=True)` 输出正文 chunk
- 最后返回 `[DONE]`

这条链路适合纯 RAG 问答，但不适合作为主系统总线，因为它不负责：

- conversation state 写回
- workflow 编排
- artifact 生成
- status card

### 2. `chat v2`

当前 `chat v2` 的 `reply` 路由已经承载主系统功能，但返回是一次性 JSON：

- `message`
- `conversation`
- `action`
- `workflow`
- `artifacts`
- `sources`
- `trace`
- `status_card`

这条链路已经接好了图片、视频、RAG、证据展示和持久化，但不是流式。

### 3. 旧 `/api/chat/stream`

旧链路已有 SSE 框架，但本质上还是“先拿完整结果，再伪装成 stream 输出一段 delta”，无法满足：

- 先推检索 metadata
- 主系统 v2 payload
- 多模态主链路
- 工作流统一事件协议

## 备选方案

### 方案 A：给 `chat v2` 新增独立 `/api/chat/v2/stream`

做法：

- 新增 `POST /api/chat/v2/stream`
- 请求体沿用 `ChatReplyRequestV2`
- 后端在 v2 主逻辑内部显式拆分“检索 -> metadata -> stream answer -> finalize”
- 前端用新 stream API 替换当前 `reply`

优点：

- 与 `chat v2` 数据结构一致
- 最容易保留状态卡、sources、artifacts、history
- 不污染旧链路
- 最接近 `query_stream` 的实现方式

缺点：

- 需要新建一套 v2 SSE/stream 协议
- 前端需要新增 POST stream 消费器

### 方案 B：复用旧 `/api/chat/stream`，底层切到 `chat v2`

优点：

- 前端改动较小

缺点：

- 旧协议是 GET + EventSource，不适合继续承载 `input_images` / `input_videos`
- `chat v2` 结构化结果很难自然映射到旧协议
- 长期会继续保留技术债

### 方案 C：把主系统直接切到 `rag/query_stream`

优点：

- 流式能力现成

缺点：

- 会破坏主系统工作流、状态卡、artifact、会话写回
- 只能覆盖纯 RAG 问答，不适合主系统

## 结论

采用方案 A。

即：新增 `POST /api/chat/v2/stream`，协议与 `query_stream` 的节奏一致，但 payload 和结果模型沿用 `chat v2` 主系统。

## 总体设计

### 一、路由层

新增：

- `POST /api/chat/v2/stream`

输入：

- 沿用 `ChatReplyRequestV2`

输出：

- `text/event-stream`

不使用 `EventSource + GET query params`，而改用 `fetch + ReadableStream`，原因：

- `chat v2` 需要 POST JSON
- 需要承载多模态输入
- 后续扩展 artifact/reference 时更自然

### 二、事件协议

采用统一事件 envelope：

```json
{
  "type": "metadata" | "status" | "delta" | "result" | "done" | "error",
  "payload": { ... }
}
```

SSE 文本格式：

```text
data: {"type":"metadata","payload":{...}}

data: {"type":"delta","payload":{"content":"..."}}

data: {"type":"done","payload":{"conversation_id":"..."}}
```

### 三、事件语义

#### 1. `metadata`

在检索与初始上下文准备完成后立即发送。

内容包括：

- `conversation_id`
- `sources`
- `trace.path`
- `retrieval_metrics`
- 初始 `status_card`
- `workflow` 基础信息（如果已经判定为工作流）

#### 2. `status`

用于工作流阶段更新。

建议字段：

- `stage`
- `node`
- `label`
- `workflow`

普通对话可以不频繁发送。

#### 3. `delta`

模型正文 token / chunk 增量。

建议字段：

- `content`

#### 4. `result`

在最终内容与结构化结果准备好后发送一次。

内容包括：

- `message`
- `conversation`
- `action`
- `workflow`
- `artifacts`
- `sources`
- `trace`
- `status_card`

这相当于当前 `ChatResponseV2` 的流式收尾快照。

#### 5. `done`

表示本轮完成，前端可停止 loading、固化结果。

#### 6. `error`

用于中途失败时通知前端。

## 后端分层设计

### 一、ReplyServiceV2 扩展为双模式

当前：

- `reply(payload) -> dict`

新增：

- `reply_stream(payload) -> Iterable[dict]`

要求：

- 普通 `reply` 和 `reply_stream` 共享请求归一化
- 最终结构化结果共享 `finalize_report_result`、course material 落库、conversation store 写回
- 避免出现“同步结果和流式结果语义不一致”

### 二、FastChatRuntime 新增 stream 版本

新增能力：

- `run_stream(request, snapshot, decision)`

执行顺序：

1. 做 RAG / Web / 图片 / 视频检索
2. 构建 `sources`
3. yield `metadata`
4. 组装 system prompt + history + multimodal user content
5. 调 `model_gateway.stream_chat(...)`
6. 对每个 chunk yield `delta`
7. 汇总完整 answer
8. 返回 final result 给 service 做统一写回

这里与 `query_stream` 保持一致的核心点：

- 先检索，再流式生成
- 检索结果优先于正文发送

### 三、工作流运行时新增 stream facade

工作流不要求内部每个大模型调用都逐 token 暴露，但要求整个工作流对前端表现为流式回复。

建议分两层：

#### 1. 工作流状态流

每个 workflow runtime 在关键阶段 yield `status`：

- `planning`
- `preparing_context`
- `generating`
- `assembling_artifact`
- `completed`

#### 2. 最终回答流

当工作流最终要返回 assistant message 时：

- 如果有文本答复，走 `delta`
- 如果只是“已生成，请在右侧查看”，则也通过 `delta` 按 chunk 输出

artifact 本体不要求 token stream，只要求事件级 stream。

### 四、统一 finalize

无论 fast path 还是 workflow path，都必须在最后统一做：

- `conversation_store.write_v2_result(...)`
- `status_card_builder.build(...)`
- `finalize_report_result(...)`
- artifact 结果整理

也就是说：

- stream 期间可以逐步发事件
- 持久化只在最终结果确定后进行一次

## 前端设计

### 一、传输方式

新增 `sendChatReplyV2Stream(...)`

实现方式：

- `fetch('/api/chat/v2/stream', { method: 'POST', body: JSON.stringify(...) })`
- 读取 `response.body.getReader()`
- 按 SSE 分帧解析

不继续复用旧 `EventSource`。

### 二、ChatPanel 行为

发送后：

1. 先插入用户消息
2. 立即插入空 AI 消息，`status='streaming'`
3. 收到 `metadata`
   - 更新 sources
   - 更新 status card
   - 若有 workflow 基础信息，更新界面
4. 收到 `delta`
   - 追加到当前 AI 消息文本
5. 收到 `status`
   - 更新 `statusText`
6. 收到 `result`
   - 补齐 sources / workflow / artifacts / status card
7. 收到 `done`
   - 结束 loading

### 三、历史一致性

因为最终仍然调用统一持久化，所以：

- 刷新页面后历史消息与非流式回复保持一致
- 图片/视频输入、sources、artifact、status card 都能从历史恢复

## 对普通对话与工作流的差异处理

### 普通对话

- 检索完成后先推 `metadata`
- 正文按 token/chunk 推 `delta`
- 最终推 `result + done`

### 报告 / PPT / 教案 / 测验

- 先推 `metadata`
- 各关键阶段推 `status`
- 最终 assistant 文案走 `delta`
- artifact 完成后推 `result`
- 最后 `done`

这样前端能感知“正在做什么”，又不需要把每个 workflow 内部实现完全改造成 token 级流式。

## 数据模型变化

### 后端

新增：

- `ChatStreamEnvelopeV2`
- `ChatStreamMetadataPayloadV2`
- `ChatStreamStatusPayloadV2`
- `ChatStreamDeltaPayloadV2`
- `ChatStreamResultPayloadV2`

### 前端

新增：

- `ChatStreamEventV2`
- `startChatReplyV2Stream` 或 `sendChatReplyV2Stream`

## 错误处理

### 后端

- 检索失败：返回 `error` 或降级为空 sources 后继续流式
- 模型流式中断：发送 `error`
- finalize 失败：发送 `error`

### 前端

- 若收到 `error`
  - 将当前 AI 消息标记为失败
  - 保留已收到的文本
- 若 stream 建立失败
  - 可降级调用现有 `/api/chat/v2/reply`

## 测试

### 后端

- `reply_stream` fast path：
  - 先 metadata
  - 再 delta
  - 最后 result / done
- `reply_stream` workflow path：
  - 包含 status
  - 最终仍有 result / done
- 检索 sources 正确进入 metadata
- 最终 conversation store 正确写回

### 前端

- SSE/stream parser 能正确解析多帧
- `ChatPanel` 能先渲染 metadata sources
- `delta` 能逐步拼接
- `status` 能更新状态文本
- `result` 能补齐 artifacts / status card

## 分阶段实施建议

### Phase 1

- `chat v2` fast path 普通对话流式化
- metadata + delta + result + done

### Phase 2

- 工作流状态事件接入
- 报告 / PPT / 教案 / 测验统一使用 v2 stream

### Phase 3

- 前端移除对旧 `/api/chat/stream` 的主依赖
- 仅保留兼容 fallback

## 结论

主系统应当“仿照 `query_stream` 的节奏”，但不照搬其纯 RAG 结构。

最终方案是：

- `chat v2` 新增自己的流式路由
- 先检索、先发 metadata
- 再流式输出回答
- 工作流通过 status + result 事件统一纳入
- 最终仍由主系统负责状态卡、artifact、历史与当前会话写回

这能最大限度复用 `query_stream` 的优点，同时保住主系统现有能力。
