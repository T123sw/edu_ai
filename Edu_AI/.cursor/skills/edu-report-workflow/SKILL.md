---
name: edu-report-workflow
description: 管理报告模式完整状态机（extractor/evaluator/ask/outline/generate），确保“先补槽位、后出大纲、确认后正文”。
version: 2.0.0
owner: edu-ai-backend
---

# 报告工作流技能（Report Workflow）

## 1. 技能目标

在报告模式下，保证流程严格为：
1) 提取槽位（extractor）
2) 评估缺失（evaluator）
3) 缺失则追问（ask）
4) 齐备则大纲（outline）
5) 用户确认后生成正文（generate）

---

## 2. 核心槽位定义

关键槽位：
- topic
- period
- outcomes
- issues
- next_plan

补充槽位：
- audience
- goal
- length
- format

---

## 3. 输入契约

```json
{
  "question": "用户输入",
  "report_meta": {"is_report": true},
  "report_slots": {},
  "report_missing": [],
  "report_outline_pending": false,
  "report_ask_counts": {}
}
```

---

## 4. 输出契约

```json
{
  "response_type": "ask|outline|generate",
  "report_slots": {},
  "report_missing": [],
  "report_outline": [],
  "report_ready": true
}
```

---

## 5. 节点执行规范

### extractor
- 从历史与本轮输入提取新增槽位
- 保留已有槽位，不做破坏性覆盖
- 若处于 `outline_pending`，优先识别用户是否确认大纲

### evaluator
- 缺槽位则设 `response_type=ask`
- 槽位齐全先 `outline`
- 已有大纲且用户确认后 `generate`

### ask
- 每轮只追问一个最高价值缺失点
- 回显已知信息，避免反复问同一内容

### outline
- 输出结构化大纲（3-6章，每章2-3点）
- 若用户修改，进行局部编辑而非全量重写

### generate
- 严格按大纲顺序生成正文
- 若用户不耐烦且触发 auto_fill，允许兜底后生成

---

## 6. Do / Don't

### Do
- 严格执行“先大纲后正文”
- 明确记录 ask 次数，避免无限追问
- 兜底填充时保持语义合理

### Don't
- 不跳过确认直接生成正文
- 不丢失历史槽位
- 不让追问一次问多个槽位

---

## 7. Few-shot 示例

### 示例1：缺失槽位
输入："帮我写课程总结报告"
输出：`response_type=ask`，优先问 `topic` 或 `period`。

### 示例2：槽位齐全
输入："主题是函数单元复习，周期是第5-6周，成效是..."
输出：`response_type=outline` 并返回章节化大纲。

### 示例3：确认大纲
输入："就按这个大纲生成"
输出：`response_type=generate`，按大纲生成正文。

---

## 8. Fallback 策略

- structured_output 失败：回退 JSON 提取
- 大纲解析失败：启用模板化兜底大纲
- 用户催促且信息不足：auto_fill 后生成

---

## 9. 审计字段

必须可追踪：
- `extractor_reason/source/override_applied`
- `outline_reason/source/override_applied`
- `generate_reason/source/override_applied`

---

## 10. 质量检查清单

- [ ] 槽位合并无破坏
- [ ] ask 次数受控
- [ ] 大纲确认门禁生效
- [ ] 正文严格遵循大纲
- [ ] 审计字段完整

---

## 11. 变更日志（v2.1）

### v2.1.0
- 新增节点审计统一格式：`reason / override_applied / route_source`。
- 明确 outline/generate 的 override 场景（改纲、auto_fill）。
- 强化“先大纲后正文”门禁描述，避免流程越级。
