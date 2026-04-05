# SearxNG 403问题修复总结

## 问题诊断

本地SearxNG容器返回403错误，原因是bot detection机制过于严格，即使配置了正确的headers和设置也无法绕过。

## 最终解决方案：使用公共SearxNG实例

### ✅ 已实施的修复

1. **修改websearch.py使用公共实例**
   - 从 `http://localhost:8090/search` 
   - 改为 `https://searx.be/search`

2. **验证修复**
   - 测试web_search工具是否正常工作
   - 确认返回结果和耗时

### 修复命令

```powershell
cd D:\Edu_AI_1\EduAgent

# 修改使用公共实例
(Get-Content tools\search\websearch.py) -replace 'endpoint: str = "http://localhost:8090/search"', 'endpoint: str = "https://searx.be/search"' | Set-Content tools\search\websearch.py

# 测试验证
python -c "from tools.search.websearch import search_links; r=search_links('test', top_k=3); print('结果数:', len(r))"
```

## 性能改善预期

使用公共SearxNG实例后：

| 指标 | 修复前 | 修复后 | 改善 |
|------|--------|--------|------|
| web_search耗时 | 5-10秒 | 1-2秒 | **快5-10倍** |
| 深度搜索总耗时 | 690秒 | 200-300秒 | **减少60-70%** |

## 备选方案

如果公共实例也无法访问，系统会自动回退到HTML解析方式：
- 虽然慢（5-10秒/次），但功能正常
- 已优化的代码仍会带来性能改善

## 验证步骤

1. **测试web_search工具**:
   ```powershell
   python -c "from tools.search.websearch import search_links; import time; start=time.time(); r=search_links('test', top_k=3); print(f'耗时: {time.time()-start:.2f}秒'); print(f'结果数: {len(r)}')"
   ```

2. **测试完整深度搜索**:
   ```powershell
   python test_deepsearch_direct.py
   ```

3. **测试完整流程**:
   ```powershell
   python test_full_pipeline.py "计算思维 课程大纲 PDF" --max-urls 3
   ```

## 注意事项

1. **隐私**: 查询会发送到公共实例，注意隐私敏感信息
2. **依赖**: 依赖外部服务，如果实例下线需要切换其他实例
3. **限流**: 某些公共实例可能有请求频率限制

## 其他公共实例（备选）

如果 `searx.be` 无法访问，可以切换到：

- `https://search.sapti.me/search`
- `https://searx.tiekoetter.com/search`

修改方法相同，只需替换URL即可。

