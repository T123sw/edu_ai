# 窗口 D：报告、习题与资源审阅 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 报告和习题真正落实节点活动及用户要求，修复已发现的漏检和共享报告策略回归，并接入 B 的原生 Harness。

**Architecture:** 保留现有原生资源格式和内容摘要绑定；为 v2 准备规格使用结构化教学上下文，正文生成与独立审阅分别执行。旧工作台大纲确认语义单独保留。

**Tech Stack:** Python、既有 Markdown/quiz schema、DeepSeek Harness Skills、pytest。

**Spec:** [总计划](../2026-09-19-preparation-chain-optimization.md)、[共享契约](00-shared-contracts.md)、[真实漏检样例](../../../acceptance/artifacts/2026-09-19-preparation-agent-audit/quality-counterexamples.json)。

## Global Constraints

- 不新增资源规划阶段，不自行改默认资源组合；生成单份内容时直接使用已经确定的教学活动。
- 不把“先例子”“面向初学者”等只写在说明中，必须落实正文。
- 审阅独立于写作；旧正文变更后重新审阅；格式失败不等于正文有错。
- 不以删除三个失败测试替代明确审阅策略兼容。

## 文件范围与接口

- 修改：`backend/src/app/chat/harness/reviewed_report.py`、`reviewed_resource.py`、必要的 `resource_profiles.py`；`backend/src/app/services/generation_task_handlers.py` 的报告审阅策略相关分支。
- 新增：`course_preparation/skills/generate-learning-resource/SKILL.md`、`skills/review-learning-resource/SKILL.md`，以及必要的准备专用要求/定位校验模块。
- 测试：`tests/chat/test_reviewed_report.py`、`test_harness_resources.py`；新 `tests/course_preparation/test_generated_content_constraints.py`、`test_review_counterexamples.py`。
- 消费 A 的 teaching_context、B 的 scoped_gateway 和 F 的 ResourceCheckpointPort/FailureDetail；Skill 注册交 B。
- E 复用 `review_classroom(content, config, gateway=None, *, checkpoint=None)`；此共享函数由 D 独占编辑。

## Task D1：去掉模板污染，让教学要求改变正文

- [ ] 固化真实反例：用户与路径要求先例后理，旧结果却概念在先、含额外面试话术。写“先例后理”和“先理后例”两组测试，验证最终章节顺序而不是 prompt 字符串。
- [ ] v2 准备输入不再要求固定的 `harness_chapters`；直接依据结构化活动组织 Markdown，生成可定位的章节和对应要求/目标映射。旧工作台有确认大纲时仍按其标题与顺序执行。
- [ ] 不增加一个额外模型资源规划调用：内容结构可在本次写作返回中确定，并由程序验证定位、独立审阅语义。
- [ ] 生成前绑定正确阶段，例如：

```python
writer = scoped_gateway(gateway, phase='resource_write',
    context=payload.teaching_context, preparation=True)
body = writer.chat(messages, max_tokens=12000)
```

- [ ] 明确基础、语言、深度、活动、排除主题、来源限制如何消费；移除未请求的面试段落。除非用户要求面试，不因旧模板残留继续生成。
- [ ] 使用 `node_budget_minutes` 控制内容规模但不声称本资源独占节点时间；返回带方法的估算，无法估算就 unknown，交 F 汇总校核。
- [ ] 保存稳定 section_id、需求/目标定位和摘要元数据。无实际内容的 locator 直接报 contract 错误，不提交通过回执。

## Task D2：逐选项解释与局部审阅恢复

- [ ] 将以下实际错误作为明确失败样例，而不是只测试算术答案：

```python
COUNTEREXAMPLE = {
    'option_text': '模型和程序都负责执行工具，只是先后顺序不同',
    'explanation': '该选项错误地认为程序也参与工具选择',
    'expected': 'reject_explanation_mismatch',
}
```

- [ ] 每个选项审阅同时携带服务端回填的选项原文、对应解析片段、独立判断和理由；索引/原文绑定防止模型审错对象。仅检查列表长度不足以判定语义正确。
- [ ] 习题生成保留稳定 question_id，返回具体目标到题目的检查映射；不要机械给每道题绑定全部目标。答案范围、题型、选项唯一性继续确定性校验。
- [ ] 为错误答案、正确答案但错误干扰项解释、含糊的多选题、缺解析、题目超出本节点目标分别编写最小样例；模拟模型测试验证控制流，真实模型样例验证识别能力，两者分开记结果。
- [ ] 在独立审阅前将正文写入 F 的私有 checkpoint。格式/覆盖不全最多按现有有限策略补审阅，跨进程重试从已保存候选继续，不能重新调用 writer。
- [ ] 故障验收采用计数网关和真实 checkpoint adapter，核心断言：

```python
assert writer_calls == 1
assert review_calls == 2
assert content_digest_before_retry == content_digest_after_retry
assert error_detail.category == 'review_format'
assert error_detail.retry_scope == 'review'
```

- [ ] 内容确实错时用 resource_repair 独立调用修复，保留未受影响内容，重新绑定摘要并审阅。review_classroom 使用同样 checkpoint/失败协议，E 不必另建审阅循环。

## Task D3：共享报告审阅策略兼容与主流程联调

- [ ] 枚举旧入口命令生产者，查明 `harness_outline_id`、`review_policy`、`harness_review_required` 的来源；先写策略矩阵测试再调整条件。
- [ ] 推荐兼容规则：显式 required 或 harness_review_required=true 必须审阅；没有新策略字段的旧 Harness 命令保留旧的强制审阅语义；明确 standard 的普通旧工作台行为保持不变。不得信任客户端传来的 standard 关闭服务端已要求的审阅。
- [ ] 统一“调用生成器”和“发布守卫”的同一服务端策略解析函数；避免前者审了、后者不要求，或反过来。若旧命令实际上从未支持此兼容，提供调用链证据并让 G 更新兼容矩阵，不静默改变历史要求。
- [ ] 修复已失败的三个测试，并增加 required、旧 Harness、普通工作台、伪造放宽策略的场景；不只修改 fixture 让错误分支消失。
- [ ] 使用总计划测试环境执行 `test_reviewed_report.py`、`test_harness_resources.py`、新要求/反例测试。与 B/F 实际连接，再跑真实报告＋习题样例并检查内容位置。

## 完成门槛与交付记录

- [ ] 两种相反教学顺序的实际产物分别符合要求，没有无关面试模板。
- [ ] 真实干扰项解释反例被拒绝或修正；每条检查可定位；格式修复未重生成正文。
- [ ] 三个共享报告回归失败得到有依据的修复，旧入口无策略退化。
- [ ] 向 E 发布课堂审阅函数兼容签名，向 F 发布失败及目标定位样例，向 G 提交原生资源和真实模型验收证据。
