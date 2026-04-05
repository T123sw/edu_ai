# SearxNG 403错误修复指南

## 问题诊断

从日志可以看到关键错误：
```
ERROR:searx.botdetection: X-Forwarded-For nor X-Real-IP header is set!
WARNING:searx.botdetection.config: missing config file: /etc/searxng/limiter.toml
```

**原因**: SearxNG的bot detection机制在检查请求headers，缺少必要的headers或配置导致返回403。

## 修复方案

### 方案1: 添加limiter.toml配置文件（推荐）

已创建 `searxng/limiter.toml` 文件，需要：
1. 更新docker-compose配置挂载此文件
2. 重启容器

**步骤**:
```powershell
cd D:\Edu_AI_1\EduAgent

# 1. 停止并删除现有容器
docker stop searxng
docker rm searxng

# 2. 使用更新后的docker-compose重新启动
docker-compose -f docker-compose.searxng.yml up -d

# 3. 等待10-15秒让容器完全启动
Start-Sleep -Seconds 15

# 4. 检查日志确认无错误
docker logs searxng --tail 20

# 5. 测试访问
python check_services.py
```

### 方案2: 确保web_search发送正确的headers

已更新 `tools/search/websearch.py`，确保发送：
- `X-Forwarded-For: 127.0.0.1`
- `X-Real-IP: 127.0.0.1`
- 完整的User-Agent

### 方案3: 使用环境变量禁用bot detection

已在docker-compose中添加：
```yaml
environment:
  - SEARXNG_BOT_DETECTION_ENABLED=false
```

## 完整修复步骤

### 步骤1: 停止现有容器

```powershell
cd D:\Edu_AI_1\EduAgent
docker stop searxng
docker rm searxng
```

### 步骤2: 使用更新后的配置启动

```powershell
docker-compose -f docker-compose.searxng.yml up -d
```

### 步骤3: 等待并验证

```powershell
# 等待容器启动
Start-Sleep -Seconds 15

# 查看日志
docker logs searxng --tail 20

# 测试访问
python check_services.py
```

### 步骤4: 测试搜索功能

```powershell
# 测试web_search工具
python -c "from tools.search.websearch import search_links; import time; start=time.time(); r=search_links('test', top_k=3); print(f'耗时: {time.time()-start:.2f}秒'); print(f'结果数: {len(r)}'); print('前3个:', r[:3])"
```

**预期结果**:
- 如果SearxNG正常: 耗时1-2秒，返回3个结果
- 如果SearxNG失败: 耗时5-10秒，使用HTML解析

## 验证修复

### 方法1: 使用检查脚本

```powershell
python check_services.py
```

应该看到：
```
[OK] SearxNG 服务正在运行
```

### 方法2: 直接测试API

```powershell
python -c "import requests; headers={'User-Agent': 'Mozilla/5.0', 'X-Forwarded-For': '127.0.0.1', 'X-Real-IP': '127.0.0.1', 'Accept': 'application/json'}; r=requests.get('http://localhost:8090/search?q=test&format=json', headers=headers, timeout=5); print('Status:', r.status_code); print('OK' if r.status_code == 200 else 'Failed')"
```

**预期**: Status: 200, OK

### 方法3: 测试web_search工具

```powershell
python -c "from tools.search.websearch import search_links; r=search_links('test', top_k=3); print('结果数:', len(r)); print('前3个:', r[:3] if r else '无结果')"
```

## 如果仍然返回403

### 备选方案1: 使用公共SearxNG实例

修改 `tools/search/websearch.py`:

```python
# 在search函数中，修改endpoint
endpoint = "https://searx.be/search"  # 或其他公共实例
```

### 备选方案2: 接受HTML解析方式

虽然慢，但功能正常。已优化的代码仍会带来性能改善。

### 备选方案3: 使用SerpAPI

需要API密钥，但更稳定快速。

## 快速修复命令（一键执行）

```powershell
cd D:\Edu_AI_1\EduAgent
docker stop searxng; docker rm searxng; docker-compose -f docker-compose.searxng.yml up -d; Start-Sleep -Seconds 15; python check_services.py
```

## 配置文件说明

### settings.yml
- 禁用limiter: `limiter: false`
- 允许JSON格式输出

### limiter.toml（新增）
- 禁用bot detection: `enabled = false`
- 禁用rate limiter: `enabled = false`

### docker-compose.searxng.yml（已更新）
- 挂载limiter.toml文件
- 添加环境变量禁用bot detection

## 预期效果

修复成功后：
- ✅ SearxNG返回200状态码
- ✅ web_search耗时从5-10秒降到1-2秒
- ✅ 深度搜索总耗时从690秒降到200-300秒

