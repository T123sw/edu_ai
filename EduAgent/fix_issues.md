# 问题修复指南

## 问题1: 端口8848被占用

**错误信息**:
```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8848)
```

**解决方案**:

### 方案A: 关闭占用端口的进程（推荐）

```powershell
# 查看占用端口的进程
netstat -ano | findstr :8848

# 关闭进程（替换5780为实际的PID）
taskkill /F /PID 5780
```

### 方案B: 修改服务端口

编辑 `main.py`，修改最后一行：

```python
# 原代码
uvicorn.run(app, host="127.0.0.1", port=8848)

# 改为其他端口，如8849
uvicorn.run(app, host="127.0.0.1", port=8849)
```

**注意**: 如果修改端口，测试脚本中的URL也需要相应修改。

## 问题2: 爬虫模块导入失败

**错误信息**:
```
[WARNING] 无法导入爬虫模块: No module named 'automation_spider'
```

**原因**: 
- 路径配置问题
- 依赖模块未找到

**已修复**: 
- 已更新 `crawler_service.py` 中的路径配置
- 添加了多个路径以确保能找到所有依赖

**验证修复**:

```python
# 测试导入
cd D:\Edu_AI_1\EduAgent
python -c "from services.crawler_service import get_crawler_service; print('导入成功')"
```

如果仍然失败，检查：
1. `自动化爬虫/src/selenium_way/crawle_url.py` 是否存在
2. `自动化爬虫/src/selenium_way/setup.py` 是否存在
3. 依赖包是否安装（trafilatura, undetected-chromedriver等）

## 快速修复步骤

1. **关闭占用端口的进程**:
   ```powershell
   taskkill /F /PID 5780
   ```

2. **重新启动服务**:
   ```powershell
   cd D:\Edu_AI_1\EduAgent
   python main.py
   ```

3. **如果仍有导入问题，检查路径**:
   ```powershell
   # 验证路径
   Test-Path "D:\Edu_AI_1\自动化爬虫\src\selenium_way\crawle_url.py"
   ```

4. **测试API**:
   ```powershell
   python test_deepsearch_and_crawl.py "测试查询" 2
   ```

