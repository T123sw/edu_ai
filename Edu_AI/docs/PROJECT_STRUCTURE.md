# 项目目录结构说明

## 📁 整体结构

```
Edu_AI/
├── api/                      # 后端API服务
│   └── Edu_AI/              # 后端主要代码目录
│       ├── *.py             # Python源代码文件
│       ├── data/            # 数据目录
│       ├── vector_db/       # 向量数据库存储
│       └── ...
├── src/                      # 前端源代码
│   ├── components/          # React组件
│   ├── pages/               # 页面组件
│   ├── services/            # API服务
│   └── ...
├── public/                   # 静态资源
├── docs/                     # 项目文档
├── node_modules/            # 前端依赖（自动生成）
└── 配置文件...
```

## 📂 详细目录说明

### 前端目录 (`src/`)

```
src/
├── components/              # 通用组件
│   └── ProtectedRoute.tsx  # 受保护路由组件
├── context/                 # React Context
│   └── AuthContext.tsx     # 认证上下文
├── layout/                  # 布局组件
│   ├── MainLayout.tsx      # 主布局
│   └── MainLayout.css      # 布局样式
├── pages/                   # 页面组件
│   ├── LoginPage.tsx       # 登录页
│   ├── ChatPage.tsx        # 智能问答页
│   ├── DocsPage.tsx        # 文档管理页
│   ├── TeacherToolsPage.tsx # 教师工具页
│   └── DataPipelinePage.tsx # 数据采集页
├── routes/                  # 路由配置
│   └── AppRoutes.tsx       # 应用路由
├── services/                # API服务层
│   ├── auth.ts             # 认证服务
│   └── chat.ts             # 聊天服务
├── styles/                  # 全局样式
│   └── global.css          # 全局CSS
└── main.tsx                # 应用入口
```

### 后端目录 (`api/Edu_AI/`)

```
api/Edu_AI/
├── core/                    # 核心功能（建议创建）
│   ├── config.py           # 配置管理
│   └── dsa_qa_prompt.py    # 提示词模板
├── services/                # 业务服务（建议创建）
│   ├── rag_qa.py           # RAG问答服务
│   ├── hybrid_retriever.py # 混合检索器
│   └── smart_enhancer.py   # 智能文档增强
├── api/                     # API接口（建议创建）
│   └── chat_api.py         # 聊天API接口
├── scripts/                 # 脚本工具（建议创建）
│   ├── build_knowledge_base.py  # 知识库构建
│   └── knowledge_importer.py    # 知识库导入
├── data/                    # 数据目录
│   └── textbooks/          # PDF教材文件
├── vector_db/              # 向量数据库存储
├── enhanced_documents/     # 增强后的文档
├── scripts/                # 启动脚本
│   ├── start_api.bat       # Windows启动脚本
│   ├── start_api.sh        # Linux/Mac启动脚本
│   └── stop_api.bat        # Windows停止脚本
├── requirements.txt        # Python依赖列表
└── README_API.md           # API文档
```

## 📄 重要文件说明

### 配置文件

- `package.json` - 前端项目配置和依赖
- `tsconfig.json` - TypeScript配置
- `vite.config.ts` - Vite构建配置
- `requirements.txt` - Python依赖列表
- `.gitignore` - Git忽略文件配置
- `.env.example` - 环境变量示例（需手动创建）

### 文档文件

- `README.md` - 项目主文档
- `docs/PROJECT_STRUCTURE.md` - 项目结构说明（本文档）
- `docs/USAGE.md` - 使用说明
- `api/Edu_AI/README_API.md` - API接口文档

## 🗑️ 建议清理的文件/目录

以下文件/目录建议清理（备份后删除）：

1. **备份目录**
   - `api/Edu_AI copy/` - 重复的备份目录

2. **临时文件**
   - `api/Edu_AI/1.py` - 临时测试文件
   - `api/Edu_AI/text1.py` - 临时测试文件

3. **根目录重复数据**（如果与api/Edu_AI下重复）
   - `data/` - 如果与api/Edu_AI/data重复
   - `enhanced_documents/` - 如果与api/Edu_AI/enhanced_documents重复
   - `vector_db/` - 如果与api/Edu_AI/vector_db重复

## 📝 目录组织建议

### 建议的后端目录重组

```
api/Edu_AI/
├── app/                    # 应用主目录
│   ├── __init__.py
│   ├── main.py            # FastAPI应用入口（重命名chat_api.py）
│   ├── config.py          # 配置
│   └── dependencies.py    # 依赖注入
├── core/                   # 核心业务逻辑
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── qa_chain.py    # QA链（rag_qa.py拆分）
│   │   ├── retriever.py   # 检索器（hybrid_retriever.py）
│   │   └── enhancer.py    # 文档增强（smart_enhancer.py）
│   └── prompts/
│       └── dsa_qa.py      # 提示词（dsa_qa_prompt.py）
├── api/                    # API路由
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py        # 聊天路由
│   │   └── health.py      # 健康检查路由
│   └── models/
│       └── schemas.py     # Pydantic模型
├── scripts/                # 脚本工具
│   ├── build_kb.py        # 知识库构建
│   └── import_kb.py       # 知识库导入
├── data/                   # 数据目录
├── storage/                # 存储目录
│   ├── vector_db/         # 向量数据库
│   ├── enhanced_docs/     # 增强文档
│   └── cache/             # 缓存文件
├── tests/                  # 测试文件
├── requirements.txt        # 依赖列表
└── README.md              # 文档
```

**注意**: 以上重组是建议，当前结构可以保持，逐步优化。

## 🔧 环境变量配置

创建 `.env` 文件（参考 `.env.example`）：

```env
# 前端
VITE_API_BASE_URL=http://localhost:8000

# 后端（如果需要）
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=your_key_here
```

## 📦 依赖管理

### 前端依赖
```bash
npm install          # 安装依赖
npm run dev          # 开发模式
npm run build        # 构建生产版本
```

### 后端依赖
```bash
cd api/Edu_AI
pip install -r requirements.txt
```

## 🚀 启动顺序

1. 启动后端API服务
   ```bash
   cd api/Edu_AI
   start_api.bat  # Windows
   # 或
   bash start_api.sh  # Linux/Mac
   ```

2. 启动前端开发服务器
   ```bash
   npm run dev
   ```

3. 访问应用
   - 前端: http://localhost:5173
   - 后端API: http://localhost:8000
   - API文档: http://localhost:8000/docs

