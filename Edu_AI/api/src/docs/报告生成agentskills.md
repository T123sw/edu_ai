# 报告生成 AgentSkills 实施文档（v4.0 对齐版）

> 本文档对齐当前实际代码与技能文件，作为报告生成能力开发与优化的依据。  
> 目标：将报告流从“理念描述”升级为“可执行、可判定、可观测”的闭环技能。

---

## 0. 架构总览（当前真实形态）

### A. 主技能（Agent 维度）
- `edu-report-agent`：报告主技能（槽位提取、追问、大纲确认、正文生成提示词）

### B. 工作流技能（状态机）
- `edu-report-workflow`：报告模式完整流程（extractor → evaluator → ask → outline → generate）

### C. 编排技能
- `edu-orchestrator`
- `edu-agent-routing`

---

## 1. 报告流程（核心规范）

### 1.1 流程门禁（强约束）
1. 提取槽位（extractor）
2. 评估缺失（evaluator）
3. 缺失则追问（ask）
4. 槽位齐备则输出大纲（outline）
5. 用户确认后生成正文（generate）

> 禁止越级：未确认大纲不得生成正文。

---

## 2. 核心槽位定义

### 2.1 关键槽位
- `topic`
- `period`
- `outcomes`
- `issues`
- `next_plan`

### 2.2 补充槽位
- `audience`
- `goal`
- `length`
- `format`

---

## 3. 主技能输入 / 输出契约

## 3.1 输入契约（状态机核心字段）

```json
{
  "question": "string",
  "report_meta": {"is_report": true, "user_intent": "provide|modify|confirm_outline|force_generate"},
  "report_slots": {},
  "report_missing": [],
  "report_outline_pending": false,
  "report_ask_counts": {},
  "report_outline": []
}
```

## 3.2 输出契约（节点联动）

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

## 4. 主技能提示词（edu-report-agent）

### 4.1 报告追问
- `REPORT_DYNAMIC_ASK_SYSTEM_PROMPT`
  - 回显已知信息 + 单点追问 + 50~80字

### 4.2 正文生成
- `REPORT_GENERATE_PROMPT`
  - 依据槽位输出 Markdown 正文

### 4.3 任务状态追踪
- `TASK_STATE_MANAGER_PROMPT`
  - 结构化 JSON 输出增量字段
  - 仅在明确跳过时允许 `force_generate`

### 4.4 大纲确认意图
- `CONFIRM_OUTLINE_INTENT_PROMPT`
  - 识别用户是否确认大纲

### 4.5 需求提取
- `EXTRACTOR_SYSTEM_PROMPT`
  - 增量提取，允许语义推断

---

## 5. 关键节点执行规范（与代码一致）

### extractor
- 从历史与本轮提取新增槽位
- 保留已有槽位，不破坏覆盖
- 若 `outline_pending`：先识别用户意图（确认/修改/提供新信息）

### evaluator
- 缺槽位 → `response_type=ask`
- 槽位齐 → `response_type=outline`
- 已有大纲 + 用户确认 → `response_type=generate`

### ask
- 单轮只问一个最高价值缺失点
- 回显已知信息，避免重复

### outline
- 输出结构化大纲（3–6章，每章2–3要点）
- 修改场景：局部编辑，不重写全篇

### generate
- 严格按大纲顺序生成正文
- 若 `auto_fill` 或用户强催促，允许兜底后生成

---

## 6. 降级策略（现有实现）

- Structured output 失败 → 回退 JSON 解析
- 大纲解析失败 → 使用模板化兜底大纲
- 用户过度催促 → `auto_fill` 后生成

---

## 7. 可观测字段与审计

### 7.1 关键审计字段
- `extractor_reason/source/override_applied`
- `outline_reason/source/override_applied`
- `generate_reason/source/override_applied`

### 7.2 运行时可观测字段
- `report_slots`
- `report_missing`
- `report_outline_pending`
- `report_outline`
- `report_ready`
- `report_ask_counts`

---

## 8. 已完成 vs 待优化

### 已完成
- 主技能收敛（`edu-report-agent`）
- 工作流门禁完整可运行
- 追问 / 大纲 / 正文的可执行提示词

### 待优化建议
1. 输出契约 JSON 的强校验（与对话主技能一致）
2. 大纲修改场景更强的 diff/定位能力
3. 报告质量评估（长度、结构完整度、可读性）
4. 指标闭环：
   - `report_outline_accept_rate`
   - `report_generation_rework_rate`
   - `report_followup_positive_rate`

---

## 9. 版本变更

### v4.0.0
- 收敛为报告主技能 `edu-report-agent`
- 文档对齐 `edu-report-workflow` 与当前代码实现
