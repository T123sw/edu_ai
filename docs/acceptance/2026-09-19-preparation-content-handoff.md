# D 报告、习题与资源审阅交接

D 模块实现与资源级验收完成：v2 教学上下文驱动正文；报告、习题和课堂支持私有候选审阅恢复；旧 Harness 报告审阅策略已恢复。最终整课交付与浏览器验收仍归 G，本文不声明全链路完成。

实际起点 `67fc18b85ffbd82406c5ab33703eff8ea627c222`；分支 `feat/preparation-content-20260919`，工作树 `.worktrees/preparation-content-20260919`。已合入 G `18080783`、A `c264070f`、F `debc7960`；这些依赖保持原提交，不混写 D 文件。D 提交为 `ee818810`（策略）及 `3157cb4f`（初始正文/恢复），后续修复 SHA 见文末。G 可按自身已集成依赖，单独 cherry-pick D 提交。

## 接口与装配

- `generate_reviewed_report(payload, gateway=None, *, initial_body="", initial_feedback=None, checkpoint=None)`。
- `ReviewedResourceGenerator(gateway=None, review_gateway=None, progress=None, *, checkpoint=None)`。
- `review_classroom(content, config, gateway=None, *, checkpoint=None)`；保持返回 `(content, resource_review)`，E 包装 `generation_state.resource_review`，场景/动作和音频失效语义保持。
- 准备调用消费 B `harness_generation.scoped_gateway`，显式 `resource_write` / `resource_repair` / `resource_review`；课堂修复为 `classroom_repair`。旧工作台没有准备策略时使用原网关。调用器不猜测提示词阶段，不新增资源规划调用。
- B 必须给所有使用 checkpoint 的 payload/config（包括 v1）填入服务端 artifact 的 `spec_digest`；v2 直接消费 A `automatic_payload`。checkpoint 是服务端对象，不进入 prompt。
- B 注册 `generate-learning-resource`、`review-learning-resource`。Skill 已包含正文写作、逐选项判断、逐分句解析判断及教学顺序要求。
- v2 写作一次返回 `{content, applied_requirements, objective_bindings}`；content 仍是 Markdown/原生 quiz。报告使用 `<a id="section-id"></a>` 加实际非空二级章节，locator=`{"section_id":"section-id"}`；习题使用原生题目 id，locator=`{"question_id":"q1"}`。这些位置已通过 F 实际解析器验证。
- `generation_state.preparation` 保存 spec/context 摘要、需求/目标定位及带方法的时长信息。审阅中的 `preparation_sha256` 绑定完整元数据，删除元数据不能降级旧回执。独立 `preparation_checks` 核验位置中的实际语义。
- 习题审阅由服务器回填 question_id/option_text，验证解析摘录确在原文；选项真假与解析真假各自返回 reasoning / explanation_reasoning，正确答案不掩盖干扰项解析错误。新回执 `option_binding_version=1` 要求完整证据，旧回执保持原读取能力。
- report/quiz 的局部修复使用原生精确 edits，保留稳定身份；仅映射错误时允许 edits=[] 更新映射，正文摘要不变。正文修复后重新审阅；旧通过回执不能复用。

## F 检查点和失败协议

保存内容是原生正文：报告字符串、习题/课堂字典。`content_digest` 使用 F `tool_registry.digest` 的规范 JSON 摘要；既有报告审阅 `content_sha256` 仍是原始 UTF-8 摘要，两者不能混用。

`review_state` 含 version/history/preparation，正文错误时另含 needs_repair/feedback。格式故障保留待审正文，恢复不调用 writer。失败使用 `GenerationFailure(FailureDetail(...))`：

| 情况 | category | retry_scope |
| --- | --- | --- |
| 审阅 JSON/覆盖格式失败 | review_format | review |
| 内容最终拒绝或重审发现语义错误 | content | content |
| 无效定位、正文/规格/元数据摘要变化 | contract | none |

F 已授权 `recovery_scope=review` 时，重审发现正文错误会在调用 writer 前交回 content 失败，由 F 创建修订，不在仅允许重审的候选上偷改正文。

SQLite 实际 ArtifactStore / ArtifactResourceCheckpoint 验证了 fail → resume_review → 新 lease → 新端口恢复。另有独立 Python 进程恢复报告用例：合计 writer=1、review=2，正文摘要不变。报告、习题、课堂的格式恢复、正文/摘要/规格篡改、错误解析精确修复均有测试。未使用 mock checkpoint 冒充持久化。

## 旧策略兼容依据

历史 `c599f7af` 的 generation_task_handlers.py:227、:778 按 harness_outline_id 强制生成审阅与发布校验；当时 GenerationCommand 没有 review_policy。当前 Harness 调用链为 `runtime.py:409 → tools.py:726–759 → generation_command.py:253–268 → durable_task_executor.py:232–244`，生产 required 与服务端标志。普通入口 `chat/api/routes_v2.py:662–684`、`agent_tools/handlers/report.py:120–146` 使用 standard 默认；standard_resources.py:223–235 显式 required。

同一策略函数用于生成器选择、payload 最后归一化、报告 adapter 和发布守卫。required 或服务端 true 优先；无新字段的旧 Harness 继续强制审阅；普通显式 standard 保持旧行为；客户端 standard 不能覆盖服务端 true。三个原失败用例均保留并通过。

## 参数到实际产物

证据目录：[原生资源与反例](artifacts/2026-09-19-preparation-content/)。

| 输入 | 消费方式 | 产物证据 |
| --- | --- | --- |
| requirements=req-order，先例后理 | 按 learning_activities 直接组织正文 | native-report-example_first.json：example-add → missing-param → division-of-labor → self-check |
| 相反要求，先理后例 | 同一主题改变正文顺序 | native-report-theory_first.json：what-is-tool-call → responsibility → example-add → self-check |
| 基础=会 Python/无 Agent 基础、中文、introductory、排除面试话术 | 基础解释、短代码和职责说明 | 上述两份报告实际使用 add 例子，无面试表达模板 |
| objective_ids=职责/缺失参数 | 逐题具体绑定 | native-quiz-example_first.json：q1 检查职责、q2 检查缺失参数，未机械绑定全部目标 |
| node_budget_minutes=10，resource_target_minutes=null | 节点上限共享，资源分别给估算方法/unknown | 报告约 1.7/2.5 分钟字符阅读估算；习题 unknown，未伪造各自10分钟 |
| source_policy=uploaded_only | 只提供给定 add 材料，没有联网工具 | 写作与审阅的原生工具仅提交文本；来源语义由审阅检查 |

原生证据包含真实 SDK runtime、phase、Skill name/sha256/loaded、provider/model、usage。B 源码来自当时主工作区的固定快照，哈希清单为 native-dependency-snapshot-v1.json（首轮）和 native-dependency-snapshot.json（解析理由增强后）。真实测试的 usage ledger 使用内存收集；SQL 候选恢复另以实际 F 适配器验证，未冒充整课数据库交付。

首次原生习题曾产生“模型校验参数，程序计算”的部分真/部分假选项，并把正确的“程序计算”也判错；旧审阅误放行。保留 native-quiz-first-pass-counterexample.json，不将它当合格产物。新增 explanation_reasoning 后，同一正文在 real-mixed-claim-review.json 被拒绝；最终 native-quiz-example_first.json 的解析仅批评“模型校验参数”，正文与选项判断回读一致。原始审查中的“执行/选择”偷换反例也在 real-counterexample-review.json 被真实模型拒绝。模型审阅仍非全面事实核查。

## 验证命令与边界

统一前缀：`COURSE_PREPARATION_ENABLED=false PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python`；测试入口先将 `dotenv.load_dotenv=lambda *a, **k: False`，不自动读取业务配置。

综合 pytest 文件：test_reviewed_report、test_harness_resources、test_report_review_policy、test_generation_task_handlers、test_generated_content_constraints、test_review_counterexamples、test_generation_context、test_resource_alignment、test_review_resume。最近综合结果 **198 passed / 28 skipped**；跳过项为隔离 PostgreSQL 未配置/仅 PostgreSQL 锁竞争，以及另行执行的真实模型用例。最后小范围改动的复测结果见文末。

真实模型实验以 `D_CONTENT_ENV_FILE` 显式指定配置，仅进程内读取凭据：

- `D_CONTENT_REAL_MODEL=1`：两个相反顺序报告、原始解析反例、新发现的混合断言反例；均分别通过。
- `D_CONTENT_NATIVE_MODEL=1`：真实原生 Harness 两种顺序报告通过（2 项）；习题首次外层格式冲突修复后通过，解析理由增强后再次运行通过（1 项）。最终证据已回读。
- `D_CONTENT_EVIDENCE_DIR` 指向上述证据目录。快照包只包含代码/Skill；凭据、数据库和构建产物不进入提交。

没有数据库迁移，没有业务库写入，没有修改默认资源组合。旧 v1 规格及旧大纲读法保留。新 v2 缺失必要映射或新审阅字段会明确拒绝，不靠降级旧格式绕过。G 仍需在 A/B/C/D/E/F 最终共同 SHA 上跑 handler 装配、整课交付及浏览器验收。

## 最终提交与复测

- D 代码提交：`ee818810e6ae50aa9ef005751e6a66eea5947035`、`3157cb4f`、`3e4d613c3b9a29693745cc2fd7b614cd0662eb5c`。
- 最新受影响范围（报告、全部 Harness 资源、新约束与反例）：**92 passed / 17 skipped，26.11 秒**。这次包含重审拒绝结果保存后的再次重放，以及跨独立 Python 进程恢复。
- 最近综合 **198 passed / 28 skipped，36.00 秒**；最后改动仅增强原解析理由反馈和 review-only 重放保护，以上 92 项覆盖最终改动。
- 原生报告 2 项通过；最终原生习题 1 项通过（32.49 秒）；同一混合断言反例真实重审 1 项通过（20.04 秒）。这些结果与默认 pytest 的 opt-in 跳过分开记录，不相加冒充统一测试总数。
- 版本控制：代码、D 计划更新、回读产物、历史失败及验证记录均提交；保留独立分支，不推送，不合并用户主工作区。

最终受影响测试的实际执行方式：

```bash
COURSE_PREPARATION_ENABLED=false PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PYTEST'
import dotenv, pytest
dotenv.load_dotenv = lambda *a, **k: False
raise SystemExit(pytest.main([
    'backend/src/tests/chat/test_reviewed_report.py',
    'backend/src/tests/chat/test_harness_resources.py',
    'backend/src/tests/course_preparation/test_generated_content_constraints.py',
    'backend/src/tests/course_preparation/test_review_counterexamples.py',
    '-q', '-ra', '--tb=short',
]))
PYTEST
```

D 代码/测试文件（不含依赖 merge 的文件）：

- `backend/src/app/chat/harness/preparation_content.py`
- `backend/src/app/chat/harness/review_policy.py`
- `backend/src/app/chat/harness/reviewed_report.py`
- `backend/src/app/chat/harness/reviewed_resource.py`
- `backend/src/app/course_preparation/skills/generate-learning-resource/SKILL.md`
- `backend/src/app/course_preparation/skills/review-learning-resource/SKILL.md`
- `backend/src/app/services/generation_task_handlers.py`
- `backend/src/tests/chat/test_harness_resources.py`
- `backend/src/tests/chat/test_report_review_policy.py`
- `backend/src/tests/chat/test_reviewed_report.py`
- `backend/src/tests/course_preparation/test_generated_content_constraints.py`
- `backend/src/tests/course_preparation/test_review_counterexamples.py`
