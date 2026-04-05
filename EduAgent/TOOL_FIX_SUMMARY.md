# 深度搜索工具调用问题分析与修复总结

## 问题诊断

根据终端输出和代码分析，发现以下问题：

### 1. **"工具调用失败"的误解**
- **现象**: 日志中频繁出现 `[thought]工具调用/结构化输出失败`
- **真相**: 这不是真正的工具执行失败，而是 **LLM 结构化输出（JSON Schema）解析失败**
- **影响**: Agent 仍能继续执行，但思考质量下降

### 2. **搜索工具返回不相关结果**
- **现象**: `web_search` 返回 Bing 自身页面或完全不相关的内容
- **原因**: 
  - Bing HTML 解析的选择器可能已失效（页面结构变化）
  - 返回的链接包含 `javascript:void(0)` 等无效链接
  - 没有正确过滤 Bing 内部链接

### 3. **结构化输出兼容性问题**
- **现象**: DeepSeek 模型通过 `llmapi.blsc.cn` 接口时，`with_structured_output(Thought, method='json_schema')` 经常失败
- **影响**: Agent 无法正常进行思考，频繁进入兜底逻辑

## 已实施的修复

### 1. 改进 Bing HTML 解析 (`tools/search/websearch.py`)
- ✅ 添加多种选择器尝试（`li.b_algo`, `ol#b_results > li`, `.b_algo`, `.b_algoSlug`）
- ✅ 增强链接过滤逻辑（过滤 `javascript:`, `void(0)`, Bing 内部链接）
- ✅ 添加备用提取逻辑（当标准选择器失败时，从页面提取所有外部链接）

### 2. 优先使用 DuckDuckGo (`tools/search/websearch.py`)
- ✅ 将 DuckDuckGo 设为优先搜索源（HTML 结构更稳定）
- ✅ 改进 DuckDuckGo 解析逻辑，支持多种选择器
- ✅ 增强链接验证（确保是有效的 HTTP/HTTPS 外部链接）

### 3. 恢复结构化输出逻辑 (`o_agent/base_agent.py`)
- ✅ 恢复原始的 `thought_node` 实现（使用 `with_structured_output`）
- ✅ 保留兜底机制（连续失败时使用默认思考文本）

## 待测试项目

1. **搜索工具测试**
   ```bash
   cd D:\Edu_AI_1\EduAgent
   python -B test_web_search_debug.py
   ```
   - 验证是否能返回相关的外部链接
   - 检查结果质量

2. **完整流程测试**
   ```bash
   python -B run_deepsearch_once.py
   ```
   - 观察是否仍频繁出现"结构化输出失败"
   - 检查最终返回的链接是否相关

3. **结构化输出测试**
   - 考虑改用 `method='pydantic'` 或普通文本解析
   - 如果问题持续，可能需要调整 prompt 或使用更兼容的模型

## 建议的后续优化

1. **使用 SearxNG 本地实例**（如果可用）
   - 配置 `config.toml` 中的 SearxNG 端点
   - 或使用 Docker 启动本地 SearxNG: `docker run -d -p 8090:8080 searxng/searxng`

2. **改进结构化输出兼容性**
   - 尝试使用 `method='pydantic'` 替代 `json_schema`
   - 或改用普通 LLM 调用 + 文本解析 JSON

3. **添加搜索质量监控**
   - 记录搜索结果的来源（Bing/DDG/SearxNG）
   - 统计结构化输出成功率
   - 记录 Agent 执行步数

## 关键代码位置

- **搜索工具**: `tools/search/websearch.py`
  - `_fallback_bing_html()`: Bing HTML 解析
  - `_fallback_ddg_html()`: DuckDuckGo HTML 解析
  - `web_search()`: LangChain 工具包装

- **Agent 思考节点**: `o_agent/base_agent.py`
  - `thought_node()`: 结构化输出逻辑

- **深度搜索入口**: `deepsearch.py`
  - `deepsearch_large_llm()`: 主函数

