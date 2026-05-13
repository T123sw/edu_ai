# 报告生成模块现状分析与重构方案

> 版本：v1.0 | 日期：2026-03-26 | 状态：分析完成

---

## 一、当前工作流程梳理

### 1.1 LangGraph 图结构（4 节点 + 2 条件边）

```
planner → validator → [条件边] → executor → analyzer → [条件边] → ...
                          ↑                                  │
                          └────── replanning ─────────────────┘
```

`build_universal_report_graph()` 定义了：

| 节点 | 函数 | 职责 |
|------|------|------|
| `planner` | `planner_node` | 槽位提取 + focus 充分性评估 + 规划下一步 |
| `validator` | `plan_validator_node` | 校验计划合法性 |
| `executor` | `executor_node` | 调度工具执行 |
| `analyzer` | `analyzer_node` | 审查执行结果，决定下一步状态 |

### 1.2 状态流转

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `planning` | 初始状态 | `make_initial_report_state` |
| `executing` | planner 已产出计划 | planner_node 返回 plan |
| `reviewing` | 执行完成待审查 | executor 执行成功 |
| `replanning` | 需要重新规划 | 工具失败/校验不通过/analyzer 判定 |
| `awaiting_human` | 等待用户反馈 | `need_human=True` 的工具结果 |
| `finished` | 流程结束 | report_content 已生成/达到 max_replans |

### 1.3 planner_node 内部流程（最复杂的节点，180 行）

```
1. 检查是否已有未执行完的计划 → 有则 return {}
2. LLM 提取槽位 (_extract_slots_with_llm)
3. 处理软确认状态 (soft_confirm_pending → soft_confirmed)
4. 合并提取的槽位到 state
5. 判断是否需要强制 focus 细化 (should_force_refine)
6. focus 充分性评估 (_assess_focus_sufficiency) → LLM 判断
7. 稳定性防抖
8. 生成兜底计划 (_fallback_plan)
9. 尝试 LLM 产出计划
10. 若无计划且有 report_content → finished
```

### 1.4 _fallback_plan 决策链

```
1. required_slots 未填满？ → ask_human_for_clarification
2. 需要软确认？ → ask_human_for_clarification(soft_confirm)
3. 有大纲无正文？ → generate 或 revise_outline
4. 无大纲？ → submit_outline_for_review
5. 无正文？ → generate_long_report_content
6. 否则 → 空计划（finished）
```

---

## 二、核心问题

### 问题 1：planner_node 职责严重越界（"上帝节点"）

`planner_node` 同时承担 5 个独立关注点：槽位提取、Focus 充分性评估、用户反馈解析、软确认管理、计划生成。180 行代码，内部状态交叉耦合。

### 问题 2：边界条件靠"补丁"维护

代码中 6 处"边界修复"/"关键修复"注释，形成"修复套修复"的腐化模式。根因是状态机未正式建模。

### 问题 3：两套 Skill 定义互相矛盾

- **edu-report-agent**：`core_topic / focus_area`（实际使用）
- **edu-report-workflow**：`topic / period / outcomes / issues / next_plan`（从未实现）

### 问题 4：focus 充分性评估是死循环陷阱

每次 planner 都调 `_assess_focus_sufficiency`（LLM 调用），判断不稳定，阻断后续流程。

### 问题 5：gathered_context 成为状态垃圾桶

`Dict[str, Any]` 中隐藏 10+ 个隐式状态标记，不可枚举、不可校验。

### 问题 6：validator 在修复 planner 的错误

validator 自动注入/裁剪步骤，模糊了节点职责边界。

---

## 三、重构方案：显式阶段状态机

### 3.1 阶段定义

```
extracting → evaluating → asking | confirming | outlining | generating → finished
```

### 3.2 evaluator 路由规则（纯 Python，~10 行）

```python
required = ["core_topic", "focus_area"]
missing = [s for s in required if not slots.get(s)]

if missing:         → asking
if not confirmed:   → confirming
if not outlined:    → outlining
else:               → generating
```

### 3.3 各阶段职责

| 阶段 | 输入 | 动作 | 边界判断 |
|------|------|------|---------|
| extracting | user_input / human_feedback | LLM 提取槽位 | 无条件→evaluating |
| evaluating | report_slots | 纯规则检查 | 缺→asking, 未确认→confirming, 无大纲→outlining, 就绪→generating |
| asking | missing_slot | 生成追问话术 | ask_count ≥ ask_limit → 用默认值 |
| confirming | slots | 生成确认话术 | 肯定回复 → soft_confirmed=True |
| outlining | slots | 生成/修改大纲 | 用户确认 → outline_confirmed=True |
| generating | slots + outline | 生成正文 | 成功→finished, 失败→重试 |

### 3.4 核心改进

| 维度 | 旧实现 | 新实现 |
|------|--------|--------|
| 状态管理 | gathered_context 隐式标记 | 显式 phase + bool 字段 |
| 阶段推进 | planner LLM 决定 | 纯规则驱动 |
| focus 评估 | 每次 LLM 评估 | 删除，有就接受 |
| 软确认 | 三处分散处理 | confirmer 单一节点 |
| 代码量 | ~1200 行 | 预计 ~400 行 |
