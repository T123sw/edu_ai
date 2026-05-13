# 服务器部署指南（IP: 192.168.1.51）

## 🎯 服务器信息

- **服务器IP**: `192.168.1.51` (主IP) 或 `10.10.10.205`
- **模型路径**: `/home/llm/models/huggingface/Qwen2-7B`
- **当前目录**: `~/api-service`

## 📋 快速部署步骤

### 在服务器上执行（当前在 ~/api-service 目录）

#### 步骤1：确认文件

```bash
# 检查文件是否存在
ls -la server_model_api.py server_requirements.txt
```

#### 步骤2：一键设置（推荐）

```bash
# 运行快速设置脚本
chmod +x server_setup_commands.sh
bash server_setup_commands.sh
```

或手动执行：

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install --upgrade pip
pip install -r server_requirements.txt

# 3. 创建配置文件
cat > .env << 'EOF'
MODEL_PATH=/home/llm/models/huggingface/Qwen2-7B
DEVICE=cuda
HOST=0.0.0.0
PORT=8000
MAX_LENGTH=4096
TEMPERATURE=0.7
TOP_P=0.9
EOF
```

#### 步骤3：测试运行

```bash
# 确保虚拟环境已激活
source venv/bin/activate

# 运行服务（首次加载模型需要几分钟）
python server_model_api.py
```

看到以下输出表示成功：
```
==================================================
模型加载完成！
模型设备: cuda:0
API服务地址: http://0.0.0.0:8000
==================================================
```

#### 步骤4：测试API（新终端）

```bash
# 健康检查
curl http://localhost:8000/health

# 测试对话
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

#### 步骤5：配置后台服务

```bash
# 创建systemd服务
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

#### 步骤6：配置防火墙

```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

## 💻 客户端配置

在您的项目 `api/Edu_AI/` 目录下：

```bash
# 复制配置文件
copy config_server_192.168.1.51.env .env

# 或手动创建 .env 文件
```

`.env` 文件内容：

```env
REMOTE_MODEL_API_BASE=http://192.168.1.51:8000/v1
LLM_MODEL=Qwen2-7B
DEFAULT_MODEL_TYPE=openai
DEFAULT_EMBEDDING_TYPE=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

## ✅ 验证连接

### 从客户端测试

```bash
# 测试服务器健康检查
curl http://192.168.1.51:8000/health

# 测试聊天API
curl -X POST http://192.168.1.51:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 启动项目并测试

```bash
# 在项目目录
cd api/Edu_AI
start_api.bat  # Windows

# 测试项目API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "你好"}'
```

## 🔧 常用管理命令

```bash
# 查看服务状态
sudo systemctl status qwen-api

# 启动服务
sudo systemctl start qwen-api

# 停止服务
sudo systemctl stop qwen-api

# 重启服务
sudo systemctl restart qwen-api

# 查看日志
sudo journalctl -u qwen-api -f

# 查看最近100行日志
sudo journalctl -u qwen-api -n 100
```

## ⚠️ 注意事项

1. **IP地址**: 
   - 如果客户端在同一内网，使用 `192.168.1.51`
   - 如果使用VPN或其他网络，可能需要使用 `10.10.10.205`

2. **首次加载**: 模型首次加载需要几分钟，请耐心等待

3. **GPU显存**: 确保A100有足够显存（Qwen2-7B需要约14-16GB）

4. **防火墙**: 确保8000端口已开放

## 🐛 故障排查

### 模型加载失败

```bash
# 检查GPU
nvidia-smi

# 检查模型路径
ls -la /home/llm/models/huggingface/Qwen2-7B

# 查看详细错误日志
sudo journalctl -u qwen-api -n 50
```

### 连接失败

```bash
# 检查服务是否运行
sudo systemctl status qwen-api

# 检查端口
netstat -tulpn | grep 8000

# 测试本地连接
curl http://localhost:8000/health
```

## 📚 相关文档

- [完整集成指南](./COMPLETE_INTEGRATION_GUIDE.md)
- [FastAPI部署文档](./FASTAPI_SERVER_DEPLOYMENT.md)
- [快速部署](./QUICK_DEPLOY.md)

