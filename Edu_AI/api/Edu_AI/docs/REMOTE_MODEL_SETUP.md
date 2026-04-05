# 远程服务器模型集成指南

本指南介绍如何将部署在远程服务器上的模型集成到项目中。

## 📋 目录

- [方案概述](#方案概述)
- [方案一：远程Ollama服务器](#方案一远程ollama服务器)
- [方案二：OpenAI兼容API服务器](#方案二openai兼容api服务器)
- [方案三：其他API服务](#方案三其他api服务)
- [配置说明](#配置说明)
- [使用示例](#使用示例)
- [故障排查](#故障排查)

## 🎯 方案概述

项目支持多种模型接入方式：

1. **Ollama（本地/远程）** - 支持本地和远程Ollama服务器
2. **OpenAI兼容API** - 支持OpenAI及兼容OpenAI API的服务（如vLLM、TGI等）
3. **通义千问** - 阿里云通义千问API
4. **智谱AI** - 智谱AI API

## 🔧 方案一：远程Ollama服务器

如果您的服务器上运行的是Ollama服务，这是最简单的集成方式。

### 服务器端配置

1. **确保Ollama服务可访问**

在服务器上启动Ollama（如果还没启动）：
```bash
# 如果使用Docker
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# 或直接运行Ollama服务
ollama serve
```

2. **配置防火墙（如果需要）**

确保服务器防火墙允许访问11434端口：
```bash
# Ubuntu/Debian
sudo ufw allow 11434/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=11434/tcp --permanent
sudo firewall-cmd --reload
```

3. **测试服务**

在服务器上测试Ollama是否可访问：
```bash
curl http://localhost:11434/api/tags
```

### 客户端配置

#### 方式1：环境变量配置（推荐）

创建或编辑 `.env` 文件（在 `api/Edu_AI/` 目录下）：

```env
# 远程Ollama服务器地址
OLLAMA_BASE_URL=http://your-server-ip:11434

# 模型名称
LLM_MODEL=qwen:7b
EMBEDDING_MODEL=nomic-embed-text

# 默认模型类型
DEFAULT_MODEL_TYPE=ollama
DEFAULT_EMBEDDING_TYPE=ollama
```

**替换说明：**
- `your-server-ip`: 替换为您的服务器IP地址或域名
- 如果使用HTTPS，使用 `https://your-server-ip:11434`

#### 方式2：直接修改配置

编辑 `core/config.py`：

```python
OLLAMA_BASE_URL = "http://your-server-ip:11434"
LLM_MODEL = "qwen:7b"
EMBEDDING_MODEL = "nomic-embed-text"
```

#### 方式3：API请求时指定

在API请求中指定服务器地址：

```json
{
  "question": "你好",
  "model_type": "ollama",
  "api_base": "http://your-server-ip:11434",
  "model_name": "qwen:7b"
}
```

### 验证连接

启动API服务后，测试连接：

```bash
# 健康检查
curl http://localhost:8000/health

# 测试对话（需要先启动API服务）
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "你好",
    "model_type": "ollama",
    "api_base": "http://your-server-ip:11434"
  }'
```

## 🌐 方案二：OpenAI兼容API服务器

如果您的服务器运行的是OpenAI兼容的API服务（如vLLM、text-generation-inference等），可以使用OpenAI兼容模式。

### 服务器端配置

确保服务器上的API服务正常运行，并暴露OpenAI兼容的端点（通常是 `/v1/chat/completions`）。

### 客户端配置

#### 方式1：环境变量配置

```env
# 远程API服务器地址
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1

# API密钥（如果需要）
REMOTE_MODEL_API_KEY=your-api-key

# 默认模型类型
DEFAULT_MODEL_TYPE=openai
LLM_MODEL=your-model-name
```

#### 方式2：API请求时指定

```json
{
  "question": "你好",
  "model_type": "openai",
  "api_base": "http://your-server-ip:8000/v1",
  "model_name": "your-model-name",
  "api_key": "your-api-key"
}
```

## 🔌 方案三：其他API服务

### 通义千问

```env
DEFAULT_MODEL_TYPE=tongyi
DASHSCOPE_API_KEY=your-api-key
```

### 智谱AI

```env
DEFAULT_MODEL_TYPE=zhipu
ZHIPU_API_KEY=your-api-key
```

## ⚙️ 配置说明

### 环境变量配置

在 `api/Edu_AI/` 目录下创建 `.env` 文件：

```env
# ============ Ollama配置 ============
# Ollama服务地址（本地或远程）
OLLAMA_BASE_URL=http://localhost:11434
# 或远程服务器
# OLLAMA_BASE_URL=http://your-server-ip:11434

# 模型名称
LLM_MODEL=qwen:7b
EMBEDDING_MODEL=nomic-embed-text

# ============ 默认模型类型 ============
# 可选值: ollama, openai, tongyi, zhipu
DEFAULT_MODEL_TYPE=ollama
DEFAULT_EMBEDDING_TYPE=ollama

# ============ OpenAI兼容API配置 ============
# 远程API服务器地址（OpenAI兼容）
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1
REMOTE_MODEL_API_KEY=your-api-key

# ============ 其他API密钥 ============
OPENAI_API_KEY=your-openai-key
DASHSCOPE_API_KEY=your-tongyi-key
ZHIPU_API_KEY=your-zhipu-key
```

### 配置文件优先级

1. API请求参数（最高优先级）
2. 环境变量（`.env` 文件）
3. `config.py` 默认值（最低优先级）

## 💡 使用示例

### 示例1：使用远程Ollama服务器

**环境变量配置：**
```env
OLLAMA_BASE_URL=http://192.168.1.100:11434
LLM_MODEL=qwen:7b
DEFAULT_MODEL_TYPE=ollama
```

**API请求：**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是数据结构？",
    "use_rag": true
  }'
```

### 示例2：使用OpenAI兼容API

**API请求：**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是数据结构？",
    "model_type": "openai",
    "api_base": "http://your-server:8000/v1",
    "model_name": "your-model",
    "api_key": "your-key"
  }'
```

### 示例3：前端调用

在 `src/services/chat.ts` 中：

```typescript
const request: ChatRequest = {
  question: "什么是数据结构？",
  model_type: "ollama",
  api_base: "http://your-server-ip:11434",
  model_name: "qwen:7b",
  use_rag: true
};
```

## 🔍 故障排查

### 问题1：无法连接到远程服务器

**检查项：**
1. 服务器IP地址和端口是否正确
2. 防火墙是否允许访问
3. 服务器Ollama服务是否运行
4. 网络是否可达

**测试方法：**
```bash
# 测试网络连接
ping your-server-ip

# 测试端口是否开放
telnet your-server-ip 11434
# 或
curl http://your-server-ip:11434/api/tags
```

### 问题2：连接超时

**可能原因：**
- 网络延迟高
- 防火墙阻止
- 服务器负载高

**解决方案：**
1. 检查网络连接质量
2. 增加超时时间（在代码中配置）
3. 使用代理或VPN

### 问题3：模型不存在

**错误信息：** `model not found`

**解决方案：**
1. 在服务器上确认模型已下载：
   ```bash
   ollama list
   ```
2. 如果未下载，在服务器上下载：
   ```bash
   ollama pull qwen:7b
   ```

### 问题4：权限问题

**错误信息：** `connection refused` 或 `403 Forbidden`

**解决方案：**
1. 检查Ollama服务是否配置了访问控制
2. 如果需要认证，配置相应的认证信息
3. 检查服务器防火墙规则

## 📝 最佳实践

1. **使用环境变量**：推荐使用 `.env` 文件管理配置，不要将敏感信息提交到代码仓库

2. **网络安全**：
   - 生产环境建议使用HTTPS
   - 配置防火墙白名单
   - 使用VPN或内网访问

3. **负载均衡**：
   - 如果有多个服务器，可以使用负载均衡器
   - 配置多个Ollama实例

4. **监控**：
   - 监控服务器资源使用情况
   - 监控API响应时间
   - 设置告警

5. **备份**：
   - 定期备份模型和配置
   - 保留多个服务器实例作为备份

## 🔗 相关文档

- [使用指南](../docs/USAGE.md)
- [API文档](README_API.md)
- [项目结构](../STRUCTURE.md)

