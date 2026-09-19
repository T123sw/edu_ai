# 窗口 B：全链路 Harness 与 Skills 接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让备课资源写作、审阅、修复和整课验收都实际通过原生 DeepSeek Harness，保留可恢复阶段主流程。

**Architecture:** 复用现有 SDK、受限工具桥、模型计量及 Skill 加载校验；增加显式阶段绑定的内容网关。各阶段用有限独立会话，共享持久化业务状态。

**Tech Stack:** DeepSeek Harness Python SDK/MCP、现有 provider transport、SQL 计量、pytest。

**Spec:** [总计划](../2026-09-19-preparation-chain-optimization.md)、[共享契约](00-shared-contracts.md)。

## Global Constraints

- 不通过外层 Harness 工具包装内部直连模型来冒充迁移完成；每个智能 completion 均需实际 SDK/Skill 证据。
- 不移除队列、服务端授权、预算和事务；不要求全流程共用一个长会话。
- 当前研究/intake 优化是共同基线的一部分，不回退；C 拥有研究工具业务和研究 Skill。

## 文件范围与接口

- 新建：`backend/src/app/course_preparation/harness_generation.py`、必要的独立受限内容提交工具模块。
- 修改：`harness_adapter.py`、`harness_provider.py`、`context.py`、`workflow_skills.py`、`generation_gateway.py`、`adapters/generation.py`；新阶段角色文件由 B 建立路由，内容与 D/E/F 对齐。
- 测试：`test_harness_generation.py`（新）、既有 `test_harness_intake.py`、`test_harness_research.py`、`test_generation_adapter.py`。
- 不修改 D 的 `reviewed_resource.py`、F 的 `quality.py`。提供共享契约中的 `PreparationHarnessGateway` / `scoped_gateway`，由消费者明确绑定 phase。

## Task B1：内容 SDK 入口与受限提交协议

- [ ] 新建 SDK 协议测试：工具参数非法、空正文、未加载 Skill、会话正常结束却未提交、模型请求被截断，都不得产出可交付结果。
- [ ] 实现 `for_phase()` 返回独立上下文视图，`.chat()` 以 SDK 会话取得提交工具的字符串结果；真实正文 JSON 的业务校验仍由 D/E 执行。
- [ ] 受限内容工具只接收本次正文结果，不能挂 shell、任意文件写入、权限提升或课程发布。实现片段的语义如下：

```python
def accept_resource_text(arguments):
    text = arguments.get('text')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('RESOURCE_TEXT_EMPTY')
    return text
```

- [ ] 新增 phase → Skill 映射：resource_write/resource_repair、resource_review、classroom_write/classroom_repair、course_review。Skill 正文由 D/E/F 提交，不另写平行版本。
- [ ] prep 网关缺 Skill 或 SDK 不可用时明确失败；旧工作台保持既有调用策略，不能全局强制切换。
- [ ] 通过 B1 协议测试后发布 B0 接口提交，包含一个 report 文本和一个 quiz JSON 的真实 SDK＋模拟 provider 样例；明确这还不是真实模型质量验收。

## Task B2：计量、上下文与生命周期统一

- [ ] 每次模型调用按共享契约记录 phase、runtime、Skill 摘要、规格摘要、真实 usage；不能把本地会话终止回执计成实际模型调用。
- [ ] 写作和审阅各自绑定正确 max_tokens、timeout、父任务剩余预算。检查当前 provider 的固定 6000 输出限制；迁移不能意外截断原有长课堂审阅，也不能无界提高配额。
- [ ] SDK 返回合法终端工具结果后本地关闭，保留原失败原因；取消、超时、失租后禁止后续写入，已发起调用的实际费用仍可结算。
- [ ] C 给出长资料视图后由 B 接到 `context.py`；先保留用户约束和引用身份，再裁减可重复历史。超限明确停止，不只增大数字来掩盖问题。
- [ ] 并发测试两个不同 node/phase 的 gateway 视图互不串参数；在父任务取消、模型慢响应、SDK 关闭失败下没有后台悬挂工作。
- [ ] 执行既有 intake/research 原生 Harness 测试；一次已经计量的 completion 不能在 wrapper 中重复计量。

## Task B3：真实主入口接线与禁止隐式回退

- [ ] `adapters/generation.py` 保留 `automatic_payload()` 兼容入口，委托 A 的 builder；用 `PreparationHarnessGateway` 替换备课 handler 的直连生成网关。
- [ ] 与 D/E 配对验证它们的每次写作/审阅/修复均调用 `scoped_gateway()`，不能只迁移首轮写作。
- [ ] 将 course_review 加入真实路由，与 F 的质量阶段做集成；保留非备课的旧 adapter 兼容，备课未知智能 phase 要报错误而不是回退直连。
- [ ] 将 F 的 FailureDetail 原样保留到失败回执；元数据与内容保存通过 F 的授权 API 执行。
- [ ] 对真实全流程的动作记录执行以下验收逻辑；缺失 phase 的旧样本应失败，新样本必须通过：

```python
def assert_all_preparation_completions_use_harness(actions):
    completed = [a for a in actions if a['kind'] == 'model_completion'
                 and a['status'] == 'completed']
    assert completed
    for action in completed:
        response = action['receipt']['model_response']
        assert response['runtime'] == 'deepseek-harness'
        assert response['phase']
        assert response['skill']['loaded'] is True
        assert response['skill']['sha256']
```

- [ ] 与 G 跑包含 report/quiz/classroom、资源审阅、整课审阅及一次内容修复的真实小课程；保存调用类型清单，不能仅凭模块名包含 harness 判定通过。

## 完成门槛与交付记录

- [ ] 所有备课智能 phase 已实际接线；确定性解析/存储/渲染操作独立列出，不算成模型调用。
- [ ] 提供每个 phase 的 Skill、输入/输出、工具范围、预算及真实运行证据；旧工作台回归没有策略变化。
- [ ] SDK/模型 mock 测试、真实模型测试、主流程集成三层结果分别记录；发布提交和需要 G 合并的装配变更。
