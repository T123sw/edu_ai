# Edu-AI 使用说明

本文档整合了项目的使用说明和快速入门指南。

## 📋 目录

- [快速开始](#快速开始)
- [功能说明](#功能说明)
- [API使用](#api使用)
- [故障排查](#故障排查)

## 🚀 快速开始

### 环境要求

- **前端**: Node.js 18+, npm/yarn/pnpm
- **后端**: Python 3.12+
- **其他**: Ollama (用于本地模型)

### 安装步骤

#### 1. 克隆项目

```bash
git clone <repository-url>
cd Edu_AI
```

#### 2. 安装前端依赖

```bash
npm install
# 或
pnpm install
# 或
yarn install
```

#### 3. 安装后端依赖

```bash
cd api/Edu_AI
pip install -r requirements.txt
```

#### 4. 配置环境变量

复制并编辑环境变量文件：

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

编辑 `.env` 文件，配置API地址等。

#### 5. 准备知识库（可选）

如果使用RAG功能，需要先构建知识库：

```bash
cd api/Edu_AI
python build_knowledge_base.py --build
```

### 启动项目

#### 启动后端

```bash
cd api/Edu_AI

# Windows
start_api.bat

# Linux/Mac
bash start_api.sh
```

后端将在 http://localhost:8000 启动

#### 启动前端

```bash
npm run dev
```

前端将在 http://localhost:5173 启动

## 📖 功能说明

### 1. 智能问答

- **位置**: 前端 → 智能问答页面
- **功能**:
  - 实时对话交互
  - 知识库检索增强（RAG）
  - 对话历史管理
  - 多模型支持（OpenAI、通义千问、智谱AI）
  - 检索结果显示

- **使用方法**:
  1. 输入问题
  2. 选择模型类型（如需要）
  3. 开启/关闭RAG检索
  4. 发送消息
  5. 查看回答和检索结果

### 2. 文档管理

- **位置**: 前端 → 文档管理页面
- **功能**: PDF文档上传与管理

### 3. 教师工具

- **位置**: 前端 → 教师工具页面
- **功能**: 教案生成、题目生成等

### 4. 数据采集

- **位置**: 前端 → 数据采集页面
- **功能**: 爬取-处理-微调流程配置与监控

## 🔌 API使用

### 基础URL

```
http://localhost:8000
```

### 主要接口

#### 1. 健康检查

```http
GET /health
```

**响应示例:**
```json
{
  "status": "ok",
  "message": "服务运行正常",
  "knowledge_base_ready": true
}
```

#### 2. 发送聊天消息

```http
POST /chat
Content-Type: application/json

{
  "question": "什么是数据结构？",
  "model_type": "openai",
  "use_rag": true,
  "temperature": 0.1,
  "max_tokens": 1000
}
```

**响应示例:**
```json
{
  "answer": "数据结构是...",
  "conversation_id": "conv_1234567890",
  "sources": [
    {
      "index": 1,
      "source": "数据结构基础.pdf",
      "page": 3,
      "content": "..."
    }
  ]
}
```

#### 3. 获取对话列表

```http
GET /conversations
```

#### 4. 获取对话历史

```http
GET /conversations/{conversation_id}
```

#### 5. 删除对话

```http
DELETE /conversations/{conversation_id}
```

### API文档

启动后端服务后，访问 http://localhost:8000/docs 查看完整的交互式API文档。

## ⚠️ 故障排查

### 端口冲突

**问题**: `WinError 10013` 或端口被占用

**解决**:
1. 使用 `stop_api.bat` 停止已有服务
2. 或修改端口配置
3. 或手动停止占用进程

### 前端无法连接后端

**检查项**:
1. 后端服务是否运行（访问 http://localhost:8000/health）
2. `.env` 文件中的 `VITE_API_BASE_URL` 是否正确
3. 浏览器控制台是否有CORS错误
4. 防火墙是否阻止连接

### RAG检索无结果

**检查项**:
1. 知识库是否已构建
2. RAG功能是否已开启
3. `documents_cache.json` 文件是否存在
4. 向量数据库是否正常

### 模型调用失败

**检查项**:
1. API密钥是否正确配置
2. 模型服务是否可访问
3. 网络连接是否正常
4. 查看后端日志错误信息

### 依赖安装失败

**Python依赖**:
```bash
# 升级pip
python -m pip install --upgrade pip

# 使用国内镜像（如果网络慢）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**前端依赖**:
```bash
# 清除缓存重新安装
rm -rf node_modules package-lock.json
npm install
```

## 📚 更多文档

- [项目结构说明](./PROJECT_STRUCTURE.md)
- [API详细文档](../api/Edu_AI/README_API.md)
- [后端README](../api/Edu_AI/README_API.md)

## 💡 提示

- 首次使用建议先运行健康检查接口确认服务正常
- 开发环境建议开启 `--reload` 模式（已默认开启）
- 生产环境请关闭调试信息并配置CORS白名单
- 定期备份知识库和配置文件

