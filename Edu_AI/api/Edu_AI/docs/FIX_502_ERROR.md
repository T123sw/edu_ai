# 🔧 修复 502 Bad Gateway 错误

## 错误信息

```
错误: 处理请求时出错: 500: LLM调用失败: Error code: 502
```

## ✅ 好消息

测试脚本显示服务器连接正常：
- ✅ 健康检查通过 (`http://192.168.1.51:8000/health`)
- ✅ 模型列表获取成功
- ✅ 对话测试成功

## 🔍 可能的原因

502错误通常表示：
1. **LangChain ChatOpenAI 客户端配置问题**
2. **base_url 路径问题**（可能重复添加 `/v1`）
3. **请求超时或服务器临时不可用**
4. **模型响应时间过长**

## 🔧 解决方案

### 方案1：检查 base_url 配置

确保 `.env` 文件中的 `REMOTE_MODEL_API_BASE` 正确：

```env
REMOTE_MODEL_API_BASE=http://192.168.1.51:8000/v1
```

**注意**：必须包含 `/v1` 路径。

### 方案2：检查服务器端日志

在服务器上查看 `server_model_api.py` 的日志，看是否有错误信息。

### 方案3：增加超时时间

如果模型响应较慢，可能需要增加超时时间。检查 `app/main.py` 中的超时设置。

### 方案4：验证 LangChain 配置

测试 LangChain 是否能正确调用服务器：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model_name='Qwen2-7B',
    openai_api_base='http://192.168.1.51:8000/v1',
    openai_api_key='dummy-key',
    timeout=60  # 增加超时时间
)

result = llm.invoke('你好')
print(result.content)
```

## 🧪 诊断步骤

### 1. 运行连接测试脚本

```bash
cd api/Edu_AI
python scripts/test_server_connection.py
```

如果测试通过，说明服务器端正常。

### 2. 检查后端日志

查看 `start_api.bat` 的输出，查找：
- `[ERROR] LLM调用失败`
- `[ERROR] 错误详情`

### 3. 检查网络连接

```bash
# 测试服务器连接
curl http://192.168.1.51:8000/health

# 测试对话端点
curl -X POST http://192.168.1.51:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "Qwen2-7B", "messages": [{"role": "user", "content": "你好"}]}'
```

### 4. 检查防火墙

确保：
- Windows 防火墙允许端口 8000 的通信
- 服务器防火墙允许端口 8000 的入站连接

## 🔄 快速修复

### 如果服务器测试通过但应用失败：

1. **重启后端服务**
   ```bash
   # 停止服务 (Ctrl+C)
   # 重新启动
   cd api/Edu_AI
   start_api.bat
   ```

2. **检查配置是否正确加载**
   启动后查看日志：
   ```
   [DEBUG] 配置信息: DEFAULT_MODEL_TYPE=openai, REMOTE_MODEL_API_BASE=http://192.168.1.51:8000/v1
   ```

3. **如果仍然失败，检查 LangChain 版本**
   ```bash
   pip show langchain-openai
   ```
   确保版本兼容。

## 📝 常见问题

### Q: 为什么测试脚本成功但应用失败？

A: 可能是：
- LangChain 的 `ChatOpenAI` 客户端配置问题
- 请求格式或参数不匹配
- 超时设置过短

### Q: 如何查看详细的错误信息？

A: 查看后端服务的日志输出，应该包含完整的错误堆栈。

### Q: 服务器端需要做什么配置？

A: 确保：
- `server_model_api.py` 正在运行
- 端口 8000 未被占用
- 模型已正确加载

## ✅ 验证

修复后，在前端发送消息应该能正常响应，不再出现 502 错误。

