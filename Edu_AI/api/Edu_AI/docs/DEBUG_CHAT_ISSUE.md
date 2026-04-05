# 对话"正在思考"问题排查指南

## 🔍 问题现象

前端显示"正在思考..."，但一直无法返回答案。

## 🎯 可能原因

1. **后端API服务未运行**
2. **服务器模型API未运行或无法连接**
3. **配置错误（API地址不正确）**
4. **网络连接问题**
5. **请求超时**
6. **模型加载失败**

## ✅ 排查步骤

### 步骤1：检查后端API服务

```bash
# 检查服务是否运行
# Windows: 查看任务管理器或运行
netstat -ano | findstr :8000

# 测试本地API
curl http://localhost:8000/health
```

如果无法访问，启动服务：
```bash
cd api/Edu_AI
start_api.bat  # Windows
```

### 步骤2：检查服务器模型API

```bash
# 在服务器上检查
sudo systemctl status qwen-api

# 测试服务器API
curl http://192.168.1.51:8000/health
curl http://192.168.1.51:8000/v1/models
```

### 步骤3：检查配置文件

确认 `api/Edu_AI/.env` 文件存在且配置正确：

```env
REMOTE_MODEL_API_BASE=http://192.168.1.51:8000/v1
LLM_MODEL=Qwen2-7B
DEFAULT_MODEL_TYPE=openai
```

### 步骤4：检查浏览器控制台

1. 打开浏览器开发者工具（F12）
2. 查看 Console 标签页的错误信息
3. 查看 Network 标签页的请求状态

常见错误：
- `Failed to fetch` - 后端服务未运行
- `Network Error` - 网络连接问题
- `Timeout` - 请求超时
- `404 Not Found` - API路径错误
- `500 Internal Server Error` - 服务器内部错误

### 步骤5：检查后端日志

查看后端API服务的日志输出，查找错误信息。

## 🔧 快速修复

### 修复1：确保配置文件存在

```bash
cd api/Edu_AI

# 复制配置文件
copy config_server_192.168.1.51.env .env

# 或手动创建
```

### 修复2：检查服务器连接

```bash
# 测试服务器连接
ping 192.168.1.51
telnet 192.168.1.51 8000

# 测试API
curl http://192.168.1.51:8000/health
```

### 修复3：临时关闭RAG测试

如果RAG功能有问题，可以临时关闭：

在前端界面，将"RAG"开关关闭，然后重试。

### 修复4：检查模型类型

确保前端选择的模型类型与配置一致：
- 如果使用OpenAI兼容模式，选择"OpenAI"
- 如果使用Ollama，选择对应的选项

## 📝 调试代码

### 添加详细日志

在后端 `app/main.py` 的 `chat` 函数中添加日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 在chat函数开始处
print(f"收到请求: question={request.question}, model_type={request.model_type}")
print(f"使用api_base: {api_base}")
```

### 测试直接调用

```bash
# 测试后端API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "你好",
    "model_type": "openai",
    "api_base": "http://192.168.1.51:8000/v1",
    "model_name": "Qwen2-7B",
    "use_rag": false
  }'
```

## 🎯 常见解决方案

### 方案1：服务器模型API未运行

```bash
# 在服务器上启动
cd /home/llm/api-service
source venv/bin/activate
python server_model_api.py
```

### 方案2：配置错误

检查 `.env` 文件中的 `REMOTE_MODEL_API_BASE` 是否正确。

### 方案3：网络问题

- 检查防火墙设置
- 确认IP地址正确
- 测试网络连通性

### 方案4：使用本地模型（临时方案）

如果服务器连接有问题，可以临时使用本地Ollama：

```env
DEFAULT_MODEL_TYPE=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

## 📊 检查清单

- [ ] 后端API服务运行正常
- [ ] 服务器模型API运行正常
- [ ] `.env` 配置文件存在且正确
- [ ] 网络连接正常
- [ ] 浏览器控制台无错误
- [ ] 后端日志无错误
- [ ] 服务器API可访问

## 🔗 相关文档

- [故障排查](./TROUBLESHOOTING.md)
- [服务器部署](./FASTAPI_SERVER_DEPLOYMENT.md)
- [完整集成指南](./COMPLETE_INTEGRATION_GUIDE.md)

