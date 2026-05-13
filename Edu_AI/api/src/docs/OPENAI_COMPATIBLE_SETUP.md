# OpenAI兼容API集成配置指南

本指南介绍如何使用OpenAI兼容的方式集成远程服务器上的模型。

## 📋 前提条件

确保您的服务器API满足以下要求：

1. ✅ 支持OpenAI兼容的API格式
2. ✅ 提供 `/v1/chat/completions` 端点
3. ✅ 请求和响应格式符合OpenAI标准

支持的框架包括：
- vLLM
- text-generation-inference (TGI)
- OpenAI官方API
- 其他OpenAI兼容的服务

## 🚀 快速配置

### 步骤1：创建配置文件

在 `api/Edu_AI/` 目录下创建 `.env` 文件：

```env
# 服务器API地址（必须包含 /v1）
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1

# API密钥（如果需要）
REMOTE_MODEL_API_KEY=your-api-key-here

# 模型名称
LLM_MODEL=your-model-name

# 使用OpenAI兼容模式
DEFAULT_MODEL_TYPE=openai

# 嵌入模型配置（如果也使用远程服务，或使用本地Ollama）
DEFAULT_EMBEDDING_TYPE=ollama
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
```

### 步骤2：修改配置值

替换以下值：
- `your-server-ip` - 您的服务器IP地址
- `your-api-key-here` - API密钥（如果需要）
- `your-model-name` - 您的模型名称

### 步骤3：测试连接

```bash
# 测试服务器API是否可访问
curl http://your-server-ip:8000/v1/models

# 或测试chat completions端点
curl -X POST http://your-server-ip:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-name",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### 步骤4：启动服务

```bash
cd api/Edu_AI
start_api.bat  # Windows
# 或
bash start_api.sh  # Linux/Mac
```

## 📝 详细配置说明

### 环境变量配置

| 变量名 | 说明 | 示例 | 必填 |
|--------|------|------|------|
| `REMOTE_MODEL_API_BASE` | API服务器地址（需包含/v1） | `http://192.168.1.100:8000/v1` | ✅ |
| `REMOTE_MODEL_API_KEY` | API密钥 | `sk-your-remote-model-api-key` | ⚠️ |
| `LLM_MODEL` | 模型名称 | `qwen-7b-chat` | ✅ |
| `DEFAULT_MODEL_TYPE` | 默认模型类型 | `openai` | ✅ |
| `DEFAULT_EMBEDDING_TYPE` | 嵌入模型类型 | `ollama` 或 `openai` | ✅ |

### API请求格式

项目会自动使用OpenAI兼容格式发送请求：

```json
{
  "model": "your-model-name",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "temperature": 0.1,
  "max_tokens": 1000
}
```

### 响应格式

服务器应返回OpenAI兼容的响应：

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "your-model-name",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help you?"
    },
    "finish_reason": "stop"
  }]
}
```

## 💡 使用示例

### 示例1：基本配置

`.env` 文件：
```env
REMOTE_MODEL_API_BASE=http://192.168.1.100:8000/v1
LLM_MODEL=qwen-7b-chat
DEFAULT_MODEL_TYPE=openai
REMOTE_MODEL_API_KEY=sk-your-remote-model-api-key
```

### 示例2：通过API请求指定

即使配置了默认值，也可以在请求中覆盖：

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是数据结构？",
    "model_type": "openai",
    "api_base": "http://192.168.1.100:8000/v1",
    "model_name": "qwen-7b-chat",
    "api_key": "sk-your-remote-model-api-key"
  }'
```

### 示例3：前端调用

```typescript
const request: ChatRequest = {
  question: "什么是数据结构？",
  model_type: "openai",
  api_base: "http://your-server-ip:8000/v1",
  model_name: "your-model-name",
  api_key: "your-api-key",
  use_rag: true
};
```

## 🔧 服务器端配置示例

### vLLM服务器

```bash
# 启动vLLM服务器（OpenAI兼容模式）
python -m vllm.entrypoints.openai.api_server \
  --model your-model-path \
  --host 0.0.0.0 \
  --port 8000
```

### text-generation-inference

```bash
# 启动TGI服务器
docker run --gpus all \
  -p 8000:80 \
  -v $PWD/models:/data \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id your-model-id \
  --num-shard 1
```

### 自定义OpenAI兼容服务

确保您的服务实现以下端点：
- `POST /v1/chat/completions` - 聊天完成
- `GET /v1/models` - 列出可用模型（可选）

## ⚙️ 高级配置

### 使用不同的嵌入模型

如果您的服务器也提供嵌入模型API：

```env
# LLM使用OpenAI兼容API
DEFAULT_MODEL_TYPE=openai
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1

# 嵌入模型也使用OpenAI兼容API（需要服务器支持）
DEFAULT_EMBEDDING_TYPE=openai
# 如果嵌入模型API地址不同，需要在代码中单独配置
```

### 配置超时和重试

可以在代码中配置（`core/model_provider.py`）：

```python
ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    openai_api_base=base_url,
    timeout=60,  # 超时时间（秒）
    max_retries=3,  # 重试次数
)
```

### 使用代理

如果需要通过代理访问：

```env
# 设置HTTP代理
HTTP_PROXY=http://proxy-server:8080
HTTPS_PROXY=http://proxy-server:8080
```

或在代码中配置：
```python
import os
os.environ['HTTP_PROXY'] = 'http://proxy-server:8080'
os.environ['HTTPS_PROXY'] = 'http://proxy-server:8080'
```

## 🔍 故障排查

### 问题1：连接失败

**错误信息：** `ConnectionError` 或 `timeout`

**解决方案：**
1. 检查服务器地址和端口是否正确
2. 确认服务器API服务正在运行
3. 检查防火墙设置
4. 测试网络连接：`curl http://your-server-ip:8000/v1/models`

### 问题2：认证失败

**错误信息：** `401 Unauthorized` 或 `403 Forbidden`

**解决方案：**
1. 检查API密钥是否正确
2. 确认密钥格式（是否需要 `Bearer` 前缀）
3. 检查服务器认证配置

### 问题3：模型不存在

**错误信息：** `model not found`

**解决方案：**
1. 确认模型名称是否正确
2. 检查服务器上是否有该模型
3. 使用 `GET /v1/models` 查看可用模型列表

### 问题4：响应格式不兼容

**错误信息：** 解析错误或格式错误

**解决方案：**
1. 确认服务器返回的格式符合OpenAI标准
2. 检查响应中的字段是否完整
3. 查看服务器日志确认响应内容

## 📊 性能优化建议

1. **使用流式响应**（如果支持）：
   ```python
   # 在model_provider.py中配置
   streaming=True
   ```

2. **批量请求**：
   - 对于多个请求，考虑批量处理
   - 使用异步请求提高并发

3. **缓存**：
   - 对相同请求进行缓存
   - 使用Redis等缓存服务

4. **负载均衡**：
   - 如果有多台服务器，使用负载均衡器
   - 配置健康检查

## 📚 相关文档

- [远程模型设置](./REMOTE_MODEL_SETUP.md)
- [快速开始指南](./QUICK_START_REMOTE.md)
- [API文档](../README_API.md)

## 🔗 参考资源

- [OpenAI API文档](https://platform.openai.com/docs/api-reference)
- [vLLM文档](https://docs.vllm.ai/)
- [text-generation-inference文档](https://huggingface.co/docs/text-generation-inference/)

