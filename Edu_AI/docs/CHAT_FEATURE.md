# 对话功能使用说明

## 功能概述

前端已经实现了完整的对话功能，可以与后端API进行交互，支持：
- ✅ 实时对话交互
- ✅ 对话历史管理
- ✅ 知识库检索（RAG）
- ✅ 多模型支持（OpenAI、通义千问、智谱AI）
- ✅ 检索结果展示

## 启动步骤

### 1. 启动后端API服务

在 `api/Edu_AI` 目录下运行：

**Windows:**
```bash
start_api.bat
```

**Linux/Mac:**
```bash
bash start_api.sh
```

或者手动启动：
```bash
cd api/Edu_AI
uvicorn chat_api:app --host 0.0.0.0 --port 8000 --reload
```

后端API默认运行在 `http://localhost:8000`

### 2. 配置前端API地址（可选）

如果需要修改后端API地址，可以创建 `.env` 文件：

```env
VITE_API_BASE_URL=http://localhost:8000
```

如果不配置，默认使用 `http://localhost:8000`

### 3. 启动前端

在项目根目录运行：
```bash
npm run dev
```

前端默认运行在 `http://localhost:5173`

## 使用说明

### 基本对话

1. 打开前端页面，进入"智能问答"页面
2. 在输入框中输入问题
3. 点击"发送"按钮或按 `Enter` 键发送
4. AI助手会基于知识库检索并生成回答

### 对话管理

- **新建对话**: 点击左侧"新建对话"按钮
- **切换对话**: 点击左侧历史对话列表中的对话项
- **查看检索结果**: 右侧面板会显示知识库检索到的相关文档片段

### 模型配置

- **模型类型**: 可以选择 OpenAI、通义千问、智谱AI
- **RAG开关**: 可以开启/关闭知识库检索增强功能
  - 开启：使用RAG检索增强，回答更准确
  - 关闭：直接使用大模型回答，速度更快

### 快捷键

- `Enter`: 发送消息
- `Ctrl + Enter`: 换行

## API接口说明

后端提供了以下接口：

- `POST /chat` - 发送聊天消息
- `GET /conversations` - 获取所有对话列表
- `GET /conversations/{conversation_id}` - 获取指定对话历史
- `DELETE /conversations/{conversation_id}` - 删除对话
- `GET /health` - 健康检查

## 注意事项

1. **确保后端服务运行**: 前端需要后端API服务正常运行
2. **知识库准备**: 如果使用RAG功能，需要先构建知识库（运行 `build_knowledge_base.py`）
3. **API密钥**: 如果使用外部模型（OpenAI、通义千问、智谱AI），需要在请求中提供API密钥，或设置环境变量：
   - `OPENAI_API_KEY`
   - `DASHSCOPE_API_KEY` (通义千问)
   - `ZHIPU_API_KEY` (智谱AI)

## 故障排查

### 前端无法连接后端

1. 检查后端服务是否正常运行（访问 `http://localhost:8000/health`）
2. 检查 `.env` 文件中的 `VITE_API_BASE_URL` 配置是否正确
3. 检查浏览器控制台是否有CORS错误

### 对话无响应

1. 检查后端日志是否有错误信息
2. 确认知识库是否已构建（如果使用RAG）
3. 检查网络连接和API密钥配置

### 检索结果为空

1. 确认已开启RAG功能（右侧RAG开关）
2. 确认知识库已构建并包含相关文档
3. 检查 `documents_cache.json` 文件是否存在

