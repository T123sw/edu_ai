# F：课程验收、候选恢复与准确版本交付

状态：F 所属实现与数据库回归已交付；B/D/E 主流程接线、原生 Harness 语义效果和 G 浏览器闭环仍待集成。不能将本记录解释为整条准备链路已完成。

## 版本与范围

- 共同基线：`18080783`（G 发布的 audited robustness/optimization baseline）。最初从 `67fc18b8` 创建隔离分支，随后 fast-forward 对齐共同基线。
- 实现提交：`debc7960`，只含 F 代码与测试。
- 分支：`feat/preparation-quality-20260919`。
- worktree：`/home/zxqs_ep/Edu_AI/.worktrees/preparation-quality-20260919`。
- 只修改 F 所属的 artifact_store、quality、delivery、失败/候选/定位新模块、课程审阅 Skill 与对应测试。未修改 B 的 generation adapter、D/E 生成器、G 的迁移和 pipeline。
- 无数据库迁移。私有候选复用 artifact JSON；未审阅正文不会成为 draft 或挂入课程。

## 实际行为与上限

`FailureDetail`/`GenerationFailure` 保留 category、phase、retry_scope、artifact/content 身份。未知旧错误没有可安全恢复的分类时明确停止，不猜测为正文错误。权限、预算、取消以及 retry_scope=none 均停止。

`ArtifactStore.checkpoint_port(child)` 返回不可序列化到模型上下文的服务器能力。保存前验证子租约、父 attempt、取消、owner、授权、记忆 epoch/引用、规格和正文摘要。候选绑定 preparation、artifact、资源 ID/版本及教学上下文摘要。父 worker 在等待子任务时可以正常释放租约；父恢复入口必须持有当前有效父租约。候选跨显式父 attempt 不自动复用，审计正文保留。

`ArtifactStore.resume_review(parent, artifact_id, recovery_key=...)` 建立可回读恢复意图：

- `review_format` 保持正文、spec、资源 ID/版本不变，仅新增恢复 attempt；review-only 中改写正文会被拒绝。
- provider 故障保留已有候选；写正文前的 provider 故障允许返回无候选的重试意图。
- 同一 recovery_key 重放返回同一 job 引用，含子任务已保存而父回执丢失的情况。
- 不同 worker 受父/子 SQL 锁串行化。每份候选最多两次恢复；父生产修复最多两轮；课程审阅每个 scope 最多两次格式纠正。D/E 内部重试同样必须有界并使用真实预算记账。
- content/render/contract 返回原受影响资源的修复路线；传递既有正文作为修改基线，并提高 spec revision。不会重写无问题资源。保留资源有问题时要求明确单独修订。

逐节点课程审阅现在携带完整正文、原始 request、teaching_context、落实映射、生成状态及用时口径；最终整课审阅仍使用已绑定输入摘要的节点审阅，不重复塞入所有正文。节点和资源 limitations 保留到最终 manifest。

v2 定位校验检查实际 section/question/scene/action ID、所属节点目标与需求、场景内 action/question 归属。课堂真实题目允许 `{scene_id, question_id}` 审阅定位；尚不生成正式 manifest classroom check。quiz checks 指向原生题目 ID，每项仅覆盖实际绑定目标。v1 报告自测只在实际存在“学习检查”章节时保留旧式检查，不能凭空制造章节。

时间汇总分离节点预算、资源 estimated/measured/unknown 与未验证交互用时。硬时限下必需资源用时未知或超限明确失败，不能用节点 minutes 充当资源测量值；语义审阅还需判断估算是否包含作答/反馈。F 不校准虚构时长、不缩小数字绕过硬约束。

课程门禁版本提高为 `preparation-delivery-v3`，摘要绑定实际 spec/context/content、资源 ID/版本、路线、证据和记忆。commit 再核验 DB 内容和规格原文、资源身份、检查位置、保留原件摘要与权限、基准版本、父任务状态，仍用单事务写材料/manifest/指针/成功事件。旧已提交版本继续可读；旧审阅回执必须重新经过当前课程门禁。ResourceSpec 的旧原始 JSON 摘要不因新增默认字段而被重算。

## 参数追踪

| 输入 | 消费者 | 实际证据/门禁 |
| --- | --- | --- |
| request.goal/requirements | 逐节点原生课程审阅（B 接线） | 原始全文与教学上下文均进入独立审阅；真实审查反例测试验证拒绝后局部修复 |
| spec.objective_ids + teaching_context | resource_alignment | 仅真实本节点目标可绑定真实 native locator；quiz checks 回读题目 |
| applied_requirements | resource_alignment + 课程审阅 | requirement ID、完整覆盖、非空解释与真实位置；语义充分性仍需原生审阅 |
| plan.nodes.minutes | duration_summary | 节点预算列，与资源实际/估算用时分列 |
| request.overrides.total_minutes | review/commit | 必需资源未知或超时不能交付 |
| memory refs/epoch | ArtifactStore/DeliveryService | 删除或变更后拒绝恢复/提交 |
| artifact spec/context/content/version | check_digest + commit | 修改任一真实值使旧 pass 失效；DB 篡改不能留下就绪指针 |

## 给 B：必须接入的接口

1. 在 handler 成功 claim 后创建 `port = store.checkpoint_port(artifact)`，以 `checkpoint=port` 传给 D/E。不能放进 payload、prompt 或工具 schema。
2. 捕获 `GenerationFailure` 后使用 `store.fail(artifact, exc.detail)`；`fail` 接受 FailureDetail、其字典或异常，旧 code 字符串保持兼容，但不允许推断重试类型。
3. 实现 `GenerationAdapter.resume_review(context, artifact_id, *, recovery_key)`：先调用同名 store API；根据其 `job_id` 查 durable queue，缺失时 enqueue 同一 job ID/idempotency key，原 workflow/owner/preparation/截止时间不变。回读核验 owner、command 和 job ID 后返回 store receipt。队列响应丢失时用同一 recovery_key 重放；不能再指向最初失败的 job。
4. quality.repair 已调用该接口并更新 `generation_receipts[digest(spec)]`。B 必须确保 read_result 查询新的 recovery job；未接入时明确报 `RESOURCE_RECOVERY_UNAVAILABLE`，不会偷偷重新生成全文。
5. 注册 `review-course-delivery` Skill 并将 `phase=course_review` 路由到原生 Harness；保持独立审阅会话和真实 completion usage/Skill 证据。F 不编辑 B 的注册表/adapter。
6. provider 的单调用暂时性错误首先在当前调用预算中重试；队列级 retry_scope=provider 只是故障恢复边界，不能重放已成功的模型调用。

## 给 D/E：候选使用样例

```python
saved = checkpoint.load_review_candidate() if checkpoint else None
if saved:
    body, review_state = saved['content'], saved['review_state']
else:
    body = write_with_metered_gateway(...)
    review_state = {'decision': 'pending'}
    if checkpoint:
        checkpoint.save_review_candidate(
            content=body, content_digest=digest(body),
            spec_digest=server_spec_digest, review_state=review_state)
# 使用独立审阅；格式错只补审阅；只有内容错才进入定向修订。
# 失败 detail 由服务端生成，消息必须脱敏，不能塞 provider headers/凭据。
```

`digest` 是 course_preparation.tool_registry.digest（规范化 JSON UTF-8 SHA256，字符串也按 JSON 编码）。候选正文可为字典或字符串，必须使用同一算法。v2 `generation_state.preparation` 按共享契约绑定 spec/context 摘要并带实际映射和用时。课堂另保留 E 的 render_checks；failed/缺失渲染检查不能通过 F 的 v2 门禁。渲染器的真实媒体可用性探测、音频失效和浏览器播放仍由 E/G 负责。

## 给 G：装配与验收

- 不需要 migration，不扩展 CheckLocator。合并 A/B/D/E 后运行下述同一组测试，并加入其各模块测试。
- `supplement_node` 保留原节点资源/路线；`revise_resource` 重建被替换资源真实检查位置；公共原件仍保留；`adjust_course` 保留资源要求 DB 原文摘要吻合。
- 学习端回读：打开新 manifest、读取确切资源版本；历史 manifest 可读；生成成功不自动写掌握。既有 prepared_learning/merge_learning_integration 在本模块回归中运行。
- 真实服务验收仍需补：B 的恢复队列/新回执全链路、D/E 原生 Harness 错误注入及审阅计量、真实生成新版本绑定、必需媒体播放、浏览器局部操作。单测的脚本化 critic 不代表真实模型能稳定识别反例。
- 真实审查 fixture 已用于检查题位置回读和“顺序错误/选项 C 解析错误”局部拒绝路径；语义 critic 在测试中是脚本化失败回执，未伪称模型效果通过。

## 验证命令

使用独立 PostgreSQL UTF-8 数据库，同时运行 SQLite 参数。测试入口禁用 dotenv，绝不读取业务 .env。

```bash
COURSE_PREPARATION_ENABLED=false \
PREPARATION_TEST_DATABASE_URL='<isolated PostgreSQL URL>' \
LEARNING_TEST_DATABASE_URL='<isolated PostgreSQL URL>' \
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PY'
import dotenv, pytest
dotenv.load_dotenv = lambda *args, **kwargs: False
names = ['resource_alignment', 'review_resume', 'quality_stages', 'delivery',
         'local_manifest', 'lifecycle_guards', 'prepared_learning',
         'merge_learning_integration', 'generation_adapter']
raise SystemExit(pytest.main([
    *(f'backend/src/tests/course_preparation/test_{name}.py' for name in names), '-q', '-ra']))
PY
```

初次 PostgreSQL 临时库默认 SQL_ASCII 导致 psycopg 版本查询返回 bytes，40 项初始化错误；新建 UTF-8 隔离库后复测。该环境失败保留说明，不计作产品用例通过。最终结果与日志见本记录末尾。


## 最终测试记录

| 范围 | 通过 | 跳过 | 说明 |
| --- | ---: | ---: | --- |
| 九个模块文件回归 | 104 | 4 | SQLite + 独立 PostgreSQL；4 项是 SQLite 不执行的行锁分支，PostgreSQL 对应分支均通过 |
| 恢复/定位/审阅补充回归 | 41 | 1 | 覆盖新增的恢复回执保留；跳过为 SQLite 行锁分支 |
| 最终新增场景 | 4 | 1 | 子任务先保存后找回回执、取消恢复竞争与费用结算、真实课堂题目定位 |
| 最终定位/课程审阅回归 | 20 | 0 | 包括不得以 limitations 掩盖失败 render_checks |

各组有重叠，不相加作为独立用例总数。代码检查 `git diff --check` 通过。

证据：[主要回归](artifacts/2026-09-19-preparation-quality/regression.txt)、[恢复专项](artifacts/2026-09-19-preparation-quality/recovery-final.txt)、[新增场景](artifacts/2026-09-19-preparation-quality/final-additions.txt)、[最终定位检查](artifacts/2026-09-19-preparation-quality/alignment-final.txt)。

PostgreSQL 是本次自建的临时 UTF-8 隔离库；未运行付费模型、未读取业务配置、未迁移业务库。真实来源是仓库已经保存的审查样本，新增语义审阅使用脚本化 critic。其他窗口的在途改动没有混入本模块提交；G 可从共同基线 cherry-pick `debc7960` 及本记录的文档提交。
