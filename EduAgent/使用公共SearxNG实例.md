# 使用公共SearxNG实例修复403问题

## 问题

本地SearxNG容器返回403错误，即使配置了正确的headers和设置。

## 解决方案：使用公共SearxNG实例

### 步骤1: 修改websearch.py

编辑 `tools/search/websearch.py`，找到 `search` 函数，修改默认endpoint：

```python
# 原代码（第145行左右）
endpoint: str = "http://localhost:8090/search",

# 改为使用公共实例
endpoint: str = "https://searx.be/search",
```

### 步骤2: 可选 - 添加多个公共实例作为备选

可以修改代码支持多个公共实例，自动切换：

```python
# 公共SearxNG实例列表
PUBLIC_SEARXNG_INSTANCES = [
    "https://searx.be/search",
    "https://search.sapti.me/search",
    "https://searx.tiekoetter.com/search",
]

# 在search函数中，尝试每个实例直到成功
```

### 步骤3: 停止本地SearxNG容器（可选）

如果不再使用本地实例：

```powershell
docker stop searxng
docker rm searxng
```

## 推荐的公共SearxNG实例

| 实例 | URL | 状态 |
|------|-----|------|
| searx.be | https://searx.be | 稳定 |
| search.sapti.me | https://search.sapti.me | 稳定 |
| searx.tiekoetter.com | https://searx.tiekoetter.com | 稳定 |

## 快速修复命令

### 方法1: 直接修改文件

```powershell
cd D:\Edu_AI_1\EduAgent

# 使用PowerShell替换
(Get-Content tools\search\websearch.py) -replace 'endpoint: str = "http://localhost:8090/search"', 'endpoint: str = "https://searx.be/search"' | Set-Content tools\search\websearch.py
```

### 方法2: 手动编辑

1. 打开 `tools/search/websearch.py`
2. 找到 `endpoint: str = "http://localhost:8090/search",`
3. 改为 `endpoint: str = "https://searx.be/search",`
4. 保存文件

## 验证修复

```powershell
# 测试web_search工具
python -c "from tools.search.websearch import search_links; import time; start=time.time(); r=search_links('test', top_k=3); print(f'耗时: {time.time()-start:.2f}秒'); print(f'结果数: {len(r)}'); print('前3个:', r[:3] if r else '无结果')"
```

**预期结果**:
- ✅ 耗时: 1-2秒（比HTML解析快5-10倍）
- ✅ 结果数: 3
- ✅ 返回正常的搜索结果

## 优势

1. **无需配置**: 公共实例已配置好，无需bot detection配置
2. **更稳定**: 公共实例通常更稳定，有维护团队
3. **更快**: 直接使用API，比HTML解析快5-10倍
4. **简单**: 只需修改一行代码

## 注意事项

1. **隐私**: 查询会发送到公共实例，注意隐私敏感信息
2. **依赖**: 依赖外部服务，如果实例下线需要切换
3. **限流**: 某些公共实例可能有请求频率限制

## 如果公共实例也无法访问

可以回退到HTML解析方式（当前方案）：
- 虽然慢（5-10秒/次），但功能正常
- 已优化的代码仍会带来性能改善

## 完整修复流程

```powershell
# 1. 修改websearch.py使用公共实例
cd D:\Edu_AI_1\EduAgent
(Get-Content tools\search\websearch.py) -replace 'endpoint: str = "http://localhost:8090/search"', 'endpoint: str = "https://searx.be/search"' | Set-Content tools\search\websearch.py

# 2. 测试验证
python -c "from tools.search.websearch import search_links; r=search_links('test', top_k=3); print('结果数:', len(r))"

# 3. 如果成功，测试完整流程
python test_deepsearch_direct.py
```

## 预期性能改善

使用公共SearxNG实例后：
- **web_search**: 从5-10秒降到1-2秒（快5-10倍）
- **深度搜索总耗时**: 从690秒降到200-300秒（减少60-70%）

