# 故障排查指南

## ❌ 常见错误

### 错误1: `{"detail": "Not Found"}` 访问 `/v1`

**问题**: 访问 `http://192.168.1.51:8000/v1` 返回 Not Found

**原因**: `/v1` 不是有效的端点，需要使用具体的API路径

**解决方案**: 使用正确的端点：

✅ **正确的访问地址**:
- API文档: `http://192.168.1.51:8000/docs`
- 健康检查: `http://192.168.1.51:8000/health`
- 模型列表: `http://192.168.1.51:8000/v1/models`
- 聊天接口: `http://192.168.1.51:8000/v1/chat/completions`

❌ **错误的访问**:
- `http://192.168.1.51:8000/v1` (这个路径不存在)

### 错误2: 连接被拒绝

**问题**: `Connection refused` 或无法连接

**可能原因**:
1. 服务未启动
2. 防火墙阻止
3. IP地址错误

**解决方案**:

```bash
# 1. 检查服务是否运行
sudo systemctl status qwen-api

# 2. 检查端口是否监听
netstat -tulpn | grep 8000

# 3. 检查防火墙
sudo ufw status

# 4. 测试本地连接
curl http://localhost:8000/health
```

### 错误3: 模型未加载

**问题**: `{"detail": "模型未加载"}`

**原因**: 模型还在加载中或加载失败

**解决方案**:

```bash
# 查看服务日志
sudo journalctl -u qwen-api -f

# 检查GPU
nvidia-smi

# 检查模型路径
ls -la /home/llm/models/huggingface/Qwen2-7B
```

### 错误4: CUDA out of memory

**问题**: GPU显存不足

**解决方案**:
1. 检查其他进程占用GPU: `nvidia-smi`
2. 减少 `MAX_LENGTH` 配置
3. 使用量化模型

## ✅ 正确的测试步骤

### 步骤1: 检查服务状态

```bash
# 在服务器上
sudo systemctl status qwen-api
```

### 步骤2: 测试本地连接

```bash
# 在服务器上测试
curl http://localhost:8000/health
```

应该返回：
```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cuda",
  "model_path": "/home/llm/models/huggingface/Qwen2-7B"
}
```

### 步骤3: 测试API端点

```bash
# 测试模型列表
curl http://localhost:8000/v1/models

# 测试聊天接口
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 步骤4: 从客户端测试

```bash
# 从您的电脑测试（替换为实际IP）
curl http://192.168.1.51:8000/health

# 测试聊天接口
curl -X POST http://192.168.1.51:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 🔍 诊断命令

### 检查服务

```bash
# 服务状态
sudo systemctl status qwen-api

# 服务日志
sudo journalctl -u qwen-api -n 50

# 实时日志
sudo journalctl -u qwen-api -f
```

### 检查网络

```bash
# 检查端口
netstat -tulpn | grep 8000

# 检查防火墙
sudo ufw status
sudo ufw allow 8000/tcp

# 测试连接
telnet localhost 8000
```

### 检查模型

```bash
# 检查模型文件
ls -la /home/llm/models/huggingface/Qwen2-7B

# 检查GPU
nvidia-smi

# 检查Python环境
source /home/llm/api-service/venv/bin/activate
python -c "import torch; print(torch.cuda.is_available())"
```

## 📝 正确的API端点列表

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径，返回服务信息 |
| `/health` | GET | 健康检查 |
| `/docs` | GET | API文档（Swagger UI） |
| `/v1/models` | GET | 列出可用模型 |
| `/v1/chat/completions` | POST | 聊天完成接口 |

## 💡 快速测试脚本

在服务器上运行：

```bash
# 使用提供的测试脚本
chmod +x test_server.sh
./test_server.sh
```

## 🔗 相关文档

- [服务器部署指南](./FASTAPI_SERVER_DEPLOYMENT.md)
- [完整集成指南](./COMPLETE_INTEGRATION_GUIDE.md)

