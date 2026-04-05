# 完整集成方案：FastAPI模型服务器

## 🎯 方案概述

本方案使用FastAPI在A100服务器上部署Qwen2-7B模型，提供OpenAI兼容的API服务，然后集成到您的项目中。

## 📋 架构图

```
┌─────────────────────────────────────────────────┐
│            A100服务器 (模型服务器)              │
│  ┌──────────────────────────────────────────┐  │
│  │  /home/llm/models/huggingface/Qwen2-7B  │  │
│  │  - config.json                           │  │
│  │  - model-*.safetensors (4个文件)        │  │
│  │  - tokenizer相关文件                     │  │
│  └──────────────────────────────────────────┘  │
│                    ↓                              │
│  ┌──────────────────────────────────────────┐  │
│  │  FastAPI服务 (server_model_api.py)        │  │
│  │  - 加载模型到GPU                           │  │
│  │  - 提供OpenAI兼容API                      │  │
│  │  - 端口: 8000                             │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
                    ↓ HTTP API
                    ↓
┌─────────────────────────────────────────────────┐
│           您的项目 (客户端)                     │
│  ┌──────────────────────────────────────────┐  │
│  │  api/Edu_AI/                             │  │
│  │  - .env (配置服务器地址)                  │  │
│  │  - app/main.py (API服务)                  │  │
│  │  - core/model_provider.py (模型调用)      │  │
│  └──────────────────────────────────────────┘  │
│                    ↓                              │
│  ┌──────────────────────────────────────────┐  │
│  │  前端 (React)                            │  │
│  │  - src/pages/ChatPage.tsx                │  │
│  │  - src/services/chat.ts                  │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## 🚀 完整部署步骤

### 第一部分：服务器端部署

#### 1. 准备服务器环境

```bash
# SSH到A100服务器
ssh user@your-server-ip

# 创建服务目录
mkdir -p /home/llm/api-service
cd /home/llm/api-service
```

#### 2. 上传服务文件

将以下文件上传到服务器：

- `scripts/server_model_api.py`
- `scripts/server_requirements.txt`
- `scripts/deploy_server.sh` (可选)

```bash
# 方法1: 使用scp
scp server_model_api.py server_requirements.txt user@server:/home/llm/api-service/

# 方法2: 使用git
cd /home/llm/api-service
git clone <your-repo> .
```

#### 3. 安装依赖

```bash
cd /home/llm/api-service

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r server_requirements.txt
```

#### 4. 配置环境变量

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

#### 5. 测试运行

```bash
# 激活环境
source venv/bin/activate

# 运行服务（首次会加载模型，需要几分钟）
python server_model_api.py
```

看到 "模型加载完成！" 后，在另一个终端测试：

```bash
# 测试健康检查
curl http://localhost:8000/health

# 测试API
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

#### 6. 配置systemd服务（后台运行）

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

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable qwen-api
sudo systemctl start qwen-api

# 查看状态
sudo systemctl status qwen-api
```

#### 7. 配置防火墙

```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

#### 8. 获取服务器IP

```bash
hostname -I
# 或
ip addr show
```

### 第二部分：客户端配置

#### 1. 配置项目

在项目 `api/Edu_AI/` 目录下创建 `.env` 文件：

```env
# 服务器API地址（替换为您的服务器IP）
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1

# 模型名称
LLM_MODEL=Qwen2-7B

# 使用OpenAI兼容模式
DEFAULT_MODEL_TYPE=openai

# 嵌入模型配置（使用本地Ollama或远程服务）
DEFAULT_EMBEDDING_TYPE=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

**重要**: 将 `your-server-ip` 替换为实际的服务器IP地址。

#### 2. 测试连接

```bash
# 测试服务器API（从您的电脑）
curl http://your-server-ip:8000/health

# 测试聊天接口
curl -X POST http://your-server-ip:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

#### 3. 启动项目API

```bash
cd api/Edu_AI
start_api.bat  # Windows
# 或
bash start_api.sh  # Linux/Mac
```

#### 4. 测试项目API

```bash
# 测试项目API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "你好"}'
```

## 📝 配置文件示例

### 服务器端 `.env`

```env
MODEL_PATH=/home/llm/models/huggingface/Qwen2-7B
DEVICE=cuda
HOST=0.0.0.0
PORT=8000
MAX_LENGTH=4096
TEMPERATURE=0.7
TOP_P=0.9
```

### 客户端 `.env`

```env
REMOTE_MODEL_API_BASE=http://192.168.1.100:8000/v1
LLM_MODEL=Qwen2-7B
DEFAULT_MODEL_TYPE=openai
DEFAULT_EMBEDDING_TYPE=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

## 🔍 验证清单

### 服务器端

- [ ] 模型文件存在且可读
- [ ] 虚拟环境创建成功
- [ ] 依赖安装完成
- [ ] 服务文件上传完成
- [ ] 环境变量配置正确
- [ ] 服务可以启动
- [ ] API测试通过
- [ ] systemd服务配置完成
- [ ] 防火墙配置完成
- [ ] 可以从外部访问

### 客户端

- [ ] `.env` 文件配置正确
- [ ] 可以连接到服务器API
- [ ] 项目API服务启动成功
- [ ] 端到端测试通过

## 🎯 使用方式

### 方式1：使用默认配置

配置好 `.env` 后，直接调用：

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是数据结构？"}'
```

### 方式2：API请求中指定

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是数据结构？",
    "model_type": "openai",
    "api_base": "http://your-server-ip:8000/v1",
    "model_name": "Qwen2-7B"
  }'
```

### 方式3：前端调用

前端会自动使用配置的服务器地址。

## ⚠️ 注意事项

1. **网络连接**: 确保客户端可以访问服务器
2. **防火墙**: 确保服务器8000端口开放
3. **GPU显存**: Qwen2-7B需要约14-16GB显存
4. **模型加载**: 首次加载需要几分钟
5. **性能**: 使用GPU加速，响应速度更快

## 🔧 故障排查

### 服务器端问题

```bash
# 查看服务状态
sudo systemctl status qwen-api

# 查看日志
sudo journalctl -u qwen-api -f

# 检查GPU
nvidia-smi

# 检查端口
netstat -tulpn | grep 8000
```

### 客户端问题

```bash
# 测试连接
ping your-server-ip
telnet your-server-ip 8000

# 检查配置
cat api/Edu_AI/.env
```

## 📚 相关文档

- [FastAPI服务器部署](./FASTAPI_SERVER_DEPLOYMENT.md)
- [OpenAI兼容配置](./OPENAI_COMPATIBLE_SETUP.md)
- [A100部署指南](./A100_DEPLOYMENT.md)

## ✅ 完成

配置完成后，您的项目就可以通过FastAPI服务使用A100服务器上的Qwen2-7B模型了！

