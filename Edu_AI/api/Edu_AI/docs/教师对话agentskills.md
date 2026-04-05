# 教师对话 AgentSkills 实施文档（v4.2 对齐版）

> 本文档为**当前实际落地版本**。  
> 相比 v3.0：从“多 dialogue 子技能文件”收敛为“**单一对话主技能 + 路由子技能**”，并与现网字段对齐。

---

## 0. 架构总览（当前真实形态）

### A. 主技能（按 Agent 维度）
1. `edu-dialogue-agent`：教师对话主技能（解释/教法/管理/复盘/澄清/共情）
2. `edu-report-agent`：报告相关主技能（槽位追问/大纲确认/正文生成提示词）

### B. 路由子技能（决策专用）
1. `dialogue-need-router`：二级对话意图路由（决定 `dialogue_skill`）
2. `tool-auth-router`：工具触发意图判定与授权话术模板

### C. 编排与流程技能
- `edu-orchestrator`
- `edu-agent-routing`
- `edu-report-workflow`
- `edu-rag-multimodal`
- `edu-teacher-content-factory`

---

## 1. 为什么从 v3.0 收敛到 v4.x

v3.0 中将对话拆为多个 skill 文件，便于讨论边界，但在工程层面会带来：
- 节点过多、状态流转复杂
- 提示词分散，版本管理成本高
- 同类场景策略漂移风险高

v4.x 采用：
- **单主技能 `edu-dialogue-agent`** 统一承载对话策略
- 通过上游路由字段 `dialogue_skill` 动态激活子模板 section
- 保留最小安全兜底，避免路由异常导致崩溃

---

## 2. 对话主技能输入/输出契约

## 2.1 输入契约（对齐运行时 state）

```json
{
  "question": "string",
  "dialogue_skill": "dialogue-explainer|dialogue-pedagogical|dialogue-management|dialogue-reflective|dialogue-consultative|dialogue-empathic",
  "need_type": "explain|teach_design|management|reflective|consultative|empathic",
  "user_role_mode": "teacher_learner|teacher_educator",
  "tool_budget": {
    "web_search_allowed": false,
    "rag_allowed": false
  },
  "user_profile": {
    "subject": "string|optional",
    "grade": "string|optional",
    "style": "string|optional"
  },
  "memory_slot": {
    "current_topic": "string|optional",
    "last_frustration_point": "string|optional"
  }
}
```

### Memory Hook 说明
- `user_profile`：用于年级/学科/风格适配
- `memory_slot`：用于多轮连续性（当前话题、最近卡点）
- 当前可静态为空，后续可由 memory skills 动态注入

## 2.2 输出契约（主技能标准）

```json
{
  "answer": "string",
  "skill_used": "dialogue-explainer|dialogue-pedagogical|dialogue-management|dialogue-reflective|dialogue-consultative|dialogue-empathic",
  "next_action": "direct_answer|ask_user|request_tool_auth",
  "needs_more_context": false,
  "requested_tool": "none|rag|web",
  "tool_auth_required": false,
  "followup_question": "string|optional",
  "audit": {
    "reason": "string",
    "route_source": "llm|fallback|override",
    "degraded": false
  }
}
```

说明：
- `next_action=request_tool_auth` 时，`requested_tool` 必须为 `rag|web`
- `next_action=ask_user` 时，建议给 `followup_question`
- 运行时可在 meta 中输出同名/近同名字段用于观测

---

## 3. 子模板驱动生成（核心机制）

`edu-dialogue-agent` 内部定义多个 section，运行时根据 `dialogue_skill` 选择模板：

- `dialogue-explainer` -> `EXPLAINER_TEMPLATE`
- `dialogue-pedagogical` -> `PEDAGOGICAL_TEMPLATE`
- `dialogue-management` -> `MANAGEMENT_TEMPLATE`
- `dialogue-reflective` -> `REFLECTIVE_TEMPLATE`
- `dialogue-consultative` -> `CONSULTATIVE_QUESTION_TEMPLATE`
- `dialogue-empathic` -> `EMPATHIC_TEMPLATE`

### 关键落地点
- `dialogue_skill` 由 `dialogue-need-router`（模型）给出
- `skill_used` 在运行时写回 state/meta
- 模板 section 由 `SkillManager.extract_section(...)` 注入

---

## 4. explain vs teach_design 边界（重点）

### explain（教师作为学习者）
触发语义：
- 什么是 / 解释一下 / 介绍一下 / 原理 / 本质 / 区别

输出目标：
- 概念解释清楚（定义 + 原理 + 例子 + 易混点）
- 不默认展开完整教案设计

### teach_design（教师作为教育者）
触发语义：
- 怎么给学生讲 / 课堂设计 / 导入 / 活动 / 教案 / 备课

输出目标：
- Hook / Analogy / Misconceptions / 课堂动作

---

## 5. consultative 追问与超限兜底

### 追问规则
- 一次只问一个关键点
- 优先级：topic -> audience -> goal
- 追问最多 2 轮

### 两轮后兜底
- 强制使用 `CONSULTATIVE_FALLBACK_AFTER_2_TURNS_TEMPLATE`
- 不再继续连环追问
- 标记 `needs_more_context=true`

---

## 6. 工具授权机制（显式确认）

### 判定流程
1. 用户显式触发（如“查知识库/上网查找”）优先
2. 其余由 `tool-auth-router` 模型判定
3. 命中后先发授权询问，不得静默调用

### 授权话术模板
来自 `edu-dialogue-agent#TOOL_AUTH_TEMPLATE`：
- “先常规解答（立即）” vs “先检索（预计耗时）” 二选一

### 用户拒绝授权
- 必须立即返回常规快速解法（显式模板）
- 不回到普通慢路径

---

## 7. 可观测字段（运行时建议）

核心字段：
- `need_type`
- `user_role_mode`
- `dialogue_skill`
- `skill_used`
- `next_action`
- `needs_more_context`
- `tool_auth_requested`
- `tool_auth_granted`
- `tool_auth_type`
- `tool_auth_reason`
- `requirement_clear`
- `requirement_signal_count`

健康检查建议：
- 校验 `skill_used/next_action/needs_more_context` 完整性
- 校验 `next_action=request_tool_auth` 时工具字段一致性

---

## 8. 当前已完成 vs 后续待做

### 已完成
- 单主技能收敛（对话/报告）
- 路由主要交给模型（含最小安全兜底）
- 子模板注入与运行时调用打通
- 工具授权拒绝后的显式快速兜底

### 后续建议
1. 统一 meta 输出字段名与输出契约完全同名
2. 增加 `template_section_used` 便于线上排查
3. 将 memory skills 正式接入并替换静态 Memory Hook

---

## 9. 字段对照表（契约 -> 运行时 -> 返回 meta）

| 语义 | 主技能输出契约字段 | 运行时 state 字段 | 返回 meta 字段 |
|---|---|---|---|
| 本轮答案 | `answer` | `final_answer` | （delta流输出正文） |
| 命中技能 | `skill_used` | `skill_used` | `skill_used` |
| 下一步动作 | `next_action` | `next_action` | `next_action` |
| 是否需更多上下文 | `needs_more_context` | `needs_more_context` | `needs_more_context` |
| 请求工具类型 | `requested_tool` | `tool_auth_type` | `tool_auth_type` |
| 是否要求授权 | `tool_auth_required` | `tool_auth_requested` | `tool_auth_requested` |
| 授权是否通过 | （可扩展） | `tool_auth_granted` | `tool_auth_granted` |
| 路由原因 | `audit.reason` | `need_route_reason` / `router_reason` | `need_route_reason` / `audit.router.reason` |
| 路由来源 | `audit.route_source` | `route_source` | `audit.router.route_source` |
| 是否降级 | `audit.degraded` | （建议新增统一 `degraded`） | （建议补充 `degraded`） |
| 需求类型 | （可扩展） | `need_type` | `need_type` |
| 用户角色模式 | （可扩展） | `user_role_mode` | `user_role_mode` |
| 对话子路由结果 | （可扩展） | `dialogue_skill` | `dialogue_skill` |

### 9.1 命名差异说明
- 当前实现中，契约里的 `requested_tool` 对应运行时 `tool_auth_type`。
- 当前实现中，契约里的 `tool_auth_required` 对应运行时 `tool_auth_requested`。
- 建议后续将返回 meta 字段与契约字段做同名统一，减少前后端映射成本。

## 10. 版本变更

### v4.2.0（当前）
- 文档全面对齐单主技能架构
- 增加 Memory Hook / Tool Auth Template / 输出契约说明
- 明确 explain vs teach_design 边界与子模板映射

### v3.0.0（历史）
- 多 dialogue 子技能文件拆分版本（已归档）
