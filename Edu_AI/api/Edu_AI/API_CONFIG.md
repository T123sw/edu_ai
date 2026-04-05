# 在线大模型API配置说明

## 当前配置

系统已配置为使用在线大模型API服务。

### API配置信息

- **API地址**: `https://llmapi.blsc.cn`
- **API密钥**: `sk-your-remote-model-api-key`
- **默认模型**: `DeepSeek-V3.2-Exp`
- **模型ID**: `deepseek-v3.2-exp`

### 环境变量配置（可选）

如果需要覆盖默认配置，可以在 `Edu_AI/api/Edu_AI/.env` 文件中设置以下环境变量：

```bash
# 在线大模型API配置
REMOTE_MODEL_API_BASE=https://llmapi.blsc.cn
REMOTE_MODEL_API_KEY=sk-your-remote-model-api-key
LLM_MODEL=DeepSeek-V3.2-Exp

# 默认模型ID
DEFAULT_LLM_MODEL_ID=deepseek-v3.2-exp

# Embedding配置（可以继续使用本地或在线服务）
EMBEDDING_BACKEND=openai
EMBEDDING_API_BASE=https://llmapi.blsc.cn
EMBEDDING_MODEL=text-embedding-ada-002

# CORS配置
CORS_ALLOW_ORIGINS=*

# 聊天历史窗口
CHAT_HISTORY_WINDOW=6
```

## API接口说明

系统使用OpenAI兼容的API接口：

- **聊天接口**: `POST /v1/chat/completions`
- **认证方式**: Bearer Token (API Key)

## 代码变更说明

### 1. core/config.py

已更新默认配置：
- `REMOTE_MODEL_API_BASE`: 默认值设置为 `https://llmapi.blsc.cn`
- `REMOTE_MODEL_API_KEY`: 默认值设置为提供的API密钥
- `LLM_MODEL`: 默认值设置为 `DeepSeek-V3.2-Exp`
- `EMBEDDING_BACKEND`: 默认值设置为 `openai`
- `EMBEDDING_API_BASE`: 默认值设置为 `https://llmapi.blsc.cn`
- 模型注册列表：更新为使用 `deepseek-v3.2-exp` 作为默认模型

### 2. new_rag/system.py

`_call_llm` 方法已确保正确处理API调用：
- 自动添加 `/v1` 后缀（如果API base URL不包含）
- 正确设置 Authorization header
- 使用OpenAI兼容的请求格式

## 验证配置

启动服务后，可以通过以下方式验证配置：

1. **检查模型列表**:
   ```bash
   curl http://localhost:8000/models
   ```

2. **测试聊天接口**:
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"question": "你好"}'
   ```

## 注意事项

1. API密钥已硬编码在配置文件中，如需更改请更新 `core/config.py` 或使用 `.env` 文件
2. 确保网络可以访问 `https://llmapi.blsc.cn`
3. API使用OpenAI兼容格式，模型名称必须是API服务支持的模型名称

