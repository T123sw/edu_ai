# EduAgent 模型配置指南

## 📋 配置文件说明

EduAgent 使用 `config.toml` 文件进行配置，支持多种模型和 API 服务。

## ⚙️ 配置结构

### 完整配置示例

```toml
[api_key]
# DeepSeek API 密钥（标准服务）
deepseek_api_key='your_deepseek_api_key_here'
# 自定义 API 服务密钥（优先使用）
remote_model_api_key='sk-your-remote-model-api-key'

[model]
# LLM 供应商类型: 'deepseek' 或 'openai'
llm_supply='deepseek'
# 模型名称（根据供应商选择）
llm_model='deepseek-chat'
# 或者使用 DeepSeek-V3.2-Exp: 'DeepSeek-V3.2-Exp'
# llm_model='DeepSeek-V3.2-Exp'
# 默认模型 ID（用于兼容）
default_llm_model_id='deepseek-chat'
# 温度参数（0.0-2.0），控制输出的随机性
temperature=0.2
# 最大输出 token 数
max_tokens=7000

[api_base]
# 自定义 API 基础地址（如果使用代理或自定义服务）
# 留空则使用默认地址
remote_model_api_base='https://1lmapi.blsc.cn'
# 示例: remote_model_api_base='https://1lmapi.blsc.cn'
```

## 🔧 配置场景

### 场景 1：使用标准 DeepSeek API

```toml
[api_key]
deepseek_api_key='sk-your-deepseek-api-key'

[model]
llm_supply='deepseek'
llm_model='deepseek-chat'
temperature=0.2
max_tokens=7000

[api_base]
# 留空，使用默认地址
remote_model_api_base=''
```

### 场景 2：使用自定义 API 服务（如 1lmapi.blsc.cn）

```toml
[api_key]
# 使用自定义服务的密钥
remote_model_api_key='sk-your-remote-model-api-key'

[model]
llm_supply='deepseek'
llm_model='DeepSeek-V3.2-Exp'
# 或者使用: llm_model='deepseek-v3.2-exp'
temperature=0.2
max_tokens=7000

[api_base]
# 配置自定义 API 基础地址
remote_model_api_base='https://1lmapi.blsc.cn'
```

### 场景 3：使用 OpenAI 兼容 API

```toml
[api_key]
remote_model_api_key='sk-your-openai-compatible-key'

[model]
llm_supply='openai'
llm_model='gpt-4'
temperature=0.2
max_tokens=7000

[api_base]
remote_model_api_base='https://your-api-endpoint.com/v1'
```

## 📝 配置优先级

1. **API 密钥优先级：**
   - 优先使用 `remote_model_api_key`
   - 如果未配置，则使用 `deepseek_api_key`

2. **API Base URL：**
   - 如果配置了 `remote_model_api_base`，则使用该地址
   - 否则使用默认的 API 地址

## 🔄 与 .env 文件对应关系

如果你的项目中有 `.env` 文件（如 Edu_AI 项目），可以这样对应：

**.env 文件：**
```env
REMOTE_MODEL_API_BASE=https://1lmapi.blsc.cn
REMOTE_MODEL_API_KEY=sk-your-remote-model-api-key
LLM_MODEL=DeepSeek-V3.2-Exp
DEFAULT_LLM_MODEL_ID=deepseek-v3.2-exp
```

**对应的 config.toml：**
```toml
[api_key]
remote_model_api_key='sk-your-remote-model-api-key'

[model]
llm_supply='deepseek'
llm_model='DeepSeek-V3.2-Exp'
default_llm_model_id='deepseek-v3.2-exp'
temperature=0.2
max_tokens=7000

[api_base]
remote_model_api_base='https://1lmapi.blsc.cn'
```

## 🚀 使用方式

### 方式 1：使用便捷函数（推荐）

```python
from o_agent import get_llm_from_config

# 使用配置文件中的默认设置
llm = get_llm_from_config()

# 覆盖温度参数
llm = get_llm_from_config(temperature=0.3)

# 覆盖温度和最大 token 数
llm = get_llm_from_config(temperature=0.5, max_tokens=10000)
```

### 方式 2：手动指定参数

```python
from o_agent import get_llm_by_type

llm = get_llm_by_type(
    supply='deepseek',
    model='DeepSeek-V3.2-Exp',
    api_key='sk-your-api-key',
    temperature=0.2,
    max_tokens=7000,
    base_url='https://1lmapi.blsc.cn'  # 可选
)
```

## 📊 模型参数说明

### temperature（温度）
- **范围：** 0.0 - 2.0
- **默认值：** 0.2
- **说明：**
  - 0.0-0.3：更确定、一致的回答（适合摘要、搜索）
  - 0.4-0.7：平衡创造性和准确性（适合对话）
  - 0.8-2.0：更随机、有创造性的回答（适合创作）

### max_tokens（最大输出长度）
- **默认值：** 7000
- **说明：** 控制模型生成的最大 token 数
- **建议：**
  - 摘要任务：3000-5000
  - 深度搜索：5000-7000
  - 长文本生成：10000+

### llm_supply（供应商）
- **支持值：** `'deepseek'` 或 `'openai'`
- **说明：** 指定使用的 LLM 供应商类型

### llm_model（模型名称）
- **DeepSeek 模型：**
  - `'deepseek-chat'` - 标准对话模型
  - `'DeepSeek-V3.2-Exp'` - V3.2 实验版
  - `'deepseek-v3.2-exp'` - V3.2 实验版（小写）
- **OpenAI 兼容模型：**
  - `'gpt-4'`, `'gpt-3.5-turbo'` 等

## 🔍 验证配置

创建测试脚本验证配置：

```python
# test_config.py
from o_agent import get_llm_from_config
from langchain_core.messages import HumanMessage

try:
    llm = get_llm_from_config()
    response = llm.invoke([HumanMessage(content="你好，请回复'配置成功'")])
    print(f"✅ 配置成功！")
    print(f"模型响应: {response.content}")
except Exception as e:
    print(f"❌ 配置失败: {e}")
```

运行测试：
```bash
python test_config.py
```

## 🐛 常见问题

### 问题 1：API 密钥错误

**错误信息：** `未配置 API 密钥`

**解决方法：**
1. 检查 `config.toml` 中的 `api_key` 配置
2. 确保至少配置了 `deepseek_api_key` 或 `remote_model_api_key` 之一

### 问题 2：API Base URL 错误

**错误信息：** `Connection refused` 或 `Invalid API endpoint`

**解决方法：**
1. 检查 `remote_model_api_base` 是否正确
2. 确认 API 服务是否可访问
3. 测试 API 端点：`curl https://1lmapi.blsc.cn/v1/models`

### 问题 3：模型名称错误

**错误信息：** `Model not found`

**解决方法：**
1. 确认模型名称是否正确
2. 检查 API 服务支持的模型列表
3. 尝试使用标准模型名称（如 `deepseek-chat`）

### 问题 4：配置未生效

**解决方法：**
1. 确认配置文件路径正确
2. 检查配置文件格式（TOML 语法）
3. 重启应用使配置生效

## 📚 相关文件

- `config.toml` - 配置文件
- `o_agent/llm/llms.py` - LLM 管理模块
- `define.py` - 路径和配置定义
- `deepsearch.py` - 深度搜索（使用 LLM）
- `chunks.py` - 文档处理（使用 LLM）

## 🎯 最佳实践

1. **安全性：**
   - 不要将 API 密钥提交到版本控制
   - 使用环境变量或安全的配置管理

2. **性能优化：**
   - 根据任务类型调整 temperature
   - 合理设置 max_tokens 避免浪费

3. **配置管理：**
   - 为不同环境创建不同的配置文件
   - 使用 `get_llm_from_config()` 统一管理

4. **错误处理：**
   - 实现配置验证
   - 提供清晰的错误提示

