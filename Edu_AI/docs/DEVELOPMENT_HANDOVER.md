# 交接文档

# 一、聊天对话功能增强

### 1.1 消息气泡操作功能

为 Assistant 和 User 的对话气泡分别添加了完整的操作功能：

**Assistant 消息操作：**

- **复制**：一键复制整条回答内容
- **重新生成**：重新调用 LLM 生成回答，同步后端对话历史
- **复制选中文本**：支持选中部分文本后复制
- **删除此轮对话**：删除当前问答对，同步后端

**User 消息操作：**
- **复制**：复制用户提问内容
- **编辑并重发**：修改提问内容后重新发送，自动截断后续对话
- **删除此轮对话**：删除当前问答对，同步后端

**相关文件：**

- `src/pages/ChatPage.tsx` - 前端组件实现
- `src/services/chat.ts` - API 服务封装
- `api/Edu_AI/app/main.py` - 后端接口（truncate、delete_message_pair）

### 1.2 后端对话管理接口

新增/优化的后端接口：

```python
# 截断对话（用于编辑重发）
POST /conversations/{conversation_id}/truncate?keep_count={n}

# 删除指定消息对
DELETE /conversations/{conversation_id}/messages/{message_index}
```

---

## 二、消息渲染功能

### 2.1 思考过程展开/收起

支持带思考标签的模型输出（如 `<think>`、`<thinking>`、`<thought>`），自动解析并提供可折叠的思考过程展示。

**实现逻辑：**
```typescript
// 解析思考内容
const parseThinkingContent = (content: string) => {
  const thinkPatterns = [
    /<think>([\s\S]*?)<\/think>/i,
    /<thinking>([\s\S]*?)<\/thinking>/i,
    /<thought>([\s\S]*?)<\/thought>/i,
  ];
  // 返回 { thinking, answer }
};
```

**UI 组件：**
- `ThinkingBlock` 组件：可点击展开/收起的思考过程区块

### 2.2 Markdown 渲染

集成 `react-markdown` 实现完整的 Markdown 渲染支持：

- **代码高亮**：使用 `react-syntax-highlighter` + `oneDark` 主题
- **表格渲染**：支持 GFM 表格语法，带滚动容器
- **LaTeX 公式**：集成 `remark-math` + `rehype-katex`

**依赖包：**
```json
{
  "react-markdown": "^9.x",
  "react-syntax-highlighter": "^15.x",
  "remark-gfm": "^4.x",
  "remark-math": "^6.x",
  "rehype-katex": "^7.x",
  "katex": "^0.16.x"
}
```

---

## 三、RAG 模式与自由对话模式分离

### 3.1 功能说明

实现了 `use_rag` 参数的完整传递，支持两种对话模式：

| 模式 | 说明 | 检索 |
|------|------|------|
| RAG 模式 | 检索增强生成 | ✅ 进行向量检索 |
| 自由对话模式 | 纯 LLM 对话 | ❌ 不检索 |

### 3.2 前端实现

```typescript
// ChatPage.tsx
const [useRAG, setUseRAG] = useState(true);

// 发送请求时传递参数
const request: ChatRequest = {
  question,
  conversation_id: currentConversationId,
  model_id: selectedModelId,
  use_rag: useRAG,  // 关键参数
};
```

### 3.3 后端实现

**ChatRequest 模型（main.py）：**
```python
class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)
    model_id: Optional[str] = None
    use_rag: Optional[bool] = Field(default=True)  # 新增字段
```

**RAGSystem.query 方法（system.py）：**
```python
def query(self, question, top_k=5, conversation_history=None, 
          llm_config=None, use_rag=True):
    if use_rag:
        # RAG 模式：检索 + 构建上下文
        query_embedding = self.embedding_client.embed_query(question)
        retrieved_docs = self.vector_store.search(...)
        # 构建带检索上下文的 prompt
    else:
        # 自由对话模式：直接对话
        messages.append({"role": "user", "content": question})
```

---

## 四、上下文历史组织优化

### 4.1 设计原则

- 使用列表格式维护对话历史
- RAG 模式下，历史消息**不包含**检索到的文档上下文
- 只保留纯净的问答对，避免上下文污染

### 4.2 实现细节

```python
# RAG 模式下清理历史消息中的检索上下文
if role == "user" and use_rag:
    context_marker = "【参考资料】"
    question_marker = "问题："
    if context_marker in content and question_marker in content:
        question_start = content.find(question_marker)
        if question_start != -1:
            content = content[question_start + len(question_marker):].strip()
```

### 4.3 上下文窗口配置

```python
# core/config.py
CHAT_HISTORY_WINDOW = int(os.getenv("CHAT_HISTORY_WINDOW", 6))
```

---

## 五、教师工具解析优化

### 5.1 问题背景

带思考过程的模型（如 Qwen3）输出会包含 `<think>` 标签，导致 JSON 解析失败。

### 5.2 解决方案

在教案生成和题目生成接口中，增加思考标签清理逻辑：

```python
def remove_thinking_tags(text: str) -> str:
    """移除各种思考过程标签"""
    patterns = [
        r'<think>.*?</think>',
        r'<thinking>.*?</thinking>',
        r'<thought>.*?</thought>',
    ]
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()
```

### 5.3 JSON 解析容错

```python
try:
    data = json.loads(cleaned_raw)
except json.JSONDecodeError:
    # 1. 去掉 Markdown 代码块
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`").split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    
    # 2. 提取最外层 JSON
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}")+1]
    
    # 3. 重试解析
    data = json.loads(cleaned)
```

**影响接口：**
- `POST /teacher/lesson_plan` - 教案生成
- `POST /teacher/questions` - 题目生成
- `POST /teacher/knowledge_points` - 知识点联想

---

## 六、文件变更清单

### 前端文件

| 文件 | 变更说明 |
|------|---------|
| `src/pages/ChatPage.tsx` | 消息操作、思考过程、Markdown 渲染、RAG 开关 |
| `src/pages/ChatPage.css` | 样式优化、文本选择支持 |
| `src/services/chat.ts` | ChatRequest 接口定义 |

### 后端文件

| 文件 | 变更说明 |
|------|---------|
| `api/Edu_AI/app/main.py` | ChatRequest 模型、use_rag 参数传递、思考标签清理 |
| `api/Edu_AI/new_rag/system.py` | RAGSystem.query 支持 use_rag 参数 |
| `api/Edu_AI/core/config.py` | CHAT_HISTORY_WINDOW 配置 |
