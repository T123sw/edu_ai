# 对话历史处理机制说明

## 概述

本 RAG 系统实现了完整的多轮对话支持，通过 `conversation_history` 参数和 `QueryRewrite` 机制，实现了对话上下文理解和指代消解。

---

## 1. 数据流转路径

```
前端发送请求
    ↓
conversation_history (List[Dict])
    ↓
API 层接收 (api.py)
    ↓
传递给 RAGSystem.query()
    ↓
分两路处理：
    ├─→ QueryRewrite: 重写查询（指代消解）
    └─→ LLM 对话: 构建完整上下文
```

---

## 2. 前端数据格式

### 请求示例

```json
{
  "question": "它的时间复杂度是多少？",
  "top_k": 5,
  "conversation_history": [
    {"role": "user", "content": "什么是红黑树？"},
    {"role": "assistant", "content": "红黑树是一种自平衡二叉查找树..."},
    {"role": "user", "content": "它有什么特点？"},
    {"role": "assistant", "content": "红黑树具有五个基本性质..."}
  ]
}
```

### 数据结构

- **字段**: `conversation_history`
- **类型**: `List[Dict[str, str]]`
- **必填**: 否（首轮对话可为空）
- **格式**: 每条消息包含 `role` 和 `content`
  - `role`: `"user"` | `"assistant"` | `"system"`
  - `content`: 消息内容（字符串）

---

## 3. 核心处理机制

### 3.1 QueryRewrite（查询重写）

**位置**: `system.py:2576` - `_rewrite_query()`

**作用**: 将含有指代词的问题改写为可独立检索的完整查询

#### 触发条件

系统会智能判断是否需要重写：

```python
# 跳过重写的情况：
- 问题过短（< 配置的最小字符数）
- 问题已经很完整且较长（>= 最大字符数 且 无指代词）
- 问题信息充分（>= 12 个 token 且 无指代词）

# 优先重写的情况：
- 包含指代词标记：["这个", "那个", "上面", "下面", "它", "他", "她", "其", "这部分", "那部分", "最后那部分"]
- 问题较短但有上下文依赖
```

#### 重写流程

```python
def _rewrite_query(question, conversation_history):
    # 1. 提取最近 N 轮对话（默认配置）
    recent = history[-self.query_rewrite_history_turns:]
    
    # 2. 构建提示词
    prompt = """
    你是检索查询重写器。请将"当前问题"改写为一个可独立检索的简洁查询，
    保留核心实体、时间、约束条件；如果当前问题已完整清晰，则原样返回。
    只输出改写后的查询，不要解释。
    """
    
    # 3. 调用 LLM 重写
    user_content = f"""
    【对话历史】
    user: 什么是红黑树？
    assistant: 红黑树是一种自平衡二叉查找树...
    
    【当前问题】
    它的时间复杂度是多少？
    
    请输出改写后的检索查询：
    """
    
    # 4. 质量门控
    # - 检查重写结果长度
    # - 检查关键实体是否保留
    # - 避免改写为无效内容
    
    # 5. 返回重写结果或原问题
    return rewritten_query
```

#### 重写示例

| 原问题 | 对话历史 | 重写后 |
|--------|---------|--------|
| "它的时间复杂度是多少？" | 上文讨论红黑树 | "红黑树的时间复杂度" |
| "这个算法怎么实现？" | 上文讨论快速排序 | "快速排序算法的实现" |
| "上面提到的那个特性是什么？" | 上文讨论 Python GIL | "Python GIL 的特性" |

#### 配置参数

```python
# system.py 中的配置
query_rewrite_enabled = True  # 是否启用查询重写
query_rewrite_min_chars = 3   # 最小字符数
query_rewrite_max_chars = 50  # 最大字符数
query_rewrite_min_tokens = 2  # 重写结果最小 token 数
query_rewrite_history_turns = 3  # 使用最近 N 轮对话
```

---

### 3.2 历史对话窗口管理

**位置**: `system.py:3081-3102`

#### 窗口大小

```python
# core/config.py
CHAT_HISTORY_WINDOW = 5  # 保留最近 5 轮对话
```

#### 历史清理逻辑

```python
if conversation_history:
    # 取最近 N 轮对话
    recent_history = conversation_history[-Config.CHAT_HISTORY_WINDOW:]
    
    for msg in recent_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        # 清理历史消息中的检索上下文（避免重复注入）
        if role == "user" and use_rag:
            # 移除之前注入的【参考资料】部分
            context_marker = "【参考资料】"
            question_marker = "问题："
            if context_marker in content and question_marker in content:
                # 只保留纯问题部分
                question_start = content.find(question_marker)
                content = content[question_start + len(question_marker):].strip()
        
        messages.append({"role": role, "content": content})
```

**关键点**: 系统会自动清理历史消息中的检索上下文，避免上下文污染和 token 浪费。

---

### 3.3 完整处理流程

```python
# system.py:3104-3113
def query(question, conversation_history, ...):
    # 步骤 1: 查询重写（用于检索）
    retrieval_query = self._rewrite_query(question, conversation_history)
    print(f"[QueryRewrite] 原问题：{question}")
    print(f"[QueryRewrite] 重写后：{retrieval_query}")
    
    # 步骤 2: 使用重写后的查询进行向量检索
    query_embedding = self.embedding_client.embed_query(retrieval_query)
    retrieved_docs = self.vector_store.hybrid_search(...)
    
    # 步骤 3: 构建 LLM 消息（使用原始问题 + 历史对话）
    messages = []
    messages.append({"role": "system", "content": system_prompt})
    
    # 添加历史对话（已清理）
    if conversation_history:
        recent_history = conversation_history[-Config.CHAT_HISTORY_WINDOW:]
        for msg in recent_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 添加当前问题 + 检索到的上下文
    messages.append({
        "role": "user",
        "content": f"【参考资料】\n{context}\n\n问题：{question}"
    })
    
    # 步骤 4: 调用 LLM 生成回答
    answer = self._call_llm(messages)
```

---

## 4. API 层处理

### 4.1 非流式接口

**位置**: `api.py:395-410`

```python
@router.post("/query")
async def rag_query(request: QueryRequest):
    result = rag_system.query(
        request.question,
        top_k=request.top_k,
        conversation_history=request.conversation_history,  # 直接传递
        use_enhanced_retrieval=request.use_enhanced_retrieval,
        hyde_weight=request.hyde_weight,
        use_rrf=request.use_rrf
    )
    return QueryResponse(**result)
```

### 4.2 流式接口

**位置**: `api.py:674-677`

```python
@router.post("/query_stream")
async def rag_query_stream(request: QueryRequest):
    # 先进行查询重写
    retrieval_query = rag_system._rewrite_query(
        request.question, 
        request.conversation_history
    )
    
    # 执行检索
    retrieved_docs = rag_system.vector_store.hybrid_search(...)
    
    # 构建消息（包含历史）
    messages = [{"role": "system", "content": system_prompt}]
    
    if request.conversation_history:
        for msg in request.conversation_history[-10:]:  # 取最近 10 条
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 流式生成
    def generate():
        stream_generator = rag_system._call_llm(messages=messages, stream=True)
        for chunk in stream_generator:
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
```

---

## 5. 前端集成建议

### 5.1 状态管理

```javascript
// 维护对话历史
const [conversationHistory, setConversationHistory] = useState([]);

// 发送消息
const sendMessage = async (question) => {
  const response = await fetch('/api/rag/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      conversation_history: conversationHistory,
      top_k: 5
    })
  });
  
  const result = await response.json();
  
  // 更新历史
  setConversationHistory([
    ...conversationHistory,
    { role: 'user', content: question },
    { role: 'assistant', content: result.answer }
  ]);
};
```

### 5.2 历史管理策略

```javascript
// 策略 1: 限制历史长度（推荐）
const MAX_HISTORY = 10;  // 保留最近 10 条消息
const trimmedHistory = conversationHistory.slice(-MAX_HISTORY);

// 策略 2: 清空历史（新话题）
const clearHistory = () => {
  setConversationHistory([]);
};

// 策略 3: 只发送用户消息和助手回复（不包含系统消息）
const cleanHistory = conversationHistory.filter(
  msg => msg.role === 'user' || msg.role === 'assistant'
);
```

### 5.3 注意事项

1. **不要发送检索上下文**: 历史消息中只保留纯问题，不要包含 `【参考资料】` 等后端注入的内容
2. **控制历史长度**: 建议前端只发送最近 5-10 轮对话，避免 token 浪费
3. **角色规范**: 确保 `role` 字段只使用 `user`、`assistant`、`system` 三种值
4. **空内容过滤**: 发送前过滤掉空消息

---

## 6. 配置与调优

### 6.1 查询重写配置

```python
# system.py 中可调整的参数
self.query_rewrite_enabled = True           # 是否启用
self.query_rewrite_min_chars = 3            # 最小字符数
self.query_rewrite_max_chars = 50           # 最大字符数
self.query_rewrite_min_tokens = 2           # 重写结果最小 token
self.query_rewrite_history_turns = 3        # 使用历史轮数
```

### 6.2 历史窗口配置

```python
# core/config.py
CHAT_HISTORY_WINDOW = 5  # LLM 对话使用的历史窗口

# api.py (流式接口)
conversation_history[-10:]  # 流式接口使用 10 条历史
```

### 6.3 性能优化建议

| 场景 | 建议配置 |
|------|---------|
| 短对话场景 | `CHAT_HISTORY_WINDOW = 3` |
| 长对话场景 | `CHAT_HISTORY_WINDOW = 10` |
| 高并发场景 | 禁用 QueryRewrite 或减少 `history_turns` |
| 精确检索场景 | 启用 QueryRewrite + 增加 `history_turns` |

---

## 7. 调试与日志

### 7.1 查询重写日志

```python
# 系统会自动打印重写过程
[QueryRewrite] 原问题：它的时间复杂度是多少？
[QueryRewrite] 重写后：红黑树的时间复杂度
[QueryRewrite] 重写成功：'它的时间复杂度是多少？' -> '红黑树的时间复杂度'

# 跳过重写的情况
[QueryRewrite] 问题过短，跳过重写
[QueryRewrite] 问题已较完整且较长，跳过重写
[QueryRewrite] 问题信息充分，跳过重写

# 降级情况
[QueryRewrite] 返回为空，降级使用原问题
[QueryRewrite] 重写结果过短，降级使用原问题
[QueryRewrite] 关键实体可能丢失 ['红黑树']，降级使用原问题
[QueryRewrite] 重写失败，降级使用原问题：{error}
```

### 7.2 前端调试

```javascript
// 打印发送的历史
console.log('Sending conversation_history:', conversationHistory);

// 检查历史格式
conversationHistory.forEach((msg, idx) => {
  if (!msg.role || !msg.content) {
    console.error(`Invalid message at index ${idx}:`, msg);
  }
});
```

---

## 8. 常见问题

### Q1: 为什么重写后的查询和原问题一样？

A: 系统判断原问题已经足够清晰，不需要重写。这是正常行为。

### Q2: 重写功能可以关闭吗？

A: 可以，在 `system.py` 中设置 `query_rewrite_enabled = False`。

### Q3: 历史对话会影响检索结果吗？

A: 会。通过 QueryRewrite 机制，历史对话会用于指代消解，生成更准确的检索查询。

### Q4: 前端需要清理历史消息中的【参考资料】吗？

A: 不需要。后端会自动清理历史消息中的检索上下文（`system.py:3092-3101`）。

### Q5: 流式接口和非流式接口的历史处理有区别吗？

A: 有细微区别。流式接口默认取最近 10 条历史（`api.py:676`），非流式接口使用配置的窗口大小（默认 5 条）。

---

## 9. 总结

本系统的对话历史处理机制包含两个核心功能：

1. **QueryRewrite（查询重写）**: 智能识别指代词，结合历史对话生成可独立检索的查询
2. **历史窗口管理**: 自动清理和截断历史消息，避免上下文污染

前端只需按标准格式发送 `conversation_history`，后端会自动处理所有复杂逻辑，实现流畅的多轮对话体验。
