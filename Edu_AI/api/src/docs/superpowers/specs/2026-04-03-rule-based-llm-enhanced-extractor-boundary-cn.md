# 规则抽取器与 LLM 增强抽取器分工边界表
**状态：** 已整理，可作为下一阶段规划与实现边界基线  
**日期：** 2026-04-03  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`

---

## 1. 文档目的

本文档用于明确下一阶段对话状态抽取系统的演进方向：

- 规则抽取器继续作为主干保留
- LLM 抽取器以增强层方式接入
- merge / guard 层必须独立存在

本文档不直接等同于 implementation plan，而是用于回答以下问题：

1. 当前为什么不适合把抽取器整体切换成 LLM
2. 规则抽取器、LLM 增强抽取器、merge / guard 层分别负责什么
3. 哪些字段继续由规则抽取负责
4. 哪些字段适合让 LLM 做增强
5. 哪些字段绝不能让 LLM 直接写入
6. LLM 增强层应在什么时机触发

---

## 2. 总体判断

当前阶段的重点不是立刻把现有抽取器全面替换成 LLM，而是：

**先把状态系统做稳，再把 LLM 抽取作为第二阶段增强层接入。**

换句话说，当前优先级应为：

- 短期重点：稳状态、稳 merge、稳写回、稳承接
- 中期重点：把 report-first 承接模式推广到 lesson plan / quiz / ppt
- LLM 抽取：作为增强层按需接入，而不是直接替代全部规则抽取

---

## 3. 为什么当前不适合全面切到 LLM 抽取

### 3.1 当前主矛盾不是“抽不聪明”，而是“状态还不够稳”

当前系统已经能抽取出以下核心状态：

- `current_topics`
- `user_goals`
- `constraints`
- `teaching_issues`
- `student_signals`
- `confirmed_facts`
- `evidence_points`

当前更大的问题在于：

- merge 是否稳定
- 写回时机是否一致
- workflow 承接是否统一
- 状态卡片是否能稳定暴露状态质量问题

这些问题不会因为引入 LLM 自动消失。

### 3.2 全量 LLM 抽取会立即引入新的工程风险

主要风险包括：

- 成本提升：每轮抽取都调用 LLM，成本会显著增加
- 时延上升：普通 reply 链路会被拉长
- 可测性下降：字段输出开始波动，单元测试和回归测试难度增大
- 状态污染风险上升：推断、建议、总结容易被误写入事实层

因此，当前阶段不宜采用“全量 LLM 抽取替换规则抽取器”的方案。

---

## 4. 推荐路线：分层抽取架构

推荐把抽取系统演进成以下三层：

### 4.1 第 1 层：规则抽取器

定位：

- 快
- 稳
- 可测试
- 低成本

职责：

- 负责确定性强、可规则化的字段
- 提供主抽取结果
- 为后续 LLM 增强层提供候选基础状态

### 4.2 第 2 层：LLM 增强抽取器

定位：

- 聚合
- 整理
- 消歧
- 结构增强

职责：

- 不直接主导所有状态写入
- 只针对语义复杂、跨轮依赖强、规则难以稳定覆盖的字段介入
- 产出“候选更新”，供 merge / guard 层裁决

### 4.3 第 3 层：merge / guard 层

定位：

- 去重
- 覆盖
- 冲突处理
- 过期
- 可信度升级 / 降级
- 来源追踪

职责：

- 作为状态写入前的最终裁决层
- 阻止 LLM 直接污染状态
- 确保结构化状态随着多轮对话保持可控与稳定

**结论：LLM 只能产出候选更新，不能直接改最终状态。**

---

## 5. 字段分工边界

### 5.1 继续由规则抽取器主负责的字段

这些字段具有较强的确定性，应继续由规则抽取器主负责：

#### 系统运行态 / 显式输入态

- `active_context`
- `workflow_state`
- `capability_policy`
- `selected_doc_ids`
- `allow_rag`
- `allow_web`

原因：

- 这些字段本质是系统状态或显式输入
- 不应依赖模型推断

#### 明确模式匹配型字段

- `action_hint`
- 明确的 `user_goals`
- 明确的 `constraints`

例如：

- “生成报告”
- “整理教案”
- “高一物理”
- “800 字左右”
- “正式一点”

原因：

- 明确关键词触发稳定
- 规则抽取成本低、结果可控

### 5.2 适合由 LLM 增强抽取器介入的字段

这些字段语义复杂、跨轮依赖强，更适合作为 LLM 增强层目标：

- `summary_text`
- `current_topics`
- `user_goals` 的主目标排序与消歧
- `teaching_issues`
- `student_signals`
- `confirmed_facts` 的候选集筛选
- `evidence_points` 的聚合与规范化

原因：

- 规则抽取可以做 MVP
- 但在跨轮整合、隐式约束、问题簇聚合、事实 / 证据 / 问题点区分上存在天花板

### 5.3 不应让 LLM 直接写入的字段

以下字段不应由 LLM 直接成为唯一来源：

- `active_context`
- `workflow_state`
- `capability_policy`
- `selected_doc_ids`
- 最终版 `confirmed_facts`

其中 `confirmed_facts` 的原则是：

- LLM 可以产出 `fact candidates`
- 但不能直接改写最终 `confirmed_facts`

---

## 6. 推荐的字段级分工表

| 字段 | 规则抽取器 | LLM 增强抽取器 | merge / guard |
|---|---|---|---|
| `active_context` | 主负责 | 不介入 | 只校验一致性 |
| `workflow_state` | 主负责 | 不介入 | 只校验一致性 |
| `capability_policy` | 主负责 | 不介入 | 只校验一致性 |
| `selected_doc_ids` | 主负责 | 不介入 | 只校验一致性 |
| `summary_text` | 可生成基础版 | 主增强 | 最终写入前裁决 |
| `current_topics` | 主负责基础抽取 | 做聚合 / 合并 / 排序增强 | 去重、衰减、覆盖 |
| `user_goals` | 主负责明确目标识别 | 做主目标排序与消歧 | 去重、切换、过期 |
| `constraints` | 主负责明确约束抽取 | 做隐式约束增强 | 冲突处理、覆盖 |
| `teaching_issues` | 主负责基础抽取 | 做问题簇聚合增强 | 去重、升级、过期 |
| `student_signals` | 主负责基础抽取 | 做聚合 / 细化增强 | 去重、升级、过期 |
| `confirmed_facts` | 主负责明确事实候选 | 做候选筛选与规范化 | 最终确认、冲突降级 |
| `evidence_points` | 主负责基础提取 | 做聚合、归类、标准化 | 来源合并、可信度升级 |

---

## 7. LLM 增强层最适合的触发时机

当前不建议每轮都跑 LLM 增强抽取器，更适合按以下时机触发。

### 7.1 关键节点触发

例如：

- 用户说“根据以上内容生成报告 / 教案 / 练习”
- 用户确认某个结论
- 用户补充关键案例 / 数据
- workflow 切入新阶段
- artifact 生成成功

### 7.2 周期性压缩触发

例如：

- 每 5 轮
- 消息累计超过一定长度
- `summary` / `memory` 脏度上升时

### 7.3 低置信度字段触发

例如规则层发现：

- `topics` 过散
- `goals` 冲突
- `constraints` 含糊
- `evidence` 质量低

### 7.4 workflow 前置触发

尤其在进入以下资源生成前：

- report
- lesson plan
- quiz
- ppt

此时进行一次上下文收口，收益最高。

---

## 8. 推荐的演进顺序

### 阶段 A：先稳规则抽取器与状态系统

目标：

- merge 稳
- 写回稳
- 状态卡片稳
- report 承接稳

此阶段不替换主抽取器架构。

### 阶段 B：先加 LLM Summary / Refinement 层

第一批最适合增强的字段：

- `summary_text`
- `teaching_issues / student_signals`
- `evidence_points`

### 阶段 C：再增强 goals / topics / constraints 的消歧

例如：

- 主目标排序
- topic 合并
- 隐式约束抽取

### 阶段 D：最后再评估是否扩大 LLM 覆盖面

只有在以下前提成立后才评估：

- 规则基线已稳定
- merge 规则已稳定
- 状态卡片反馈回路建立
- report / lesson / quiz 等 workflow 已验证承接链稳定

---

## 9. 当前阶段的实施优先级

下一阶段推荐的优先级排序如下：

### 第一优先级

- merge 规则
- 写回事件流
- 状态卡片稳定性

### 第二优先级

- lesson plan / quiz / ppt 接入统一 `GenerationContext`

### 第三优先级

- 引入 LLM 增强抽取器
- 第一批只增强：
  - `summary_text`
  - `teaching_issues / student_signals`
  - `evidence_points`

### 第四优先级

- 再评估是否扩大 LLM 抽取覆盖面

---

## 10. 一句话收口

当前最合适的路线不是“立刻把抽取器整体换成 LLM”，而是：

**保留规则抽取器做主干，再引入一个关键节点触发的 LLM 增强抽取层，由独立的 merge / guard 层最终裁决状态写入。**
