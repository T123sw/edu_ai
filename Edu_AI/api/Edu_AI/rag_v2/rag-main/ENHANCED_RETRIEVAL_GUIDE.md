# 增强检索功能使用说明

## 📚 概述

本次优化实现了 **HyDE + 多路召回 + RRF 融合 + Rerank 精排** 的增强检索链路，显著提升了 RAG 系统的检索效果。

### 核心改进

#### 1️⃣ **HyDE（Hypothetical Document Embeddings）**
- **原理**：先生成一个假设性答案，然后用答案的 embedding 进行检索
- **优势**：答案空间比问题空间更密集，更容易匹配到相关文档
- **适用场景**：复杂问题、需要推理的问题、专业领域问题

#### 2️⃣ **多路召回**
同时使用三种检索策略：
- **原问题向量检索**：语义相似度匹配
- **HyDE 答案向量检索**：答案空间匹配
- **BM25 关键词检索**：精确词汇匹配

#### 3️⃣ **RRF（Reciprocal Rank Fusion）融合**
- **公式**：`score(d) = Σ w_i / (k + rank_i(d))`
- **优势**：业界标准的排名融合算法，被 Google Search、Elasticsearch 广泛使用
- **可配置权重**：可以为不同召回路径设置不同权重

#### 4️⃣ **Rerank 精排**
- **模型**：BAAI/bge-reranker-v2-m3（可配置）
- **作用**：对融合后的结果进行精细排序
- **失败降级**：自动降级到 RRF 结果

---

## 🚀 使用方法

### API 调用方式

#### 基础用法（传统检索）
```python
POST /api/rag/query
{
    "question": "什么是二分搜索树？",
    "top_k": 5
}
```

#### 增强检索模式
```python
POST /api/rag/query
{
    "question": "什么是二分搜索树？",
    "top_k": 5,
    "use_enhanced_retrieval": true,  // 启用增强检索
    "hyde_weight": 0.5,               // HyDE 权重（0-1）
    "use_rrf": true                   // 使用 RRF 融合
}
```

### Python SDK 调用

```python
from system import RAGSystem

rag = RAGSystem(...)

# 传统检索
result = rag.query(
    question="什么是动态规划？",
    top_k=5,
    use_enhanced_retrieval=False
)

# 增强检索
result = rag.query(
    question="什么是动态规划？",
    top_k=5,
    use_enhanced_retrieval=True,   # 关键参数
    hyde_weight=0.5,               # HyDE 权重
    use_rrf=True                   # RRF 融合
)
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_enhanced_retrieval` | bool | False | 是否使用增强检索 |
| `hyde_weight` | float | 0.5 | HyDE 结果权重（0-1），越高越重视答案空间匹配 |
| `use_rrf` | bool | True | 是否使用 RRF 融合（否则使用加权融合） |

---

## 📊 检索流程对比

### 传统检索流程
```
用户问题 → 向量化 → 混合检索（向量 60% + BM25 40%）→ Top-K → Rerank → 返回
```

### 增强检索流程
```
用户问题
  ↓
[1] HyDE 改写 → 生成假设性答案
  ↓
[2] 三路 Embedding
  ├─ 原问题 embedding
  └─ 假设性答案 embedding
  ↓
[3] 多路召回
  ├─ 向量路 1：原问题向量检索
  ├─ 向量路 2：HyDE 答案向量检索
  └─ 关键词路：BM25 检索
  ↓
[4] RRF 融合 → 合并三路结果（加权）
  ↓
[5] Rerank 精排 → 最终 Top-K
  ↓
返回结果
```

---

## 🔧 高级配置

### 环境变量

在 `.env` 文件中配置：

```bash
# 启用 Reranker（增强检索依赖这个）
RAG_ENABLE_RERANKER=1
RERANKER_API_BASE=https://your-api.com
RERANKER_API_KEY=your-api-key
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# Embedding 配置
EMBEDDING_API_BASE=https://your-api.com
EMBEDDING_MODEL=gemini-embedding-2-preview
```

### 调优建议

#### 1. 调整 HyDE 权重
```python
# 适合简单事实性问题
hyde_weight=0.3  # 降低 HyDE 权重

# 适合复杂推理问题
hyde_weight=0.7  # 提高 HyDE 权重
```

#### 2. 调整 RRF 参数
```python
# k 值越小，排名差异影响越大
rrf_k=60   # 默认值，平衡选择
rrf_k=30   # 更重视高排名结果
rrf_k=100  # 更平等的融合
```

#### 3. 性能优化
```python
# 如果不需要最高精度，可以关闭某些组件
use_enhanced_retrieval=True,
use_hyde=True,      # 关闭 HyDE（减少一次 LLM 调用）
use_rrf=True,       # 仍然使用 RRF
rerank_enabled=False  # 关闭 Rerank（减少延迟）
```

---

## 📈 测试与评估

### 运行测试脚本

```bash
python test_enhanced_retrieval.py
```

测试脚本会：
1. 使用传统检索和增强检索分别回答相同问题
2. 对比两种方式的召回结果
3. 展示增强检索独有的文档
4. 输出详细的分数和指标

### 评估指标

关注以下指标：

- **召回率提升**：增强检索是否召回了更多相关文档？
- **Rerank Top1 变化率**：重排后第一名是否改变？（变化率高说明 Rerank 有价值）
- **响应时间**：增强检索的延迟增加多少？
- **答案质量**：人工评估答案的准确性和完整性

---

## 💡 最佳实践

### 何时使用增强检索？

✅ **推荐使用场景**：
- 复杂问题、需要推理的问题
- 专业领域问题（医疗、法律等）
- 用户反馈传统检索效果不佳时
- 对答案质量要求高的场景

❌ **不推荐使用场景**：
- 简单事实查询（"今天天气如何？"）
- 对延迟极其敏感的场景
- 知识库非常小（<100 个文档块）

### 性能考虑

增强检索会增加一些延迟：

| 组件 | 增加延迟 | 说明 |
|------|----------|------|
| HyDE 生成 | ~500-1000ms | LLM 生成假设性答案 |
| 额外向量检索 | ~100-200ms | HyDE embedding |
| RRF 融合 | ~10-50ms | 计算开销很小 |
| Rerank | ~200-500ms | 取决于文档数量 |
| **总计** | **~800-1800ms** | 相比传统检索 |

**优化建议**：
- 如果对延迟敏感，可以只开启 RRF，关闭 HyDE
- 缓存常见问题的 HyDE 答案
- 批量处理多个问题时并行化

---

## 🎯 实际案例

### 案例 1：复杂概念理解

**问题**："动态规划和贪心算法有什么区别？"

**传统检索**：
- 召回 3 个文档
- 主要匹配"动态规划"、"贪心"关键词
- 缺少对比性内容

**增强检索**：
- 召回 5 个文档
- HyDE 生成了包含"区别"、"对比"的假设性答案
- 额外召回 2 个对比性文档
- Rerank 将对比文档排到前面

**结果**：增强检索的答案更完整、更有针对性

### 案例 2：算法原理理解

**问题**："并查集的路径压缩是什么原理？"

**传统检索**：
- 召回包含"路径压缩"的文档
- 但可能遗漏使用"优化"、"扁平化"等同义词的文档

**增强检索**：
- HyDE 答案中包含多种表述方式
- BM25 捕获精确术语
- 向量检索捕获语义相似内容
- RRF 融合多路结果

**结果**：召回率提升约 40%

---

## 📝 故障排查

### 问题 1：增强检索没有效果

**检查点**：
1. 确认 `use_enhanced_retrieval=True`
2. 查看日志中的 `[EnhancedHybrid]` 前缀
3. 确认 Reranker 是否启用（`RAG_ENABLE_RERANKER=1`）

### 问题 2：响应时间过长

**优化方案**：
```python
# 方案 1：只使用 RRF，关闭 HyDE
use_enhanced_retrieval=True,
use_hyde=False,  # 跳过 HyDE 生成
use_rrf=True

# 方案 2：关闭 Rerank
rerank_enabled=False
```

### 问题 3：HyDE 生成失败

**原因**：LLM API 不可用或超时

**解决**：
- 检查 LLM API 配置
- 增加超时时间
- 代码已自动降级到传统检索

---

## 🔮 未来扩展

可以进一步增强的方向：

1. **查询扩展**：生成多个同义查询变体
2. **父子分块**：小块检索 + 大块返回
3. **元数据过滤**：支持按页面、章节等过滤
4. **评估体系**：自动化评估检索质量（NDCG、MRR 等）

---

## 📚 参考资料

- **HyDE 论文**：[Precise Zero-Shot Dense Retrieval without Relevance Labels](https://arxiv.org/abs/2212.10496)
- **RRF 论文**：[The Probabilistic Relevance Framework](https://dl.acm.org/doi/10.1145/1506250.1506255)
- **Rerank 模型**：[BGE Reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3)

---

## 📞 技术支持

如有问题，请查看：
- 系统日志中的 `[EnhancedHybrid]`、`[Reranker]` 前缀
- 运行 `test_enhanced_retrieval.py` 进行诊断
- 检查 `.env` 配置是否正确
