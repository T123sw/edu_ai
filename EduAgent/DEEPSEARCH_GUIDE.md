# 深度搜索模块使用指南

## 📋 概述

深度搜索（DeepSearch）是一个基于 LangGraph Agent 的智能搜索系统，能够：
- 自动分解复杂查询为子查询
- 使用多种工具进行网络搜索和页面扫描
- 智能筛选和整理搜索结果
- 返回结构化的相关链接列表

## 🔄 工作流程

```
用户查询
  ↓
Agent 初始化（LangGraph）
  ↓
┌─────────────────────────────────┐
│  Thought Node (思考节点)        │
│  - 分析查询需求                  │
│  - 规划搜索策略                  │
│  - 决定下一步行动                │
└─────────────────────────────────┘
  ↓
┌─────────────────────────────────┐
│  Action Node (行动节点)          │
│  - 选择要使用的工具              │
│  - 准备工具调用参数              │
└─────────────────────────────────┘
  ↓
┌─────────────────────────────────┐
│  Tool Node (工具节点)            │
│  - web_search: 网络搜索         │
│  - scan_page: 页面内容提取       │
│  - chat: 返回结果给用户          │
└─────────────────────────────────┘
  ↓
┌─────────────────────────────────┐
│  Reflex Node (反思节点)          │
│  - 评估当前进展                  │
│  - 决定是否继续或结束             │
└─────────────────────────────────┘
  ↓
返回 JSON 格式的链接列表
```

## 🛠️ 核心组件

### 1. **deepsearch.py** - 主入口

#### `deepsearch_large_llm(query: str) -> dict | None`

**功能：** 执行深度搜索的主函数

**参数：**
- `query`: 用户查询字符串

**返回值：**
- 成功：`{'links': ['url1', 'url2', ...]}`
- 失败：`None`

**工作流程：**
1. 从配置文件读取 DeepSeek API 密钥
2. 创建 LLM 实例（DeepSeek，temperature=0.2）
3. 创建 Agent，配置工具：`[scan_page, web_search]`
4. 调用 Agent，传入用户查询
5. 解析 Agent 返回的 JSON 格式链接列表
6. 最多重试 3 次

**示例：**
```python
from deepsearch import deepsearch_large_llm

result = deepsearch_large_llm("计算思维课程教学")
if result:
    print(f"找到 {len(result['links'])} 个链接:")
    for link in result['links']:
        print(f"  - {link}")
```

### 2. **Agent 工作流（LangGraph）**

#### 状态机节点

**Thought Node（思考节点）**
- 使用 `thought.md` 模板
- 分析当前状态和历史对话
- 输出纯文本思考内容
- 决定下一步行动方向

**Action Node（行动节点）**
- 使用 `action.md` 模板
- 基于思考结果选择工具
- 准备工具调用参数
- 支持的工具：`web_search`, `scan_page`, `chat`

**Tool Node（工具节点）**
- 执行选定的工具
- 处理工具返回结果
- 如果调用 `chat` 工具，则结束流程
- 否则继续到 Thought 或 Reflex 节点

**Reflex Node（反思节点）**
- 使用 `reflex.md` 模板
- 每 100 步执行一次（防止无限循环）
- 评估当前进展
- 决定是否继续或调整策略

### 3. **工具系统**

#### `web_search(query, top_k=8, language="zh-CN")`

**功能：** 使用 SearxNG 搜索引擎进行网络搜索

**参数：**
- `query`: 搜索查询
- `top_k`: 返回结果数量（默认 8）
- `language`: 语言代码（默认 "zh-CN"）

**返回：**
```python
[
    {
        "title": "页面标题",
        "url": "https://example.com",
        "snippet": "页面摘要",
        "engine": "搜索引擎名称"
    },
    ...
]
```

**配置：**
- 默认端点：`http://localhost:8090/search`
- 需要本地运行 SearxNG 实例

#### `scan_page(url)`

**功能：** 使用 Playwright 扫描网页并提取主要内容

**参数：**
- `url`: 要扫描的网页 URL

**返回：**
- 成功：页面文本内容（Markdown 格式）
- 失败：`None`

**特性：**
- 使用 Readability 算法提取正文
- 拦截图片/字体/媒体资源（提高速度）
- 超时控制（默认 45 秒）
- 支持 PDF 内容检测
- 自动处理 JavaScript 渲染

**工作流程：**
1. 使用 Playwright 加载页面
2. 等待页面加载完成（DOMContentLoaded）
3. 使用 Readability 提取正文
4. 转换为 Markdown 格式
5. 限制最大字符数（默认 4500）

## 📝 使用示例

### 1. **通过 API 调用**

```bash
# 使用 curl
curl -X POST "http://127.0.0.1:8848/agent/deepsearch?query=计算思维课程教学" \
  -H "Content-Type: application/json"

# 使用 Python requests
import requests

response = requests.post(
    "http://127.0.0.1:8848/agent/deepsearch",
    params={"query": "计算思维课程教学"}
)
result = response.json()
print(result)
```

**响应格式：**
```json
{
    "ok": true,
    "query": "计算思维课程教学",
    "results": [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3"
    ]
}
```

### 2. **直接调用函数**

```python
from deepsearch import deepsearch_large_llm

# 执行搜索
query = "计算思维课程教学"
result = deepsearch_large_llm(query)

if result:
    links = result['links']
    print(f"找到 {len(links)} 个相关链接:")
    for i, link in enumerate(links, 1):
        print(f"{i}. {link}")
else:
    print("搜索失败，请检查配置和网络连接")
```

### 3. **在代码中集成**

```python
from deepsearch import deepsearch_large_llm
from main import app

@app.post("/custom/search")
def custom_search(query: str):
    """自定义搜索接口"""
    result = deepsearch_large_llm(query)
    
    if not result:
        return {
            "ok": False,
            "message": "搜索失败"
        }
    
    return {
        "ok": True,
        "query": query,
        "links": result['links'],
        "count": len(result['links'])
    }
```

## ⚙️ 配置要求

### 1. **API 密钥配置**

编辑 `config.toml`：
```toml
[api_key]
deepseek_api_key='your_deepseek_api_key_here'
```

### 2. **SearxNG 配置**

**选项 1：使用本地 SearxNG**
```bash
# 安装并运行 SearxNG
docker run -d -p 8090:8080 searxng/searxng
```

**选项 2：使用 SerpAPI（需要修改代码）**
- 在 `tools/search/websearch.py` 中配置 SerpAPI 密钥
- 修改 `google_search` 函数使用 SerpAPI

### 3. **Playwright 安装**

```bash
# 安装 Playwright
pip install playwright
playwright install chromium
```

## 🔍 Agent 工作流程详解

### 初始输入

Agent 接收三个 HumanMessage：

1. **系统指令：**
   ```
   我需要你将我的话题（topic）分解为一些子查询，使用工具进行搜索，
   最后将搜索到的与我的话题相关的链接以JSON的形式通过chat返回给我
   ```

2. **用户查询：**
   ```
   我想查询的话题：{query}
   请至少返回5条链接，如果不足如实返回，查询不到返回一个JSON空列表
   ```

3. **输出格式示例：**
   ```
   最终通过chat返回的结果应为如下样例:
   ["link1", "link2", "link3"]
   ```

### Agent 执行步骤

1. **思考阶段：**
   - Agent 分析查询需求
   - 将复杂查询分解为多个子查询
   - 规划搜索策略

2. **行动阶段：**
   - 选择 `web_search` 工具进行搜索
   - 准备搜索查询参数

3. **工具执行：**
   - 调用 `web_search` 获取搜索结果
   - 可能调用 `scan_page` 扫描相关页面
   - 分析页面内容相关性

4. **迭代循环：**
   - 根据搜索结果继续思考
   - 可能需要多次搜索和扫描
   - 直到收集到足够的链接

5. **结果返回：**
   - 使用 `chat` 工具返回 JSON 格式的链接列表
   - 格式：`["url1", "url2", "url3"]`

### 递归限制

- 默认递归限制：49 步
- 防止无限循环
- 每 100 步执行一次反思

## 🐛 故障排查

### 问题 1：返回 None

**可能原因：**
- API 密钥未配置或无效
- Agent 返回的不是 JSON 格式
- 网络连接问题
- SearxNG 服务未运行

**解决方法：**
1. 检查 `config.toml` 中的 API 密钥
2. 查看日志文件 `logs/large_model_deepsearch.log`
3. 确认 SearxNG 服务运行在 `http://localhost:8090`
4. 检查网络连接

### 问题 2：搜索结果为空

**可能原因：**
- 查询过于具体或冷门
- SearxNG 配置问题
- 网络搜索工具未正确配置

**解决方法：**
1. 尝试更通用的查询关键词
2. 检查 SearxNG 是否正常运行
3. 查看 Agent 的思考日志，了解搜索过程

### 问题 3：Agent 超时

**可能原因：**
- 递归限制设置过低
- 网络请求超时
- 页面扫描超时

**解决方法：**
1. 增加递归限制（在 `deepsearch.py` 中修改）
2. 检查网络连接
3. 调整 Playwright 超时设置

## 📊 性能优化建议

1. **减少递归次数：**
   - 优化 Prompt，让 Agent 更高效
   - 减少不必要的页面扫描

2. **并行处理：**
   - 可以同时搜索多个子查询
   - 使用异步工具调用

3. **缓存结果：**
   - 对相同查询缓存结果
   - 避免重复搜索

4. **限制页面扫描：**
   - 只扫描最相关的页面
   - 设置合理的超时时间

## 🔗 与爬虫模块集成

深度搜索可以与自动化爬虫模块集成：

```python
from deepsearch import deepsearch_large_llm
from automation_spider.src.selenium_way.get_PDF_links_by_keywords import pdf_runner

# 1. 使用深度搜索找到相关主题
query = "计算思维"
search_result = deepsearch_large_llm(query)

if search_result:
    # 2. 从搜索结果中提取关键词
    # 3. 使用爬虫模块搜索 PDF
    for link in search_result['links']:
        # 提取关键词并搜索 PDF
        keywords = extract_keywords_from_url(link)
        pdf_runner(
            path="./output",
            keywords=keywords,
            pages=2
        )
```

## 📚 相关文件

- `deepsearch.py` - 深度搜索主模块
- `o_agent/base_agent.py` - Agent 基础实现
- `tools/search/websearch.py` - 网络搜索工具
- `tools/scan/scan_page.py` - 页面扫描工具
- `o_agent/prompt/thought.md` - 思考 Prompt 模板
- `o_agent/prompt/action.md` - 行动 Prompt 模板
- `o_agent/prompt/reflex.md` - 反思 Prompt 模板

## 🎯 最佳实践

1. **查询优化：**
   - 使用具体、明确的关键词
   - 避免过于宽泛的查询
   - 结合领域术语

2. **结果处理：**
   - 验证返回的链接有效性
   - 去重处理
   - 按相关性排序

3. **错误处理：**
   - 实现重试机制
   - 记录详细日志
   - 提供友好的错误提示

4. **监控和调试：**
   - 查看 Agent 的思考过程
   - 监控工具调用次数
   - 分析搜索效果

