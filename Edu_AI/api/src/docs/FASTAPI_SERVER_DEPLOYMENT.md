# FastAPI模型服务器部署完整指南

## 📋 概述

本指南介绍如何在A100服务器上使用FastAPI部署Qwen2-7B模型，提供OpenAI兼容的API服务。

## 🎯 部署架构

```
A100服务器                   客户端（您的项目）
┌─────────────┐              ┌─────────────┐
│  Qwen2-7B   │              │  Edu-AI     │
│  模型文件   │              │  项目       │
│             │              │             │
│  FastAPI    │  HTTP API    │  FastAPI    │
│  服务       │◄─────────────┤  客户端     │
│  :8000      │              │  :8000      │
└─────────────┘              └─────────────┘
```

## 📦 服务器端部署

### 步骤1：准备环境

在A100服务器上执行：

```bash
# 1. 创建服务目录
mkdir -p /home/llm/api-service
cd /home/llm/api-service

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install --upgrade pip
pip install fastapi uvicorn[standard]
pip install torch transformers accelerate sentencepiece
pip install pydantic python-multipart
```

### 步骤2：上传服务文件

将以下文件上传到服务器 `/home/llm/api-service/`：

1. `server_model_api.py` - API服务主文件
2. `server_requirements.txt` - 依赖列表

或使用git克隆：

```bash
cd /home/llm/api-service
# 从您的仓库克隆或上传文件
```

### 步骤3：配置环境变量

创建 `.env` 文件：

```bash
cat > /home/llm/api-service/.env << EOF
MODEL_PATH=/home/llm/models/huggingface/Qwen2-7B
DEVICE=cuda
HOST=0.0.0.0
PORT=8000
MAX_LENGTH=4096
TEMPERATURE=0.7
TOP_P=0.9
EOF
```

### 步骤4：测试运行

```bash
cd /home/llm/api-service
source venv/bin/activate
python server_model_api.py
```

首次运行会加载模型，可能需要几分钟时间。

### 步骤5：配置systemd服务（后台运行）

创建服务文件：

```bash
sudo tee /etc/systemd/system/qwen-api.service > /dev/null << 'EOF'
[Unit]
Description=Qwen2-7B API Service
After=network.target

[Service]
Type=simple
User=llm
WorkingDirectory=/home/llm/api-service
Environment="PATH=/home/llm/api-service/venv/bin"
EnvironmentFile=/home/llm/api-service/.env
ExecStart=/home/llm/api-service/venv/bin/python /home/llm/api-service/server_model_api.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable qwen-api
sudo systemctl start qwen-api

# 查看状态
sudo systemctl status qwen-api

# 查看日志
sudo journalctl -u qwen-api -f
```

### 步骤6：配置防火墙

```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

## 🔧 客户端配置

### 步骤1：获取服务器IP

在服务器上查看IP地址：

```bash
hostname -I
# 或
ip addr show
```

### 步骤2：配置项目

在项目 `api/Edu_AI/` 目录下创建或编辑 `.env` 文件：

```env
# 服务器API地址（替换为您的服务器IP）
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1

# 模型名称（与服务器上的模型名称一致）
LLM_MODEL=Qwen2-7B

# 使用OpenAI兼容模式
DEFAULT_MODEL_TYPE=openai

# 嵌入模型配置（如果也在服务器上，或使用本地Ollama）
DEFAULT_EMBEDDING_TYPE=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

### 步骤3：测试连接

```bash
# 测试服务器API
curl http://your-server-ip:8000/health

# 测试聊天接口
curl -X POST http://your-server-ip:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 测试项目API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "你好"}'
```

## 📝 快速部署脚本

使用提供的部署脚本（在服务器上运行）：

```bash
# 1. 上传 deploy_server.sh 到服务器
# 2. 赋予执行权限
chmod +x deploy_server.sh

# 3. 运行部署脚本
./deploy_server.sh
```

脚本会自动完成：
- 创建虚拟环境
- 安装依赖
- 配置服务
- 启动systemd服务

## ⚙️ 配置参数说明

### 服务器端配置（.env）

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `MODEL_PATH` | 模型路径 | - | `/home/llm/models/huggingface/Qwen2-7B` |
| `DEVICE` | 设备类型 | `cuda` | `cuda` 或 `cpu` |
| `HOST` | 监听地址 | `0.0.0.0` | `0.0.0.0` |
| `PORT` | 监听端口 | `8000` | `8000` |
| `MAX_LENGTH` | 最大序列长度 | `4096` | `4096` 或 `8192` |
| `TEMPERATURE` | 默认温度 | `0.7` | `0.0-2.0` |
| `TOP_P` | 默认top_p | `0.9` | `0.0-1.0` |

### 客户端配置（.env）

| 参数 | 说明 | 示例 |
|------|------|------|
| `REMOTE_MODEL_API_BASE` | 服务器API地址 | `http://192.168.1.100:8000/v1` |
| `LLM_MODEL` | 模型名称 | `Qwen2-7B` |
| `DEFAULT_MODEL_TYPE` | 模型类型 | `openai` |

## 🔍 验证部署

### 1. 检查服务状态

```bash
# 在服务器上
sudo systemctl status qwen-api

# 检查端口
netstat -tulpn | grep 8000

# 检查GPU使用
nvidia-smi
```

### 2. 测试API端点

```bash
# 健康检查
curl http://your-server-ip:8000/health

# 列出模型
curl http://your-server-ip:8000/v1/models

# 测试对话
curl -X POST http://your-server-ip:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [
      {"role": "user", "content": "请用一句话介绍自己"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### 3. 查看API文档

访问：`http://your-server-ip:8000/docs`

## 🚀 性能优化

### 1. 使用量化（节省显存）

修改 `server_model_api.py`：

```python
from transformers import BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    quantization_config=quantization_config,
    device_map="auto",
    trust_remote_code=True
)
```

### 2. 使用Flash Attention（加速）

```bash
pip install flash-attn --no-build-isolation
```

### 3. 调整批处理大小

在生成参数中调整 `max_tokens` 和 `MAX_LENGTH`。

## 🔧 故障排查

### 问题1：模型加载失败

**错误**: `CUDA out of memory`

**解决**:
- 减少 `MAX_LENGTH`
- 使用量化（4bit或8bit）
- 检查其他进程占用GPU

### 问题2：服务无法启动

**检查**:
```bash
# 查看日志
sudo journalctl -u qwen-api -n 50

# 检查端口占用
netstat -tulpn | grep 8000

# 检查权限
ls -la /home/llm/models/huggingface/Qwen2-7B
```

### 问题3：连接超时

**检查**:
- 防火墙配置
- 服务器IP地址
- 网络连接

```bash
# 测试连接
ping your-server-ip
telnet your-server-ip 8000
```

### 问题4：响应慢

**优化**:
- 使用GPU加速（确保 `DEVICE=cuda`）
- 减少 `max_tokens`
- 使用量化模型
- 检查GPU利用率：`nvidia-smi`

## 📊 监控和维护

### 查看服务日志

```bash
# 实时日志
sudo journalctl -u qwen-api -f

# 最近100行
sudo journalctl -u qwen-api -n 100
```

### 重启服务

```bash
sudo systemctl restart qwen-api
```

### 停止服务

```bash
sudo systemctl stop qwen-api
```

### 更新模型

1. 停止服务
2. 更新模型文件
3. 重启服务（会自动重新加载）

## 📚 相关文档

- [OpenAI兼容配置](./OPENAI_COMPATIBLE_SETUP.md)
- [A100部署指南](./A100_DEPLOYMENT.md)
- [项目配置说明](../README_OPENAI_CONFIG.md)

## ✅ 部署检查清单

- [ ] 服务器环境准备完成
- [ ] 模型文件路径正确
- [ ] 依赖安装完成
- [ ] 服务文件上传完成
- [ ] 环境变量配置正确
- [ ] systemd服务配置完成
- [ ] 防火墙配置完成
- [ ] 服务启动成功
- [ ] API测试通过
- [ ] 客户端配置完成
- [ ] 端到端测试通过

