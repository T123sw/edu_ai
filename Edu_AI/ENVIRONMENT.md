# Edu-AI 环境配置文档

本文档说明如何通过 Conda 创建隔离环境，并安装前后端所需依赖。

---

## 📋 目录

- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [详细步骤](#详细步骤)
- [环境验证](#环境验证)
- [常见问题](#常见问题)

---

## 🔧 环境要求

### 系统要求
- **操作系统**: Windows / Linux / macOS
- **Conda**: Miniconda 或 Anaconda (推荐 Miniconda)
- **Python**: 3.12+
- **Node.js**: 20+ (通过 conda 安装)

### 硬件建议
- **内存**: 至少 8GB RAM
- **存储**: 至少 10GB 可用空间（包含依赖和向量数据库）
- **GPU**: 可选，用于本地模型推理（本项目主要使用远程模型）

---

## 🚀 快速开始

### 1. 创建 Conda 环境

```bash
# 进入项目根目录
cd Edu_AI

# 使用 environment.yml 创建环境
conda env create -f environment.yml

# 激活环境
conda activate edu-ai
```

### 2. 安装前端依赖

```bash
# 确保在 Edu_AI 目录下
npm install
```

### 3. 配置环境变量

创建 `.env` 文件（如果不存在）：

```bash
# 后端 API 地址（前端访问）
VITE_API_BASE_URL=http://localhost:8001

# 远程模型配置（后端使用）
REMOTE_MODEL_API_BASE=http://localhost:11434/v1
REMOTE_MODEL_API_KEY=dummy-key
LLM_MODEL=qwen3-8b
DEFAULT_EMBEDDING_TYPE=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_MODEL_TYPE=openai
```

### 4. 启动服务

#### 启动后端（终端 1）

```bash
conda activate edu-ai
cd api
uvicorn Edu_AI.app.main:app --host 0.0.0.0 --port 8001 --reload
```

#### 启动前端（终端 2）

```bash
conda activate edu-ai
cd Edu_AI  # 前端根目录
npm run dev
```

访问 `http://localhost:5173` (或 Vite 分配的端口)

---

## 📝 详细步骤

### 步骤 1: 安装 Conda

如果尚未安装 Conda：

**Windows:**
1. 下载 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 [Anaconda](https://www.anaconda.com/products/distribution)
2. 运行安装程序，按提示完成安装
3. 打开 "Anaconda Prompt" 或 PowerShell

**Linux/macOS:**
```bash
# 下载并安装 Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 或 macOS
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
bash Miniconda3-latest-MacOSX-x86_64.sh
```

### 步骤 2: 创建 Conda 环境

```bash
# 进入项目目录
cd /path/to/Edu_AI_1/Edu_AI

# 创建环境（自动安装 Python 和基础依赖）
conda env create -f environment.yml

# 激活环境
conda activate edu-ai

# 验证 Python 版本
python --version  # 应该显示 Python 3.12.x
```

### 步骤 3: 安装后端 Python 依赖

环境创建后，Python 依赖已通过 `pip` 安装在 `environment.yml` 中定义。

如需手动安装或更新：

```bash
conda activate edu-ai
cd api/Edu_AI

# 安装完整依赖
pip install -r requirements_api.txt

# 或仅安装核心依赖
pip install -r requirements.txt
```

### 步骤 4: 安装前端 Node.js 依赖

```bash
conda activate edu-ai  # Node.js 已通过 conda 安装
cd /path/to/Edu_AI_1/Edu_AI  # 前端根目录

# 安装依赖
npm install

# 验证安装
npm list --depth=0
```

### 步骤 5: 配置环境变量

#### 前端环境变量 (`Edu_AI/.env`)

```env
# API 基础地址
VITE_API_BASE_URL=http://localhost:8001
```

#### 后端环境变量 (`Edu_AI/api/Edu_AI/.env` 或通过系统环境变量)

```env
# 远程模型服务
REMOTE_MODEL_API_BASE=http://localhost:11434/v1
REMOTE_MODEL_API_KEY=dummy-key
LLM_MODEL=qwen3-8b

# 向量数据库
DEFAULT_EMBEDDING_TYPE=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_MODEL_TYPE=openai
```

---

## ✅ 环境验证

### 验证 Python 环境

```bash
conda activate edu-ai

# 检查 Python 版本
python --version

# 检查关键包
python -c "import fastapi; print(fastapi.__version__)"
python -c "import chromadb; print(chromadb.__version__)"
python -c "import uvicorn; print('uvicorn OK')"
```

### 验证 Node.js 环境

```bash
conda activate edu-ai

# 检查 Node.js 和 npm 版本
node --version
npm --version

# 检查前端依赖
cd Edu_AI
npm list react vite typescript
```

### 验证后端服务

```bash
conda activate edu-ai
cd api
uvicorn Edu_AI.app.main:app --host 0.0.0.0 --port 8001

# 在浏览器访问
# http://localhost:8001/docs  (Swagger UI)
# http://localhost:8001/health (健康检查，如果实现了)
```

### 验证前端服务

```bash
conda activate edu-ai
cd Edu_AI
npm run dev

# 访问 http://localhost:5173 (或 Vite 显示的端口)
```

---

## 🔍 常见问题

### Q1: Conda 环境创建失败

**问题**: `Solving environment: failed`

**解决**:
```bash
# 更新 conda
conda update conda

# 使用 conda-forge 频道
conda config --add channels conda-forge
conda config --set channel_priority strict

# 重新创建
conda env create -f environment.yml
```

### Q2: pip 安装依赖时版本冲突

**问题**: `ERROR: Cannot install package==x.x.x`

**解决**:
```bash
# 在 environment.yml 中使用 >= 而不是 ==，允许版本范围
# 或手动升级 pip
pip install --upgrade pip

# 然后重新安装
pip install -r requirements_api.txt
```

### Q3: Node.js 版本不匹配

**问题**: `The engine "node" is incompatible with this module`

**解决**:
```bash
# 检查 Node.js 版本
node --version

# 如果需要更新（通过 conda）
conda install nodejs=20 -c conda-forge

# 或使用 nvm（如果已安装）
nvm install 20
nvm use 20
```

### Q4: 端口被占用

**问题**: `Address already in use` 或 `Port 8001 is already in use`

**解决**:
```bash
# Windows
netstat -ano | findstr :8001
taskkill /PID <PID> /F

# Linux/macOS
lsof -ti:8001 | xargs kill -9

# 或修改 .env 中的端口
VITE_API_BASE_URL=http://localhost:8002
```

### Q5: 环境激活后命令找不到

**问题**: `command not found: python` 或 `command not found: npm`

**解决**:
```bash
# 确保环境已激活（提示符应显示 (edu-ai)）
conda activate edu-ai

# 验证路径
which python   # Linux/macOS
where python   # Windows

# 如果路径不对，重新初始化 conda
conda init bash  # Linux/macOS
conda init powershell  # Windows PowerShell
conda init cmd.exe  # Windows CMD

# 重启终端后再激活
```

---

## 📦 依赖清单

### Python 后端依赖

核心框架:
- `fastapi>=0.104.0` - Web 框架
- `uvicorn[standard]>=0.24.0` - ASGI 服务器
- `pydantic>=2.0.0` - 数据验证

认证与安全:
- `pyjwt>=2.8.0` - JWT 令牌
- `python-jose[cryptography]>=3.3.0` - JOSE 实现
- `passlib[bcrypt]>=1.7.4` - 密码哈希

向量数据库与 RAG:
- `chromadb>=0.4.0` - 向量数据库
- `langchain-core>=0.1.0` - LangChain 核心
- `langchain-community>=0.0.20` - LangChain 社区集成
- `langchain-text-splitters>=0.0.1` - 文本分割

文档处理:
- MinerU Cloud - PDF 解析

工具库:
- `requests>=2.31.0` - HTTP 客户端
- `python-dotenv>=1.0.0` - 环境变量管理
- `python-multipart>=0.0.6` - 文件上传支持

### Node.js 前端依赖

核心框架:
- `react@^18.3.1` - UI 框架
- `react-dom@^18.3.1` - React DOM
- `react-router-dom@^6.28.0` - 路由

UI 组件库:
- `antd@^5.21.0` - Ant Design 组件库

Markdown 渲染:
- `react-markdown@^10.1.0` - Markdown 渲染
- `remark-gfm@^4.0.1` - GitHub Flavored Markdown
- `remark-math@^6.0.0` - 数学公式支持
- `rehype-katex@^7.0.1` - KaTeX 渲染
- `react-katex@^3.1.0` - React KaTeX 组件
- `katex@^0.16.27` - KaTeX 核心库

代码高亮:
- `react-syntax-highlighter@^16.1.0` - 代码语法高亮

构建工具:
- `vite@^6.0.0` - 构建工具
- `typescript@^5.6.3` - TypeScript 编译器
- `@vitejs/plugin-react-swc@^3.7.1` - Vite React 插件

---

## 🗂️ 项目结构

```
Edu_AI/
├── environment.yml          # Conda 环境配置文件（本文档对应的文件）
├── ENVIRONMENT.md          # 本文档
├── .env                    # 前端环境变量
├── package.json            # 前端依赖清单
├── vite.config.ts          # Vite 配置
│
├── api/                    # 后端目录
│   └── Edu_AI/
│       ├── requirements_api.txt  # 完整后端依赖
│       ├── requirements.txt      # 精简后端依赖
│       ├── app/                  # FastAPI 应用
│       ├── core/                 # 核心模块
│       └── new_rag/              # RAG 系统
│
└── src/                    # 前端源码
    ├── pages/              # 页面组件
    ├── services/           # API 服务
    └── components/         # 通用组件
```

---

## 🔄 更新环境

### 更新 Python 依赖

```bash
conda activate edu-ai
cd api/Edu_AI
pip install --upgrade -r requirements_api.txt
```

### 更新 Node.js 依赖

```bash
conda activate edu-ai
cd Edu_AI
npm update
```

### 更新 Conda 环境

```bash
# 如果修改了 environment.yml
conda env update -f environment.yml --prune
```

---

## 🗑️ 删除环境

如果不再需要此环境：

```bash
# 停用环境（如果当前已激活）
conda deactivate

# 删除环境
conda env remove -n edu-ai
```

---

## 📚 参考资源

- [Conda 官方文档](https://docs.conda.io/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Vite 文档](https://vitejs.dev/)
- [React 文档](https://react.dev/)

---

**最后更新**: 2025-12-28

