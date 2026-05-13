# 远程模型快速配置指南

## 🚀 5分钟快速配置

### 如果您的服务器运行Ollama

#### 步骤1：配置环境变量

在 `api/Edu_AI/` 目录创建 `.env` 文件：

```env
OLLAMA_BASE_URL=http://your-server-ip:11434
LLM_MODEL=qwen:7b
EMBEDDING_MODEL=nomic-embed-text
DEFAULT_MODEL_TYPE=ollama
```

**替换 `your-server-ip` 为您的服务器IP地址**

#### 步骤2：启动服务

```bash
cd api/Edu_AI
start_api.bat  # Windows
# 或
bash start_api.sh  # Linux/Mac
```

#### 步骤3：测试

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "你好"}'
```

**完成！** 🎉

### 如果服务器是OpenAI兼容API

#### 步骤1：配置环境变量

```env
DEFAULT_MODEL_TYPE=openai
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1
REMOTE_MODEL_API_KEY=your-api-key
```

#### 步骤2：API调用时指定

```json
{
  "question": "你好",
  "model_type": "openai",
  "api_base": "http://your-server-ip:8000/v1",
  "model_name": "your-model"
}
```

## ❓ 常见问题

**Q: 是否还需要Ollama？**
A: 如果服务器上运行Ollama，推荐使用Ollama模式（最简单）。如果服务器是其他API服务，可以使用OpenAI兼容模式。

**Q: 如何确认服务器地址？**
A: 在服务器上运行 `curl http://localhost:11434/api/tags` 测试。如果可访问，将 `localhost` 替换为服务器IP。

**Q: 连接失败怎么办？**
A: 检查：
1. 服务器IP和端口是否正确
2. 防火墙是否开放端口
3. 服务器Ollama服务是否运行

## 📖 详细文档

- [完整集成指南](./REMOTE_MODEL_SETUP.md)
- [使用指南](../USAGE.md)

