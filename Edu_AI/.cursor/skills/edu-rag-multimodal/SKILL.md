---
name: edu-rag-multimodal
description: 负责检索增强回答、多工具协调、图片注入与最终模型选择。遵循“文本默认 deep，命中图片或视频证据走 qwen”。
version: 2.0.0
owner: edu-ai-backend
---

# 教育RAG多模态技能（RAG Multimodal）

## 1. 技能目标

在普通问答/研究问答场景下，完成：
- RAG 工具调用
- deepsearch 工具调用
- 图片证据注入（最多3张）
- 终答模型选择（deep / qwen）
- 输出审计字段（模型与路径）

---

## 2. 输入契约

```json
{
  "question": "用户问题",
  "rag_tool_enabled": true,
  "deepsearch_tool_enabled": false,
  "selected_doc_ids": [],
  "video_hits": [],
  "messages": []
}
```

---

## 3. 输出契约

```json
{
  "final_answer": "最终回答",
  "final_answer_role": "deep|qwen_vlm",
  "final_answer_model": "模型名",
  "tool_calls": ["rag_search_tool"],
  "degraded": false
}
```

---

## 4. 工具调用顺序

1. 先让快速模型进行工具规划
2. 若没调用工具且 `deepsearch_tool_enabled=true`，强制 deepsearch
3. 若没调用工具且 `rag_tool_enabled=true` 且有 selected_doc_ids，强制 rag
4. 收集 tool message 中 sources，提取图片路径

---

## 5. 多模态注入规则

- 最多处理 3 张图片
- 每张图需通过：路径存在、可读、可编码
- 失败跳过，不得导致整轮失败
- 若 `injected_image_count > 0` 或 `video_hits 非空`，优先 `qwen_vlm`
- 否则使用 `deep`

---

## 6. 审计字段要求

必须记录：
- `sources_images`
- `injected`
- `final_answer_role`
- `final_answer_model`
- `degraded`

---

## 7. Do / Don't

### Do
- 先保证可回答，再追求多模态增强
- 一切失败都应降级到文本可用结果
- 强制工具调用要可追踪

### Don't
- 不要因单张坏图报错终止
- 不要在无证据时盲目切到视觉模型
- 不要丢失工具返回来源信息

---

## 8. Few-shot 示例

### 示例1：本地资料问答
输入："根据我上传的讲义解释布鲁姆目标分类"
输出要点：调用 `rag_search_tool`，若无图则 `deep` 输出。

### 示例2：含图片证据
输入："结合这几张示意图解释电路串并联"
输出要点：注入有效图片，`final_answer_role=qwen_vlm`。

### 示例3：视频片段辅助
输入："视频里老师讲到元认知那一段是什么意思"
输出要点：当 `video_hits` 存在，可直接走 qwen 终答并引用时间点。

---

## 9. Fallback 策略

- 工具失败：写入 tool error payload，继续流程
- 图片注入失败：走 deep 文本结果
- qwen 调用失败：回落已有文本草稿

---

## 10. 质量检查清单

- [ ] 工具命中逻辑符合开关
- [ ] 图片注入统计完整
- [ ] 模型选择符合规则
- [ ] 失败路径均可降级
- [ ] 审计字段完整可观测

---

## 11. 变更日志（v2.1）

### v2.1.0
- 明确 `qwen_vlm` 切换条件：图片注入成功或存在视频证据。
- 新增审计字段约束：终答模型与角色必须可追踪。
- 强化降级要求：任意多模态失败均回退文本可用答案。
