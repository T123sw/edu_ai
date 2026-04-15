# 前端开发交接文档 (Frontend Handover)

你好！这是 RAG 后端服务的接口与交互说明。为了让你能更丝滑地对接，请仔细阅读以下内容。

## 📋 项目概述

本项目是一个**多模态 RAG（检索增强生成）系统**，支持：
- 📄 多种格式文档导入（PDF、Word、Markdown、图片等）
- 🔍 智能检索（HyDE + BM25/ChromaDB 多路召回 + Rerank 精排）
- 💬 智能问答（DeepSeek/Gemini/Qwen 等大模型）
- 📊 检索质量量化与溯源展示

---

## 1. 📖 接口文档在哪里？

**无需阅读复杂的后端代码！** 我们使用 `FastAPI` 框架，它会自动生成一份完整的、可交互的接口文档。

- **访问地址**：启动后端服务后，在浏览器打开 `http://localhost:8000/docs`
- **功能**：你可以在这里看到所有接口的 URL、请求方式、参数定义，甚至可以直接点击 "Try it out" 进行 Mock 测试。
- **推荐工具**：也可以使用 Postman、Apifox 等工具导入 OpenAPI 规范。

---

## 2. 💡 核心业务逻辑说明

我们的系统主要包含三类交互场景，请注意区分：

### A. 知识库上传 (Import)

- **接口路径**：`POST /api/rag/import`
- **数据格式**：必须使用 `Multipart/form-data` 格式提交文件。
- **参数说明**：
  - `file`: 上传的文件（支持 PDF、DOCX、MD、TXT、PNG、JPG 等）
  - `owner`: 可选，文档所有者用户名
- **性能提示**：
  - 后台集成了 **MinerU** 引擎，会对 PDF 进行深度解析（提取公式、排版和图片）。
  - 这个过程比普通的文本读取要慢得多（通常在 **10s - 60s** 不等，取决于文件大小和复杂度）。
- **前端建议**：
  - ✅ 用户上传文件后，务必展示一个 **Loading 状态或进度条**。
  - ✅ 提示文案：“正在深度解析中，请稍候...”
  - ❌ 避免用户以为页面卡死而重复点击。
  - 💡 可以考虑使用 WebSocket 或轮询查询导入进度（如果需要实时反馈）。

### B. 智能问答 (Query)

- **接口路径**：`POST /api/rag/query`
- **请求体示例**：
```json
{
  "question": "什么是红黑树？",
  "top_k": 5,
  "use_enhanced_retrieval": false,
  "hyde_weight": 0.5,
  "use_rrf": true,
  "conversation_history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮助你的？"}
  ]
}
```

- **参数说明**：
  - `question`: 用户问题（必填）
  - `top_k`: 检索文档数量（默认 5，范围 1-20）
  - `use_enhanced_retrieval`: 是否使用增强检索（HyDE + 多路召回 + RRF），默认 false
  - `hyde_weight`: HyDE 权重（0-1），默认 0.5
  - `use_rrf`: 是否使用 RRF 融合，默认 true
  - `conversation_history`: 对话历史记录（可选，用于多轮对话）

- **响应示例**：
```json
{
  "question": "什么是红黑树？",
  "answer": "红黑树是一种自平衡二叉查找树^1^。它具有五个基本性质^2^...",
  "sources": [
    {
      "source": "红黑树基础.md",
      "content": "红黑树是一种自平衡二叉查找树...",
      "rerank_score": 0.92
    }
  ],
  "retrieval_metrics": {
    "max_score": 0.92,
    "avg_score": 0.85,
    "confidence_level": "High",
    "doc_count": 5,
    "rerank_enabled": true
  }
}
```

- **交互方式**：标准的 JSON 交互（目前不支持流式输出）。
- **上下文处理**：后端会自动处理对话历史窗口，前端只需按顺序发送当前问题和历史记录即可。

### C. 文档管理 (Documents)

- **获取文档列表**：`GET /api/rag/documents`
- **删除文档**：`DELETE /api/rag/documents/{document_id}`
- **切换搜索状态**：`PUT /api/rag/documents/{document_id}/toggle-search`
- **获取统计信息**：`GET /api/rag/stats`

---

## 3. 📦 响应格式规范

后端所有接口均返回统一的 JSON 结构，方便你进行全局拦截处理：

```json
{
  "code": 200,      // 状态码：200 表示成功，其他为异常
  "data": { ... },  // 具体的业务数据
  "msg": "success"  // 提示信息，出错时会包含具体原因
}
```

**常见错误码：**
- `200`: 成功
- `400`: 请求参数错误
- `401`: 未授权（需要登录）
- `404`: 资源不存在
- `500`: 服务器内部错误

---

## 4. ⚠️ 渲染特殊要求 (非常重要！)

为了让用户知道 AI 的回答是基于哪份文档生成的，后端在返回答案时，会嵌入一些**溯源引用的标记**。

### 📊 数据流说明

完整的引用对应流程如下：

```
┌─────────────┐
│  LLM 生成   │  回答中包含 <cite source="xxx.md" score="0.92">内容</cite>
│  原始回答   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  后端处理   │  1. 解析 <cite> 标签
│ (webui.py)  │  2. 提取 source、score、content
└──────┬──────┘  3. 清洗脏数据（移除乱码、重复标题）
       │         4. 替换为上标数字 ^1^、^2^
       │         5. 在文末添加可展开的参考资料卡片
       ▼
┌─────────────┐
│  前端接收   │  answer: "红黑树是一种自平衡二叉查找树^1^..."
│             │  sources: [{source, score, content}, ...]
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  前端渲染   │  1. 将 ^数字^ 渲染为上标
│             │  2. 渲染文末的 <details> 卡片
└─────────────┘
```

---

### 🔍 引用格式详解

#### 后端返回的数据结构

```json
{
  "question": "什么是红黑树？",
  "answer": "红黑树是一种自平衡二叉查找树^1^。它具有五个基本性质^2^...\n\n---\n\n### 📚 参考资料\n\n<details>...</details>",
  "sources": [
    {
      "source": "红黑树基础.md",
      "content": "红黑树是一种自平衡二叉查找树，其查找、插入、删除操作的时间复杂度均为 O(log n)...",
      "rerank_score": 0.92
    },
    {
      "source": "数据结构.md",
      "content": "红黑树具有五个基本性质：1.每个节点要么是红色要么是黑色...",
      "rerank_score": 0.88
    }
  ],
  "retrieval_metrics": {
    "max_score": 0.92,
    "avg_score": 0.85,
    "confidence_level": "High",
    "doc_count": 5,
    "rerank_enabled": true
  }
}
```

#### 引用标记格式

后端返回的 `answer` 字段中，引用标记使用 **上标数字** 格式：

```markdown
红黑树是一种自平衡二叉查找树^1^。它具有五个基本性质^2^...
```

- `^1^` 表示第一个引用
- `^2^` 表示第二个引用
- 依此类推...

在回答末尾，会有一个**可展开的参考资料列表**，使用 HTML `<details>` 标签：

```html
### 📚 参考资料

<details style="margin: 8px 0; padding: 8px 12px; background: #f6f8fa; border-left: 3px solid #0366d6;">
  <summary style="cursor: pointer; font-weight: 600; color: #0366d6;">
    📄 红黑树基础.md (相关性：0.92)
  </summary>
  <div style="margin-top: 8px; padding: 8px; background: white;">
    <strong>原文内容：</strong><br>
    红黑树是一种自平衡二叉查找树...
  </div>
</details>

<details style="margin: 8px 0; padding: 8px 12px; background: #f6f8fa; border-left: 3px solid #0366d6;">
  <summary style="cursor: pointer; font-weight: 600; color: #0366d6;">
    📄 数据结构.md (相关性：0.88)
  </summary>
  <div style="margin-top: 8px; padding: 8px; background: white;">
    <strong>原文内容：</strong><br>
    红黑树具有五个基本性质...
  </div>
</details>
```

---

### 💻 前端实现方案

在渲染对话气泡（Chat Bubble）中的 `answer` 字段时，**不能简单地作为纯文本显示**。

以下是三种实现方案，从简单到复杂：

---

#### 方案 1：使用 Markdown 渲染库（推荐⭐⭐⭐）

这是最简单、最推荐的方案。Markdown 渲染库会自动处理上标和 HTML 标签。

##### React 实现

**安装依赖：**
```bash
npm install react-markdown remark-gfm rehype-raw
```

**代码示例：**
```jsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

function ChatMessage({ message }) {
  return (
    <div className="chat-bubble">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          // 自定义上标渲染
          sup: ({ node, children, ...props }) => (
            <sup 
              style={{ 
                color: '#0366d6', 
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
              {...props}
            >
              {children}
            </sup>
          )
        }}
      >
        {message.answer}
      </ReactMarkdown>
    </div>
  );
}

export default ChatMessage;
```

##### Vue 3 实现

**安装依赖：**
```bash
npm install markdown-it @types/markdown-it
```

**代码示例：**
```vue
<template>
  <div class="chat-bubble" v-html="renderedAnswer"></div>
</template>

<script setup>
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';

const props = defineProps({
  message: Object
});

const md = new MarkdownIt({
  html: true,  // 允许 HTML 标签
  linkify: true,
  typographer: true
});

const renderedAnswer = computed(() => {
  return md.render(props.message.answer);
});
</script>

<style scoped>
.chat-bubble :deep(sup) {
  color: #0366d6;
  cursor: pointer;
  font-weight: bold;
}
</style>
```

**优点：**
- ✅ 简单易用，几行代码搞定
- ✅ 自动处理 Markdown 语法
- ✅ 支持 HTML 标签（`<details>`）
- ✅ 社区活跃，文档完善

**缺点：**
- ❌ 需要引入额外的库
- ❌ 包体积稍大

---

#### 方案 2：使用 HTML 富文本解析（轻量级）

如果不想引入 Markdown 库，可以直接渲染 HTML。

##### React 实现

```jsx
import React from 'react';
import DOMPurify from 'dompurify';  // 安全处理

function ChatMessage({ message }) {
  // 1. 将 ^数字^ 替换为 <sup> 标签
  const processedAnswer = message.answer.replace(
    /\^(\d+)\^/g, 
    '<sup style="color: #0366d6; cursor: pointer; font-weight: bold;">$1</sup>'
  );
  
  // 2. 安全处理 HTML（防止 XSS）
  const cleanHTML = DOMPurify.sanitize(processedAnswer);
  
  return (
    <div 
      className="chat-bubble"
      dangerouslySetInnerHTML={{ __html: cleanHTML }}
    />
  );
}

export default ChatMessage;
```

##### Vue 3 实现

```vue
<template>
  <div class="chat-bubble" v-html="safeHTML"></div>
</template>

<script setup>
import { computed } from 'vue';
import DOMPurify from 'dompurify';

const props = defineProps({
  message: Object
});

const safeHTML = computed(() => {
  // 1. 将 ^数字^ 替换为 <sup> 标签
  let html = props.message.answer.replace(
    /\^(\d+)\^/g, 
    '<sup style="color: #0366d6; cursor: pointer; font-weight: bold;">$1</sup>'
  );
  
  // 2. 安全处理 HTML
  return DOMPurify.sanitize(html);
});
</script>
```

**安装 DOMPurify：**
```bash
npm install dompurify
```

**优点：**
- ✅ 轻量级，无需 Markdown 解析器
- ✅ 完全控制渲染效果
- ✅ 性能好

**缺点：**
- ❌ 需要手动处理 Markdown 语法
- ❌ 需要注意 XSS 安全

---

#### 方案 3：自定义解析器（完全控制）

如果需要完全控制渲染逻辑，可以编写自定义解析器。

##### 完整实现示例（React）

```jsx
import React, { useState } from 'react';

function ChatMessage({ message }) {
  const [expandedRefs, setExpandedRefs] = useState({});
  
  // 1. 解析 answer，提取上标数字
  const parseAnswer = (text) => {
    const parts = [];
    let lastIndex = 0;
    const regex = /\^(\d+)\^/g;
    let match;
    
    while ((match = regex.exec(text)) !== null) {
      // 添加普通文本
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: text.slice(lastIndex, match.index)
        });
      }
      
      // 添加引用标记
      parts.push({
        type: 'citation',
        index: parseInt(match[1]),
        original: match[0]
      });
      
      lastIndex = regex.lastIndex;
    }
    
    // 添加剩余文本
    if (lastIndex < text.length) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex)
      });
    }
    
    return parts;
  };
  
  // 2. 切换引用展开状态
  const toggleRef = (index) => {
    setExpandedRefs(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };
  
  const parsedParts = parseAnswer(message.answer);
  
  return (
    <div className="chat-message">
      {/* 渲染回答正文 */}
      <div className="answer-body">
        {parsedParts.map((part, idx) => {
          if (part.type === 'text') {
            return <span key={idx}>{part.content}</span>;
          } else if (part.type === 'citation') {
            return (
              <sup
                key={idx}
                onClick={() => toggleRef(part.index)}
                style={{
                  color: '#0366d6',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  textDecoration: expandedRefs[part.index] ? 'underline' : 'none'
                }}
                title={`点击查看来源 ${part.index}`}
              >
                {part.index}
              </sup>
            );
          }
          return null;
        })}
      </div>
      
      {/* 渲染参考资料列表 */}
      {message.sources && message.sources.length > 0 && (
        <div className="references-section">
          <h3>📚 参考资料</h3>
          {message.sources.map((source, idx) => (
            <div 
              key={idx}
              className={`reference-card ${expandedRefs[idx + 1] ? 'expanded' : ''}`}
              onClick={() => toggleRef(idx + 1)}
            >
              <div className="reference-header">
                <span className="ref-icon">📄</span>
                <span className="ref-title">{source.source}</span>
                <span className="ref-score">(相关性：{source.rerank_score?.toFixed(2) || 'N/A'})</span>
                <span className="ref-toggle">
                  {expandedRefs[idx + 1] ? '▲' : '▼'}
                </span>
              </div>
              
              {expandedRefs[idx + 1] && (
                <div className="reference-content">
                  <strong>原文内容：</strong>
                  <p>{source.content}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ChatMessage;
```

**配套 CSS：**
```css
.chat-message {
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.answer-body {
  line-height: 1.6;
  color: #24292e;
}

.references-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 2px solid #e1e4e8;
}

.references-section h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #0366d6;
}

.reference-card {
  margin: 8px 0;
  padding: 12px;
  background: #f6f8fa;
  border-left: 3px solid #0366d6;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.reference-card:hover {
  background: #eef1f3;
}

.reference-card.expanded {
  background: #fff;
  border: 1px solid #e1e4e8;
}

.reference-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ref-icon {
  font-size: 16px;
}

.ref-title {
  font-weight: 600;
  color: #0366d6;
  flex: 1;
}

.ref-score {
  color: #6a737d;
  font-size: 14px;
}

.ref-toggle {
  color: #6a737d;
  font-size: 12px;
}

.reference-content {
  margin-top: 8px;
  padding: 8px;
  background: #fafbfc;
  border-radius: 3px;
  font-size: 14px;
  line-height: 1.5;
  color: #586069;
}

.reference-content p {
  margin: 4px 0 0 0;
}
```

**优点：**
- ✅ 完全控制交互逻辑
- ✅ 可以实现点击上标跳转到对应引用
- ✅ 可以高亮当前选中的引用
- ✅ 灵活的动画效果

**缺点：**
- ❌ 代码量大
- ❌ 需要自己处理所有细节

---

### 🎯 最佳实践建议

#### 1. 安全性第一

无论使用哪种方案，都要注意 **XSS 攻击防护**：

```javascript
// ❌ 危险：直接渲染用户输入
<div dangerouslySetInnerHTML={{ __html: answer }} />

// ✅ 安全：先 sanitize
import DOMPurify from 'dompurify';
const cleanHTML = DOMPurify.sanitize(answer);
<div dangerouslySetInnerHTML={{ __html: cleanHTML }} />
```

#### 2. 用户体验优化

- **悬停提示**：鼠标悬停在上标数字时，显示来源文件名
- **点击跳转**：点击上标数字，滚动到对应的参考资料卡片
- **高亮显示**：展开的参考资料卡片高亮显示
- **平滑动画**：展开/收起时使用过渡动画

#### 3. 响应式设计

确保在小屏幕上也能正常显示：

```css
@media (max-width: 768px) {
  .reference-card {
    padding: 8px;
  }
  
  .reference-header {
    flex-wrap: wrap;
  }
  
  .ref-score {
    width: 100%;
    margin-top: 4px;
  }
}
```

#### 4. 无障碍访问

为视障用户提供支持：

```jsx
<sup 
  role="button"
  tabIndex={0}
  aria-label={`查看引用来源 ${index}`}
  onKeyDown={(e) => e.key === 'Enter' && toggleRef(index)}
>
  {index}
</sup>
```

---

### 📝 总结对比

| 方案 | 难度 | 灵活性 | 性能 | 推荐场景 |
|------|------|--------|------|----------|
| **方案 1: Markdown 库** | ⭐简单 | ⭐⭐中等 | ⭐⭐⭐好 | 快速开发，标准需求 |
| **方案 2: HTML 解析** | ⭐⭐中等 | ⭐⭐⭐高 | ⭐⭐⭐⭐优秀 | 轻量级项目 |
| **方案 3: 自定义解析** | ⭐⭐⭐困难 | ⭐⭐⭐⭐⭐最高 | ⭐⭐⭐⭐⭐最优 | 高度定制化需求 |

**我的建议：**
- 🚀 **新手/快速开发** → 选择方案 1
- ⚖️ **平衡性能和复杂度** → 选择方案 2
- 🎨 **追求极致体验** → 选择方案 3

如果需要完全控制渲染效果，可以编写一个简单的解析器：

```javascript
function renderAnswer(answer) {
  // 1. 将 ^数字^ 替换为上标
  answer = answer.replace(/\^(\d+)\^/g, '<sup>$1</sup>');
  
  // 2. 渲染 HTML
  return <div dangerouslySetInnerHTML={{ __html: answer }} />;
}
```

### 样式建议

参考资料卡片应该具有以下特点：
- ✅ **左侧蓝色边框** - 视觉清晰
- ✅ **灰色背景** - 与正文区分
- ✅ **圆角设计** - 美观现代
- ✅ **鼠标指针** - 提示可点击
- ✅ **白色内容区** - 展开后背景变白

---

## 5. 🎨 UI/UX 设计建议

### 聊天界面布局

```
┌─────────────────────────────────────┐
│  [侧边栏]        │   [主聊天区]     │
│                  │                  │
│  ⚙️ 检索设置    │  👤 用户问题     │
│  - Top K: 5     │                  │
│  - 增强检索: ☑️  │  🤖 AI 回答     │
│                  │  ^1^ ^2^ ^3^    │
│  📚 文档管理    │                  │
│  - 上传文档      │  ---            │
│  - 查看列表      │  ### 📚 参考资料 │
│  - 删除文档      │  📄 文件1.md ▼  │
│                  │  📄 文件2.md ▼  │
│                  │                  │
│                  │  [输入框] 📎    │
└─────────────────────────────────────┘
```

### 关键交互点

1. **文件上传**：
   - 拖拽上传 or 点击选择
   - 显示上传进度
   - 成功后显示文档名称和大小

2. **聊天输入**：
   - 支持 Enter 发送，Shift+Enter 换行
   - 显示 Loading 状态
   - 支持多轮对话（自动携带历史记录）

3. **引用展示**：
   - 正文中用上标数字标记 `¹`、`²`
   - 文末用可展开卡片展示详情
   - 点击卡片标题展开/收起

4. **检索质量评估**：
   - 可选：在回答下方显示检索质量指标
   - 最高分、平均分、置信度等级
   - 帮助用户判断回答可靠性

---

## 6. 🛠️ 技术栈建议

### 前端框架

- **React** + Vite（推荐）
- **Vue 3** + Vite
- **SvelteKit**
- **Next.js** / **Nuxt.js**（如果需要 SSR）

### UI 组件库

- **Ant Design**（企业级，功能丰富）
- **Element Plus**（Vue 生态）
- **Material-UI**（Material Design）
- **TailwindCSS**（原子化 CSS，高度自定义）

### HTTP 客户端

- **Axios**（推荐，功能强大）
- **Fetch API**（原生，轻量）
- **TanStack Query**（React Query，数据缓存）

### Markdown 渲染

- **react-markdown**（React）
- **markdown-it**（Vue/通用）
- **marked**（轻量级）

---

## 7. 🚀 快速开始

### 步骤 1：启动后端服务

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 API Key 等配置

# 启动服务
python main.py
```

### 步骤 2：访问接口文档

打开浏览器访问：`http://localhost:8000/docs`

### 步骤 3：测试接口

使用 Postman 或 curl 测试接口：

```bash
# 测试问答接口
curl -X POST http://localhost:8000/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是红黑树？",
    "top_k": 5
  }'
```

### 步骤 4：开始前端开发

根据你的技术栈选择，创建新项目并集成 API。

---

## 8. ❓ 常见问题

### Q1: 为什么文件上传很慢？

A: 因为后台使用了 MinerU 引擎对 PDF 进行深度解析，包括 OCR、公式识别、版面分析等。这是正常现象，建议在 UI 上给予用户明确的进度提示。

### Q2: 如何实现流式输出？

A: 当前版本暂不支持流式输出。如果需要，可以联系后端开发人员添加 SSE（Server-Sent Events）支持。

### Q3: 引用标记为什么不直接用 HTML 标签？

A: 为了避免 Streamlit 等框架的 HTML 转义问题，我们采用了简单的上标数字格式 `^1^`，并在文末统一展示参考资料。这种方式兼容性更好。

### Q4: 如何获取用户的认证信息？

A: 如果启用了认证，需要在请求头中添加 `Authorization: Bearer <token>`。Token 可以通过登录接口获取。

---

## 9. 📞 联系方式

如有任何接口细节疑问，请：

1. 查阅 `/docs` 页面的接口文档
2. 查看 `api.py` 源码了解详细实现
3. 联系后端负责人

祝合作愉快！🚀
