# A100服务器模型部署指南

## 📋 服务器信息

- **服务器类型**: A100 GPU服务器
- **模型路径**: `/home/llm/models/huggingface/Qwen2-7B`
- **模型格式**: HuggingFace格式

## 🎯 部署方案

### 方案一：使用vLLM部署（推荐，性能最佳）

vLLM是专为GPU优化的高性能推理框架，特别适合A100服务器。

#### 1. 安装vLLM

在服务器上安装vLLM：

```bash
# 创建虚拟环境（可选）
python -m venv vllm_env
source vllm_env/bin/activate

# 安装vLLM（支持CUDA）
pip install vllm
# 或从源码安装最新版本
# pip install git+https://github.com/vllm-project/vllm.git
```

#### 2. 启动vLLM服务

```bash
# 基础启动命令
python -m vllm.entrypoints.openai.api_server \
  --model /home/llm/models/huggingface/Qwen2-7B \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1

# 完整参数示例（A100优化）
python -m vllm.entrypoints.openai.api_server \
  --model /home/llm/models/huggingface/Qwen2-7B \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.9 \
  --max-model-len 4096 \
  --trust-remote-code \
  --served-model-name Qwen2-7B
```

#### 3. 参数说明

| 参数 | 说明 | 推荐值（A100） |
|------|------|---------------|
| `--model` | 模型路径 | `/home/llm/models/huggingface/Qwen2-7B` |
| `--host` | 监听地址 | `0.0.0.0`（允许外部访问） |
| `--port` | 监听端口 | `8000` |
| `--tensor-parallel-size` | 张量并行大小 | `1`（单卡）或 `2`（双卡） |
| `--gpu-memory-utilization` | GPU内存利用率 | `0.9`（使用90%显存） |
| `--max-model-len` | 最大序列长度 | `4096` 或 `8192` |
| `--trust-remote-code` | 信任远程代码 | 如果需要（Qwen模型可能需要） |

#### 4. 测试服务

```bash
# 查看可用模型
curl http://localhost:8000/v1/models

# 测试对话
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 方案二：使用text-generation-inference (TGI)

TGI是HuggingFace官方的推理服务框架。

#### 1. 使用Docker部署（推荐）

```bash
# 拉取TGI镜像
docker pull ghcr.io/huggingface/text-generation-inference:latest

# 启动服务
docker run --gpus all \
  -p 8000:80 \
  -v /home/llm/models/huggingface:/data \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id /data/Qwen2-7B \
  --num-shard 1 \
  --port 80
```

### 方案三：使用FastAPI + transformers（灵活但性能较低）

如果前两种方案不适合，可以使用自定义API服务。

## 📝 客户端配置

### 1. 配置项目连接

编辑 `api/Edu_AI/.env` 文件：

```env
# vLLM服务器地址（替换为您的服务器IP）
REMOTE_MODEL_API_BASE=http://your-server-ip:8000/v1

# 模型名称（与vLLM启动时的served-model-name一致）
LLM_MODEL=Qwen2-7B

# 使用OpenAI兼容模式
DEFAULT_MODEL_TYPE=openai

# 嵌入模型配置（如果也在服务器上）
DEFAULT_EMBEDDING_TYPE=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

### 2. 获取服务器IP

```bash
# 在服务器上查看IP
ip addr show
# 或
hostname -I
```

## 🔧 高级配置

### 多GPU配置（如果有多张A100）

```bash
# 使用2张GPU
python -m vllm.entrypoints.openai.api_server \
  --model /home/llm/models/huggingface/Qwen2-7B \
  --tensor-parallel-size 2 \
  --host 0.0.0.0 \
  --port 8000
```

### 量化部署（节省显存）

```bash
# 使用AWQ量化
python -m vllm.entrypoints.openai.api_server \
  --model /home/llm/models/huggingface/Qwen2-7B \
  --quantization awq \
  --host 0.0.0.0 \
  --port 8000
```

### 配置systemd服务（后台运行）

创建服务文件 `/etc/systemd/system/vllm.service`：

```ini
[Unit]
Description=vLLM API Server
After=network.target

[Service]
Type=simple
User=llm
WorkingDirectory=/home/llm
Environment="PATH=/home/llm/vllm_env/bin"
ExecStart=/home/llm/vllm_env/bin/python -m vllm.entrypoints.openai.api_server \
  --model /home/llm/models/huggingface/Qwen2-7B \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable vllm
sudo systemctl start vllm
sudo systemctl status vllm
```

## 🔍 验证部署

### 1. 检查服务运行

```bash
# 查看进程
ps aux | grep vllm

# 查看端口
netstat -tulpn | grep 8000

# 查看日志
journalctl -u vllm -f  # systemd服务
# 或查看vLLM输出日志
```

### 2. 测试API

```bash
# 健康检查
curl http://your-server-ip:8000/health

# 列出模型
curl http://your-server-ip:8000/v1/models

# 测试对话
curl http://your-server-ip:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-7B",
    "messages": [{"role": "user", "content": "你好，请介绍一下自己"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### 3. 在项目中测试

启动项目API服务后：

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "你好",
    "model_type": "openai",
    "api_base": "http://your-server-ip:8000/v1",
    "model_name": "Qwen2-7B"
  }'
```

## ⚠️ 注意事项

### 防火墙配置

确保服务器防火墙允许访问8000端口：

```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

### 权限配置

确保模型文件可读：

```bash
# 检查权限
ls -la /home/llm/models/huggingface/Qwen2-7B

# 如果需要，修改权限
chmod -R 755 /home/llm/models/huggingface/Qwen2-7B
```

### GPU显存管理

- 监控GPU使用：`nvidia-smi`
- 根据显存大小调整 `--gpu-memory-utilization`
- Qwen2-7B大约需要14-16GB显存

## 📊 性能优化建议

1. **使用vLLM**: 专为GPU优化，性能最佳
2. **量化模型**: 使用AWQ或GPTQ量化可节省显存
3. **批处理**: vLLM自动批处理，提高吞吐量
4. **调整参数**: 根据实际需求调整 `max-model-len` 和 `gpu-memory-utilization`

## 🔗 相关文档

- [vLLM官方文档](https://docs.vllm.ai/)
- [TGI官方文档](https://huggingface.co/docs/text-generation-inference)
- [项目配置指南](./OPENAI_COMPATIBLE_SETUP.md)

