# API 配置问题排查指南

## 🔍 当前错误

```
AuthenticationError: Error code: 401
Authentication Fails, Your api key: ****uuvw is invalid
```

## 📋 可能的原因和解决方案

### 1. API 密钥无效或过期

**检查方法：**
- 确认 API 密钥是否正确复制（没有多余空格）
- 检查密钥是否已过期
- 验证密钥是否属于正确的 API 服务

**解决方案：**
```toml
[api_key]
remote_model_api_key='你的正确API密钥'
```

### 2. base_url 格式不正确

**问题：** LangChain 的 `ChatDeepSeek` 可能需要完整的 API 端点路径。

**尝试的格式：**
- `https://1lmapi.blsc.cn` （当前）
- `https://1lmapi.blsc.cn/v1` （可能需要）
- `https://1lmapi.blsc.cn/api/v1` （某些服务需要）

**解决方案：**
更新 `config.toml`：
```toml
[api_base]
remote_model_api_base='https://1lmapi.blsc.cn/v1'
```

### 3. 模型名称不匹配

**问题：** API 服务可能不支持 `DeepSeek-V3.2-Exp` 这个模型名称。

**尝试的模型名称：**
- `deepseek-chat`
- `deepseek-v3.2-exp`
- `DeepSeek-V3.2-Exp`
- `gpt-3.5-turbo`（如果使用 OpenAI 兼容 API）

**解决方案：**
```toml
[model]
llm_model='deepseek-chat'  # 或尝试其他名称
```

### 4. 使用 OpenAI 兼容模式

如果 `1lmapi.blsc.cn` 是 OpenAI 兼容的 API，可能需要使用 `openai` 供应商：

```toml
[model]
llm_supply='openai'  # 改为 openai
llm_model='gpt-3.5-turbo'  # 或实际支持的模型名
```

### 5. API 服务端点验证

**测试 API 是否可访问：**

```python
import requests

base_url = "https://1lmapi.blsc.cn"
api_key = "sk-your-api-key"

# 测试 1: 检查 /v1/models
response = requests.get(
    f"{base_url}/v1/models",
    headers={"Authorization": f"Bearer {api_key}"}
)
print(f"状态码: {response.status_code}")
print(f"响应: {response.text}")

# 测试 2: 检查 /models
response = requests.get(
    f"{base_url}/models",
    headers={"Authorization": f"Bearer {api_key}"}
)
print(f"状态码: {response.status_code}")
```

## 🔧 快速修复步骤

### 步骤 1: 检查 base_url 格式

尝试在 `config.toml` 中添加 `/v1`：

```toml
[api_base]
remote_model_api_base='https://1lmapi.blsc.cn/v1'
```

### 步骤 2: 尝试标准模型名称

```toml
[model]
llm_model='deepseek-chat'
```

### 步骤 3: 如果使用 OpenAI 兼容 API

```toml
[model]
llm_supply='openai'
llm_model='gpt-3.5-turbo'

[api_base]
remote_model_api_base='https://1lmapi.blsc.cn/v1'
```

### 步骤 4: 验证 API 密钥

联系 API 服务提供商确认：
- API 密钥是否有效
- 正确的 API 端点格式
- 支持的模型列表
- 认证方式（Bearer token 格式）

## 🧪 测试脚本

运行诊断脚本：

```bash
python test_api_connection.py
```

这将测试：
1. API 端点是否可访问
2. 不同的 base_url 格式
3. 配置详情

## 📞 联系支持

如果以上方法都不行，请提供：
1. API 服务文档
2. 正确的 API 端点格式
3. 支持的模型列表
4. 认证方式说明

