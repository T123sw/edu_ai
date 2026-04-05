# SearxNG 403错误修复 - 简化方案

## 问题

SearxNG返回403错误，原因是bot detection机制。

## 简化修复方案

由于limiter.toml格式复杂，采用更简单的方案：

### 方案1: 确保headers正确（已实现）

`tools/search/websearch.py` 已确保发送正确的headers：
- `X-Forwarded-For: 127.0.0.1`
- `X-Real-IP: 127.0.0.1`
- 完整的User-Agent

### 方案2: 使用公共SearxNG实例（推荐）

如果本地SearxNG持续有问题，可以使用公共实例：

**修改 `tools/search/websearch.py`**:

```python
# 在search函数中，修改默认endpoint
endpoint = "https://searx.be/search"  # 或其他公共实例
```

**公共SearxNG实例列表**:
- `https://searx.be`
- `https://search.sapti.me`
- `https://searx.tiekoetter.com`

### 方案3: 接受HTML解析方式（当前可用）

虽然慢，但功能正常：
- Bing HTML解析: 5-10秒/次
- DuckDuckGo HTML解析: 5-10秒/次
- 已优化的代码仍会带来性能改善

## 快速修复命令

### 如果使用本地SearxNG:

```powershell
cd D:\Edu_AI_1\EduAgent

# 重启容器
docker stop searxng
docker rm searxng
docker-compose -f docker-compose.searxng.yml up -d

# 等待启动
Start-Sleep -Seconds 20

# 测试
python check_services.py
```

### 如果改用公共实例:

编辑 `tools/search/websearch.py`，找到 `search` 函数，修改：

```python
# 原代码
endpoint: str = "http://localhost:8090/search",

# 改为
endpoint: str = "https://searx.be/search",
```

## 验证修复

```powershell
# 测试web_search工具
python -c "from tools.search.websearch import search_links; import time; start=time.time(); r=search_links('test', top_k=3); print(f'耗时: {time.time()-start:.2f}秒'); print(f'结果数: {len(r)}')"
```

**预期**:
- SearxNG正常: 1-2秒
- SearxNG失败（HTML解析）: 5-10秒

## 当前状态

即使SearxNG返回403，系统仍可正常工作：
- ✅ 自动回退到Bing/DDG HTML解析
- ✅ 功能正常，只是稍慢
- ✅ 已优化的代码会带来性能改善

## 建议

**短期**: 接受HTML解析方式，功能正常可用

**长期**: 
1. 使用公共SearxNG实例
2. 或使用SerpAPI（需要API密钥）
3. 或深入研究SearxNG bot detection配置

