# .env 文件配置更新指南

## 直接修改 .env 文件

请打开 `Edu_AI/api/Edu_AI/.env` 文件，将以下配置修改为：

```env
# LLM API配置 - 使用在线API
REMOTE_MODEL_API_BASE=https://llmapi.blsc.cn
REMOTE_MODEL_API_KEY=sk-your-remote-model-api-key
LLM_MODEL=DeepSeek-V3.2-Exp

# 默认模型ID
DEFAULT_LLM_MODEL_ID=deepseek-v3.2-exp

# Embedding配置 - 使用在线API
EMBEDDING_BACKEND=openai
EMBEDDING_API_BASE=https://llmapi.blsc.cn
EMBEDDING_MODEL=text-embedding-ada-002

# CORS配置
CORS_ALLOW_ORIGINS=*

# 聊天历史窗口
CHAT_HISTORY_WINDOW=6
```

## 关键修改点

1. **REMOTE_MODEL_API_BASE**: `http://localhost:1234/v1` → `https://llmapi.blsc.cn`
2. **REMOTE_MODEL_API_KEY**: `lm-studio` → `sk-your-remote-model-api-key`
3. **LLM_MODEL**: `qwen3-8b` → `DeepSeek-V3.2-Exp`
4. **EMBEDDING_BACKEND**: `ollama` → `openai`
5. **EMBEDDING_API_BASE**: `http://localhost:11434` → `https://llmapi.blsc.cn`

## 修改后

保存文件后，**重启后端服务**，配置即可生效。

