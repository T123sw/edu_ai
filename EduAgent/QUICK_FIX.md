# 快速修复 API 认证问题

## 🔴 当前问题

API 返回 `401 Authentication Fails`，说明 API 密钥认证失败。

## ✅ 解决方案

### 方案 1: 验证 API 密钥是否正确

**检查步骤：**
1. 确认 API 密钥没有多余的空格或换行
2. 确认 API 密钥是否已过期
3. 联系 API 服务提供商确认密钥状态

### 方案 2: 尝试使用 OpenAI 兼容模式

如果 `1lmapi.blsc.cn` 是 OpenAI 兼容的 API，修改 `config.toml`：

```toml
[model]
llm_supply='openai'  # 改为 openai
llm_model='gpt-3.5-turbo'  # 或实际支持的模型名

[api_base]
remote_model_api_base='https://1lmapi.blsc.cn/v1'
```

### 方案 3: 尝试不同的 base_url 格式

```toml
# 选项 1: 带 /v1
remote_model_api_base='https://1lmapi.blsc.cn/v1'

# 选项 2: 不带 /v1
remote_model_api_base='https://1lmapi.blsc.cn'

# 选项 3: 带 /api/v1
remote_model_api_base='https://1lmapi.blsc.cn/api/v1'
```

### 方案 4: 尝试不同的模型名称

```toml
# 选项 1: 标准名称
llm_model='deepseek-chat'

# 选项 2: 小写版本
llm_model='deepseek-v3.2-exp'

# 选项 3: 原始名称
llm_model='DeepSeek-V3.2-Exp'
```

### 方案 5: 检查 API 服务文档

请确认：
1. API 服务是否支持 DeepSeek 模型
2. 正确的 API 端点格式
3. 认证方式（Bearer token 或其他）
4. 支持的模型列表

## 🧪 测试命令

```bash
# 测试配置
python test_config.py

# 直接测试 API
python test_api_direct.py
```

## 📝 推荐配置（如果使用 OpenAI 兼容 API）

```toml
[api_key]
remote_model_api_key='sk-your-remote-model-api-key'

[model]
llm_supply='openai'
llm_model='gpt-3.5-turbo'
temperature=0.2
max_tokens=7000

[api_base]
remote_model_api_base='https://1lmapi.blsc.cn/v1'
```

## 🔍 如果仍然失败

请提供以下信息：
1. API 服务提供商的文档链接
2. 正确的 API 端点格式
3. 支持的模型列表
4. 认证方式说明

