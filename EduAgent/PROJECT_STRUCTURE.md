# EduAgent 项目结构分析

## 📁 项目概述

**EduAgent** 是一个基于 FastAPI 的教育智能代理系统，主要用于：
- 文档处理（PDF、PPT、文本文件）
- 深度搜索（DeepSearch）
- 文档摘要生成
- 智能问答和对话

## 🏗️ 项目架构

```
EduAgent/
├── main.py                 # FastAPI 主应用入口
├── config.toml            # 配置文件（API密钥等）
├── define.py              # 路径和配置定义
├── chunks.py              # 文档分块处理
├── deepsearch.py          # 深度搜索功能
├── chunk_type.py          # 分块类型定义
├── quiz.py                # 测验生成（待实现）
├── api.JSON               # API 文档/定义
│
├── o_agent/               # 核心 Agent 模块
│   ├── base_agent.py      # Agent 基础类（LangGraph）
│   ├── types.py           # 状态和类型定义
│   ├── token_counter.py   # Token 计数
│   ├── llm/               # LLM 封装
│   │   └── llms.py        # LLM 实例管理
│   └── prompt/            # Prompt 模板
│       ├── abstract.md    # 摘要提示
│       ├── action.md      # 行动提示
│       ├── reflex.md      # 反思提示
│       └── thought.md     # 思考提示
│
├── tools/                  # 工具模块
│   ├── search/            # 搜索工具
│   │   └── websearch.py   # 网络搜索（Google/SerpAPI）
│   ├── scan/              # 页面扫描工具
│   │   └── scan_page.py   # 网页内容提取（Playwright）
│   ├── paper/             # 论文搜索
│   │   └── search.py
│   ├── repl/              # REPL 工具
│   │   └── analysis.py
│   ├── canvas/            # 画布编辑
│   │   ├── edit.py
│   │   └── types.py
│   ├── subagent/          # 子代理
│   │   └── sub.py
│   ├── special_tools/     # 特殊工具
│   │   └── conversation.py
│   └── source/            # 资源文件
│       └── chromedriver.exe
│
├── files/                  # 文件存储
│   ├── ppt/               # PPT 文件
│   ├── pdf/               # PDF 文件
│   └── line/              # 文本文件
│
├── logs/                   # 日志文件
│   ├── large_model_deepsearch.log
│   └── ppt_summary.log
│
└── test/                   # 测试文件
    ├── test01.py
    └── test02.py
```

## 🔧 核心模块详解

### 1. **main.py** - FastAPI 应用

**主要功能：**
- 提供 RESTful API 接口
- 文件上传和管理
- 文档摘要生成
- 深度搜索服务

**API 端点：**
- `POST /agent/deepsearch` - 深度搜索
- `POST /agent/summary` - 文档摘要
- `POST /file/upload` - 文件上传
- `GET /file/get_file_list` - 获取文件列表
- `GET /file/get_file/{file_name}` - 下载文件

**技术栈：**
- FastAPI
- Uvicorn
- CORS 中间件

### 2. **chunks.py** - 文档分块处理

**功能：**
- 将文档（PDF、PPT、文本）分割成可处理的块（Chunk）
- 支持三种分块类型：
  - `pdf_page` - PDF 按页分块
  - `ppt_slide` - PPT 按幻灯片分块
  - `text_lines` - 文本按行分块

**关键函数：**
- `build_chunks(file_name)` - 构建文档块列表
- `pdf_chunks_by_page()` - PDF 分页处理
- `ppt_chunks_by_slide()` - PPT 分幻灯片处理
- `doc_chunks_by_lines()` - 文本分行处理
- `summarize_pdf()` - PDF 摘要生成
- `summarize_ppt()` - PPT 摘要生成
- `summarize_doc()` - 文档摘要生成

**依赖：**
- PyMuPDF (fitz) - PDF 处理
- python-pptx - PPT 处理

### 3. **deepsearch.py** - 深度搜索

**功能：**
- 使用大语言模型进行深度搜索
- 结合网络搜索和页面扫描
- 返回相关链接和内容

**关键函数：**
- `deepsearch_large_llm(query)` - 执行深度搜索
- `parse_json_from_text()` - 从文本中解析 JSON

**工作流程：**
1. 接收查询
2. 使用 Agent 进行思考和分析
3. 调用搜索工具获取结果
4. 扫描相关页面提取内容
5. 返回结构化结果

### 4. **o_agent/** - Agent 核心模块

#### **base_agent.py**
- 基于 LangGraph 的 Agent 实现
- 使用状态机管理 Agent 工作流
- 支持工具调用和思考循环

**关键组件：**
- `get_agent()` - 获取 Agent 实例
- `get_template_by_name()` - 获取 Prompt 模板
- `chat()` - 用户交互工具

**状态管理：**
- `State` - Agent 状态（消息、步骤、响应等）
- `Thought` - 思考过程

#### **llm/llms.py**
- LLM 实例管理
- 支持多种 LLM 类型
- `get_llm_by_type()` - 获取指定类型的 LLM

#### **prompt/**
- 使用 Jinja2 模板引擎
- 包含不同场景的 Prompt 模板

### 5. **tools/** - 工具模块

#### **search/websearch.py**
- Google 搜索集成（通过 SerpAPI）
- 返回搜索结果（URL + 标题）

#### **scan/scan_page.py**
- 使用 Playwright 扫描网页
- 提取页面主要内容
- 支持 PDF 内容检测
- 使用 Readability 算法提取正文

**关键特性：**
- 拦截图片/字体/媒体资源（提高速度）
- 超时控制（默认 45 秒）
- 失败时返回 None 并记录日志

#### **其他工具：**
- `paper/search.py` - 论文搜索
- `repl/analysis.py` - REPL 分析
- `canvas/edit.py` - 画布编辑
- `subagent/sub.py` - 子代理

### 6. **chunk_type.py** - 类型定义

**核心类型：**
- `ChunkKind` - 分块类型（pdf_page, ppt_slide, text_lines）
- `ChunkMeta` - 分块元数据
- `Chunk` - 分块数据结构

**Chunk 结构：**
```python
{
    "doc_id": str,      # 文档 ID
    "chunk_id": str,    # 块 ID
    "source_path": str, # 源文件路径
    "kind": ChunkKind,  # 块类型
    "index": int,       # 索引（页码/幻灯片号）
    "text": str,        # 文本内容
    "meta": ChunkMeta   # 元数据
}
```

### 7. **define.py** - 配置定义

**路径定义：**
- `PPT_DIR` - PPT 文件目录
- `PDF_DIR` - PDF 文件目录
- `DOC_DIR` - 文档文件目录
- `CONFIG_PATH` - 配置文件路径

**函数：**
- `get_config_dict()` - 读取配置文件

## 🔄 工作流程

### 文档处理流程
1. **上传文件** → `POST /file/upload`
2. **构建分块** → `build_chunks(file_name)`
3. **生成摘要** → `POST /agent/summary`
4. **返回结果** → JSON 响应

### 深度搜索流程
1. **接收查询** → `POST /agent/deepsearch`
2. **Agent 思考** → 使用 LangGraph Agent
3. **工具调用** → 搜索工具 + 页面扫描
4. **结果整理** → 返回链接列表

## 🛠️ 技术栈

### 核心框架
- **FastAPI** - Web 框架
- **LangGraph** - Agent 工作流
- **LangChain** - LLM 集成

### 文档处理
- **PyMuPDF (fitz)** - PDF 处理
- **python-pptx** - PPT 处理

### 网络工具
- **Playwright** - 浏览器自动化
- **BeautifulSoup** - HTML 解析
- **SerpAPI** - 搜索引擎 API

### 其他
- **Jinja2** - 模板引擎
- **Pydantic** - 数据验证
- **Uvicorn** - ASGI 服务器

## 📝 配置说明

### config.toml
```toml
[api_key]
deepseek_api_key=''  # DeepSeek API 密钥
```

## 🚀 运行方式

```bash
# 启动服务
python main.py

# 服务运行在 http://127.0.0.1:8848
```

## 📊 数据流

```
用户查询
  ↓
FastAPI 接口
  ↓
Agent (LangGraph)
  ↓
工具调用 (搜索/扫描)
  ↓
LLM 处理
  ↓
返回结果
```

## 🔍 关键设计模式

1. **Agent 模式** - 使用 LangGraph 实现智能代理
2. **工具模式** - 将功能封装为可调用工具
3. **分块模式** - 将大文档分割为可处理的小块
4. **模板模式** - 使用 Jinja2 管理 Prompt

## ⚠️ 待完善功能

- `quiz.py` - 测验生成功能（目前为空）
- 错误处理和日志记录需要完善
- 配置文件管理可以更灵活

## 🔗 与自动化爬虫的集成点

EduAgent 的深度搜索功能可以与自动化爬虫模块集成：
- 使用爬虫获取的 PDF 链接作为搜索结果
- 将爬取的文档直接用于摘要生成
- 结合爬虫的 PDF 下载功能完善文档处理流程

