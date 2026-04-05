# Phase 3 验证用例（Skill 驱动 + 重规划）

## 用例 1：Skill 切换行为变化

### 输入
- 同一用户问题："帮我写一份孙悟空报告"
- Skill A：强调先补全 focus，再大纲确认
- Skill B：强调先检索，再补全 soft 参数

### 预期
1. Planner 输出 step 顺序在 A/B 下不同
2. 代码不变，仅 skill_prompt 变化即可触发行为变化

---

## 用例 2：工具失败补救重规划

### 输入
- 初始计划：`rag_search_tool`
- 模拟 rag 返回失败（ok=false）

### 预期
1. Executor 状态转 `replanning`
2. Analyzer 触发更新计划（如 web_search 或改 query）
3. `replan_count` +1

---

## 用例 3：重规划上限保护

### 输入
- 连续失败场景，达到 `max_replans=3`

### 预期
1. 状态从 `replanning` 转 `finished`
2. 输出降级提示："达到最大重规划次数，请补充信息"

---

## 用例 4：大纲确认前禁止正文

### 输入
- report_outline 为空
- report_content 为空

### 预期
1. Planner 不能直接输出 `generate_long_report_content`
2. 必须先走 `submit_outline_for_review`

---

## 用例 5：挂起恢复基本链路

### 输入
- 第一次执行触发 `ask_human_for_clarification`
- 用户反馈写入 `human_feedback`
- 继续执行子图

### 预期
1. 第一次状态 `awaiting_human`
2. 恢复后 Planner 基于 feedback 生成下一步
3. 流程可继续到大纲或正文阶段
