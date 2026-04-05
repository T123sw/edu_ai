# SearxNG 403错误修复指南

## 问题

SearxNG容器运行但返回403错误，导致web_search使用慢速的HTML解析方式。

## 原因分析

1. **Bot Detection**: SearxNG默认启用bot detection，会拦截API请求
2. **配置问题**: settings.yml格式可能不正确
3. **Headers问题**: 请求headers可能不够完整

## 解决方案

### 方案1: 使用简化的配置文件（推荐）

已创建简化的`settings.yml`，只包含必要配置：
- 禁用limiter
- 设置secret_key
- 允许JSON格式

### 方案2: 如果SearxNG仍无法修复

可以暂时使用Bing/DDG HTML解析，虽然慢但可用。

**优化HTML解析**:
- 减少超时时间
- 优化选择器
- 并行处理

### 方案3: 使用其他搜索API

如果SearxNG持续有问题，可以考虑：
- SerpAPI（需要API密钥）
- 直接使用Bing API
- 使用DuckDuckGo API

## 验证修复

```powershell
# 1. 检查容器状态
docker ps | findstr searxng

# 2. 查看日志
docker logs searxng --tail 20

# 3. 测试访问
python check_services.py

# 4. 如果SearxNG正常，测试搜索
python -c "from tools.search.websearch import search_links; print(search_links('test', top_k=3))"
```

## 性能影响

- **SearxNG正常**: web_search ~1-2秒
- **SearxNG失败（HTML解析）**: web_search ~5-10秒
- **性能差异**: 5-10倍

## 当前状态

即使SearxNG无法修复，已完成的优化（减少重试次数、减少递归限制）仍会带来改善：
- 从690秒可能降到400-500秒

