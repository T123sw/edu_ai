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

- [x] 新建 SDK 协议测试：工具参数非法、空正文、未加载 Skill、会话正常结束却未提交、模型请求被截断，都不得产出可交付结果。
- [x] 实现 `for_phase()` 返回独立上下文视图，`.chat()` 以 SDK 会话取得提交工具的字符串结果；真实正文 JSON 的业务校验仍由 D/E 执行。
- [x] 受限内容工具只接收本次正文结果，不能挂 shell、任意文件写入、权限提升或课程发布。实现片段的语义如下：

```python
def accept_resource_text(arguments):
    text = arguments.get('text')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('RESOURCE_TEXT_EMPTY')
    return text
```

- [x] 新增 phase → Skill 映射：resource_write/resource_repair、resource_review、classroom_write/classroom_repair、course_review。Skill 正文由 D/E/F 提交，不另写平行版本。
- [x] prep 网关缺 Skill 或 SDK 不可用时明确失败；旧工作台保持既有调用策略，不能全局强制切换。
- [ ] 通过 B1 协议测试后发布 B0 接口提交，包含一个 report 文本和一个 quiz JSON 的真实 SDK＋模拟 provider 样例；明确这还不是真实模型质量验收。

## Task B2：计量、上下文与生命周期统一

- [x] 每次模型调用按共享契约记录 phase、runtime、Skill 摘要、规格摘要、真实 usage；不能把本地会话终止回执计成实际模型调用。
- [x] 写作和审阅各自绑定正确 max_tokens、timeout、父任务剩余预算。检查当前 provider 的固定 6000 输出限制；迁移不能意外截断原有长课堂审阅，也不能无界提高配额。
- [ ] SDK 返回合法终端工具结果后本地关闭，保留原失败原因；取消、超时、失租后禁止后续写入，已发起调用的实际费用仍可结算。
- [ ] C 给出长资料视图后由 B 接到 `context.py`；先保留用户约束和引用身份，再裁减可重复历史。超限明确停止，不只增大数字来掩盖问题。
- [x] 并发测试两个不同 node/phase 的 gateway 视图互不串参数；在父任务取消、模型慢响应、SDK 关闭失败下没有后台悬挂工作。
- [x] 执行既有 intake/research 原生 Harness 测试；一次已经计量的 completion 不能在 wrapper 中重复计量。

## Task B3：真实主入口接线与禁止隐式回退

- [x] `adapters/generation.py` 保留 `automatic_payload()` 兼容入口，委托 A 的 builder；用 `PreparationHarnessGateway` 替换备课 handler 的直连生成网关。
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


## B 执行记录（2026-09-19）

**当前状态：B0 接口与协议验证已落地；B2 生命周期/长资料接入、B3 消费者和真实全流程验收仍有跨窗口依赖。不能将本记录解释为全链路已完成。**

- 开始时 HEAD：`67fc18b8`；分支 `feat/self-learning-frontend-20260914`。工作区已有研究/intake 未提交修改，不等于 G0 已固定的共同基线。
- 保留已有修改，在当前工作区只修改 B 拥有的代码/测试。未将已有研究改动提交为 B 的成果；模块提交 SHA 暂无，提供仅 B 增量的 [装配 patch](../../../acceptance/artifacts/2026-09-19-preparation-harness-b/b0-changes.patch) 及其中两个共享文件的起始摘要。G 固定共同基线后应用并发布模块提交。
- 原生 SDK + 模拟 provider 的报告正文、习题 JSON 和六个 phase 的 [调用证据](../../../acceptance/artifacts/2026-09-19-preparation-harness-b/sdk-mock-provider.json) 已保存。Skill 为临时协议夹具，provider 为 `httpx.MockTransport`；没有真实模型内容质量或真实整课验收结论。

### 已提供接口与边界

`harness_generation.PreparationHarnessGateway` 保留 `chat(messages, temperature, max_tokens)`，必须先 `for_phase(phase, context=...)`。`scoped_gateway(gateway, phase=..., context=..., preparation=True)` 拒绝没有原生能力的网关；`preparation=False` 返回原网关。`generation_gateway.py` 同时导出这两个接口。

绑定返回新视图；每次 chat 创建新 adapter、临时 Skill 根、SDK 会话、鉴权 MCP/provider 桥。模型工具只有原生 Skill 加载工具和 `submit_resource_text`，后者仅接受非空 `text` 字符串，拒绝额外字段。业务正文/JSON 校验仍由 D/E/F 执行。新内容桥上限 2,000,000 字节，避免旧 256 KiB 桥意外拒绝长课堂审阅；旧工作台桥未修改。

| phase | Skill（正文仍归业务窗口） | 输出上限 | 工具与输入/输出 |
| --- | --- | --- | --- |
| resource_write / resource_repair | generate-learning-resource（D） | 调用方值，最多 12000 | messages + 显式阶段上下文 → 原样正文/JSON 字符串 |
| resource_review | review-learning-resource（D） | 调用方值，最多 65536 | 完整候选及审阅要求 → 审阅 JSON 字符串 |
| classroom_write / classroom_repair | generate-ai-classroom（E） | 调用方值，最多 12000 | 课堂上下文 → 课堂 JSON 字符串 |
| course_review | review-course-delivery（F） | chat 最多 12000；现有 decide 路由保持 6000 | chat 使用文本提交；QualityStages 现有 decide 使用 review_course_delivery 结构化工具 |

chat 会话时限为 `min(120 秒, 父任务剩余时限)`，最多 4 次 provider 尝试；真实调用前经过原有 SQL 预算预留，完成后按 usage 结算。原生 intake/research 的配额保持原策略。终端工具提交后的本地结束回执不经过模型、不计费；协议错误不能被 SDK 重试清除，close 失败不能覆盖已有失败原因。网关支持 `guard=` 回调；取消/时限在提交前和返回后检查，已完成的在途响应仍结算费用。

调用回执保存 `runtime`、`phase`、`skill.name/sha256/loaded`、provider/model、usage、`spec_digest`、`context_digest`。资源规格摘要来自 handler 的 artifact；研究/整课现有入口没有独立资源规格时，用当前完整阶段输入摘要作为规格摘要。模型响应格式非法且无可用 usage 时保守结算原预留，不伪造实际 token 数。

参数路径：调用方显式 phase → 注册表/独立 Skill → provider 回执 phase；调用方 max_tokens → SDK/provider 同值 → SQL output_limit；artifact.spec_digest → 阶段上下文 → model_response.spec_digest；正文 text → 原样返回 → D/E 业务校验。以上已有协议证据；教学要求是否改变最终资源的语义效果，仍待 A/D/E/F/G 的真实模型验收。

### 消费者装配清单

- **A：** 已提供自动委托 `generation_context.automatic_payload` 的兼容 wrapper。当前该模块未合入：旧 v1 规格仍走历史 reader；v2 明确报 `PREPARATION_CONTEXT_UNAVAILABLE`。A builder 到位后全部委托；A 负责清除历史固定模板并提供规范化数据。
- **D：** 在 `reviewed_report.py` / `reviewed_resource.py` 的每次写作、独立审阅、修复调用前分别使用 `resource_write` / `resource_review` / `resource_repair` 的 scoped_gateway；不要仅在首轮绑定。提供两个 Skill 正文与 checkpoint 消费接口。
- **E：** 课堂写作和修复分别绑定 `classroom_write` / `classroom_repair`，课堂审阅通过 D 的 `resource_review`。提供 `generate-ai-classroom` Skill。
- **F：** 提供 `review-course-delivery` Skill；当前 QualityStages 已经通过 HarnessPreparationAdapter 的 course_review 路由，缺 Skill 时明确失败。提供 FailureDetail 持久化、已授权 ResourceCheckpointPort 构造接口和可注入的租约/父任务 guard，B 再接到 handler。当前仍调用既有 ArtifactStore.save/fail；未擅自扩充 F 的私有存储 API。
- **C：** 当前没有本轮长资料视图接口交付到 B。继续保留已有精确引用身份与硬约束、先删除 trace 的上下文策略；超限显式失败，不扩大总上下文窗口掩盖资料问题。
- **G：** 合入上面的业务消费者后再运行真实小课程。handler 已改为提供未绑定的原生网关，旧消费者直接 chat 将报 `HARNESS_PHASE_REQUIRED`，因此当前组合不能启动完整生产生成。确定性解析/存储/渲染不记为模型 completion。

本次未增加迁移、不改持久化规格 digest 算法、不写正式 Skill 正文、不改旧工作台模型选择/确认/审阅策略。F 完成候选 checkpoint 前，不能声称审阅失败可恢复而不重写正文。

### 验证记录

基线命令采用总计划约定的 Python，禁用 dotenv：原生 intake/research 与 generation adapter 共 **38 passed / 6 skipped**；跳过项均为未配置隔离 PostgreSQL 测试库。

最终模块命令与数量见 [验证记录](../../../acceptance/artifacts/2026-09-19-preparation-harness-b/verification.txt)。测试覆盖真实 SDK/MCP＋模拟 provider、空正文/非法参数/无 Skill/无提交/截断、长课堂审阅、并发 node/phase、取消和失租 guard、慢响应结算与关闭失败、主入口拒绝未绑定消费者，以及原生 intake/research 回归。

三层结果分别为：**SDK/模型 mock 协议已验证；真实模型未执行（业务 Skill/消费者缺失）；真实全流程未执行（A/C/D/E/F/G 待集成）**。上述未完成复选框保留，不以局部测试替代。
