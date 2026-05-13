# 端口8000被占用问题解决

## ❌ 错误信息

```
ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8000): address already in use
```

## 🔍 问题原因

端口8000已被其他进程占用。可能是：
- 之前启动的服务仍在运行
- 其他应用占用了该端口

## ✅ 解决方案

### 方案1：停止占用端口的进程（推荐）

#### 在服务器上执行：

```bash
# 查找占用端口的进程
lsof -i :8000
# 或
netstat -tulpn | grep 8000

# 停止进程（替换PID为实际进程ID）
kill -9 <PID>

# 或使用提供的脚本
chmod +x scripts/kill_port.sh
./scripts/kill_port.sh
```

#### 如果使用systemd服务：

```bash
# 停止服务
sudo systemctl stop qwen-api

# 检查状态
sudo systemctl status qwen-api
```

### 方案2：使用其他端口

#### 修改服务器端配置

编辑 `~/api-service/.env`：

```env
PORT=8001  # 改为其他端口
```

#### 修改客户端配置

编辑 `api/Edu_AI/.env`：

```env
REMOTE_MODEL_API_BASE=http://192.168.1.51:8001/v1
```

### 方案3：检查并停止所有相关进程

```bash
# 查找所有Python进程
ps aux | grep python

# 查找所有uvicorn进程
ps aux | grep uvicorn

# 停止所有Python进程（谨慎使用）
pkill -f "server_model_api.py"
pkill -f "uvicorn"
```

## 🔧 快速修复命令

### 一键停止占用进程

```bash
# 方法1: 使用fuser
sudo fuser -k 8000/tcp

# 方法2: 使用lsof
sudo kill -9 $(lsof -t -i:8000)

# 方法3: 使用netstat（需要root）
sudo kill -9 $(netstat -tlnp | grep :8000 | awk '{print $7}' | cut -d'/' -f1)
```

### 检查端口占用

```bash
# 使用提供的检查脚本
chmod +x scripts/check_port.sh
./scripts/check_port.sh
```

## 📝 完整解决步骤

### 步骤1：停止占用进程

```bash
# 在服务器上
cd ~/api-service

# 查找进程
lsof -i :8000

# 停止进程（假设PID是12345）
kill -9 12345
```

### 步骤2：验证端口已释放

```bash
# 检查端口
lsof -i :8000
# 应该没有输出
```

### 步骤3：重新启动服务

```bash
# 如果使用systemd
sudo systemctl start qwen-api

# 或手动启动
source venv/bin/activate
python server_model_api.py
```

## ⚠️ 注意事项

1. **不要强制杀死重要进程**：确认进程ID后再停止
2. **systemd服务**：如果使用systemd，优先使用systemctl命令
3. **端口选择**：如果8000端口被系统服务占用，考虑使用其他端口

## 🔍 常见占用原因

1. **之前的服务未正确关闭**
2. **systemd服务仍在运行**
3. **多个实例同时运行**
4. **其他应用占用端口**

## ✅ 验证

端口释放后，重新启动服务应该看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

而不是端口占用错误。

