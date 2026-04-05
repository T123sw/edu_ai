---
name: edu-agent-routing
description: 对话入口的语义路由技能。仅做意图分类与审计输出，不承载业务流程判断；业务流程由 Python 状态机守门。
version: 2.2.0
owner: edu-ai-backend
---

# 教育路由技能（去幻觉可执行版）

## 1. 适用范围

仅适用于以下任务：
- 将用户输入分类为 `chat|generate_content|research`
- 输出可观测审计字段（原因、来源、是否覆写）

不适用于：
- 直接生成最终回答
- 决定报告流内部节点（ask/outline/generate）
- 处理工具调用细节

---

## 2. 核心原则

1. **语义分类最小化**：路由层只做“分类”，不做“业务决策”。
2. **状态守门优先**：若命中 awaiting 状态，Python override 具有最高优先级。
3. **确定性兜底**：LLM 失败必须进入 fallback，不得抛出未处理异常。
4. **审计先行**：每轮必须输出 `reason/override_applied/route_source`。

---

## 3. 输入契约

```json
{
  "question": "用户问题",
  "conv_state": {
    "awaiting_clarification": false,
    "report_state": {
      "awaiting": false
    }
  }
}
```

---

## 4. 输出契约

```json
{
  "intent_category": "chat|generate_content|research",
  "router_reason": "awaiting_clarification_override|llm_json|fallback_keyword_*|fallback_default_chat",
  "override_applied": true,
  "route_source": "override|llm|fallback"
}
```

---

## 5. 执行顺序（必须）

### 步骤A：状态覆写（Python）
若以下任一条件为 true：
- `awaiting_clarification`
- `report_state.awaiting`

则直接输出：
- `intent_category = generate_content`
- `override_applied = true`
- `route_source = override`
- `router_reason = awaiting_clarification_override`

### 步骤B：语义分类（LLM）
仅在步骤A未命中时执行。LLM 只返回 JSON：

```json
{"intent_category":"chat|generate_content|research"}
```

### 步骤C：fallback（Python）
当 LLM 输出无效/超时/解析失败：
- research 关键词命中 -> `research`
- generate 关键词命中 -> `generate_content`
- 否则 -> `chat`

并设置：
- `route_source = fallback`
- `router_reason = fallback_keyword_* | fallback_default_chat`

---

## 6. 反模式（禁止）

- 禁止在路由层拼装最终答案正文
- 禁止把报告工作流逻辑塞进路由分类
- 禁止只返回分类不返回审计字段
- 禁止无 fallback 直接抛错

---

## 7. Few-shot（可执行示例）

### 示例1：状态覆写
输入：用户说“继续刚才报告”，且 `report_state.awaiting=true`
输出：
- `intent_category=generate_content`
- `route_source=override`

### 示例2：普通问答
输入：“什么是形成性评价？”
输出：
- `intent_category=chat`
- `route_source=llm|fallback`

### 示例3：联网检索
输入：“帮我查 2026 年最新教育 AI 政策并总结”
输出：
- `intent_category=research`

---

## 8. 验收指标（可量化）

- `state_override_accuracy >= 99%`
- `fallback_recovery_rate >= 99%`
- `audit_field_completeness = 100%`
- `router_p95_latency` 单独监控（含 llm 与 fallback 分桶）

---

## 9. 与代码对齐清单

需与以下运行时字段一致：
- `state.awaiting_override_applied`
- `state.route_source`
- `state.router_reason`
- `meta.audit.router.reason`
- `meta.audit.router.override_applied`
- `meta.audit.router.route_source`

---

## 10. 变更日志

### v2.2.0
- 移除所有未验证外部来源描述（去幻觉）
- 强化“路由只分类，流程由 Python 守门”边界
- 统一输出审计契约与 fallback 命名规范
- 增加可量化验收指标与代码对齐清单

### v2.1.0
- 增加 `research` 分类
- 强调 fallback 由 Python 执行
