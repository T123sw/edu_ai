# 远程服务器模型集成完整指南

## 📚 快速开始

如果您的模型在远程服务器上，有两种主要集成方式：

1. **Ollama远程服务器**（推荐）- 最简单的方式
2. **OpenAI兼容API** - 支持vLLM、TGI等框架

## 🚀 方案一：远程Ollama服务器（推荐）

### 为什么选择Ollama？

- ✅ **简单易用**：只需修改一个URL配置
- ✅ **兼容性好**：支持所有Ollama模型
- ✅ **无需修改代码**：项目已完全支持
- ✅ **统一管理**：LLM和嵌入模型都可用Ollama

### 配置步骤

#### 1. 服务器端准备

确保服务器上已安装并运行Ollama：

```bash
# 在服务器上检查Ollama是否运行
curl http://localhost:11434/api/tags

# 如果没有运行，启动Ollama
ollama serve
# 或使用Docker
docker run -d -p 11434:11434 ollama/ollama
```

#### 2. 下载所需模型

在服务器上下载项目需要的模型：

```bash
# LLM模型
ollama pull qwen:7b

# 嵌入模型
ollama pull nomic-embed-text
```

#### 3. 配置防火墙

确保服务器11434端口可访问：

```bash
# Ubuntu/Debian
sudo ufw allow 11434/tcp

# 测试从外部访问
curl http://your-server-ip:11434/api/tags
```

#### 4. 客户端配置

在项目 `api/Edu_AI/` 目录下创建 `.env` 文件：

```env
# 远程Ollama服务器地址（替换为您的服务器IP）
OLLAMA_BASE_URL=http://192.168.1.100:11434

# 模型名称（根据服务器上的模型调整）
LLM_MODEL=qwen:7b
EMBEDDING_MODEL=nomic-embed-text

# 使用Ollama作为默认模型
DEFAULT_MODEL_TYPE=ollama
DEFAULT_EMBEDDING_TYPE=ollama
```

#### 5. 启动并测试

```bash
# 启动API服务
cd api/Edu_AI
start_api.bat  # Windows
# 或
bash start_api.sh  # Linux/Mac

# 测试连接
curl http://localhost:8000/health

# 测试对话
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "你好"}'
```

## 🌐 方案二：OpenAI兼容API

如果服务器运行的是OpenAI兼容的API服务（如vLLM、text-generation-inference等）。

### 配置步骤

#### 1. 确认API端点

确保服务器API支持OpenAI兼容格式：
- 端点：`/v1/chat/completions`
- 格式：OpenAI API格式

#### 2. 配置项目

在 `.env` 文件中配置：

```env
# 使用OpenAI兼容模式
DEFAULT_MODEL_TYPE=openai

# 服务器API地址
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1

# API密钥（如果需要）
REMOTE_MODEL_API_KEY=your-api-key
```

#### 3. API调用

```json
{
  "question": "你好",
  "model_type": "openai",
  "api_base": "http://your-server-ip:8000/v1",
  "model_name": "your-model-name",
  "api_key": "your-key"
}
```

## 📋 配置方式对比

| 配置方式 | 优先级 | 适用场景 |
|---------|--------|---------|
| API请求参数 | 最高 | 临时测试、动态切换 |
| 环境变量(.env) | 中等 | 推荐，便于管理 |
| config.py默认值 | 最低 | 开发环境默认值 |

## 💡 使用示例

### 示例1：使用环境变量配置远程Ollama

`.env` 文件：
```env
OLLAMA_BASE_URL=http://192.168.1.100:11434
LLM_MODEL=qwen:7b
DEFAULT_MODEL_TYPE=ollama
```

API调用（无需指定model_type，自动使用配置）：
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是数据结构？"}'
```

### 示例2：API请求中指定服务器

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是数据结构？",
    "model_type": "ollama",
    "api_base": "http://192.168.1.100:11434",
    "model_name": "qwen:7b"
  }'
```

### 示例3：前端调用

```typescript
// src/services/chat.ts
const request: ChatRequest = {
  question: "什么是数据结构？",
  model_type: "ollama",
  api_base: "http://your-server-ip:11434",
  model_name: "qwen:7b",
  use_rag: true
};
```

## 🔍 常见问题

### Q1: 需要继续使用Ollama吗？

**A:** 
- ✅ **推荐使用**：如果服务器上运行Ollama，这是最简单的集成方式
- ✅ **无需改动代码**：项目已完全支持远程Ollama
- ✅ **统一管理**：LLM和嵌入模型都可用同一Ollama服务

### Q2: 服务器上没有Ollama怎么办？

**A:** 可以：
1. 在服务器上安装Ollama（推荐）
2. 使用OpenAI兼容API模式
3. 使用其他API服务（通义千问、智谱AI等）

### Q3: 如何确保安全性？

**A:** 
- 使用HTTPS（如果可能）
- 配置防火墙白名单
- 使用VPN或内网访问
- 不要在代码中硬编码敏感信息

### Q4: 性能如何优化？

**A:**
- 使用SSD存储模型
- 配置GPU加速（如果可用）
- 使用负载均衡（多服务器）
- 配置缓存机制

## 📖 详细文档

- [远程模型设置详细文档](../api/Edu_AI/docs/REMOTE_MODEL_SETUP.md)
- [API文档](../api/Edu_AI/README_API.md)
- [使用指南](./USAGE.md)

