# 课程准备 Agent 分阶段实施计划

> **For agentic workers:** 按 `writing-plans` 整理的可执行计划。按用户要求逐阶段实施和验收；执行方式服从当前会话授权与仓库规则，不因技能建议额外暂停请求确认。状态复核以本文检查框和验收记录为准。

**Goal:** 从一句学习需求及可选资料出发，自主交付版本化课程，并支持学习 Agent 发起的个人补充和修订。

**Architecture:** 独立 preparation 运行上下文与服务端可恢复工具调用循环，复用现有模型网关、durable runtime、来源/生成服务及适用的 Harness 资源规范。模型选择教学动作，确定性服务负责权限、状态、预算和原子提交；已提交 manifest 是学习端交付事实。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、PostgreSQL、Alembic、现有 ChatModelGateway 的严格工具调用适配；前端 React/TypeScript。

**Spec:** [主设计](../../architecture/2026-09-17-course-preparation-agent-design-cn.md)、[具体设计 V1](../../architecture/2026-09-17-course-preparation-agent-technical-design-cn.md)、[学习侧设计](../../architecture/2026-09-17-learning-agent-design-cn.md)。

**运行核心补充（2026-09-17）：** [记忆、工具与决策协议](../../architecture/2026-09-17-course-preparation-agent-runtime-design-cn.md)明确根角色、记忆生命周期、上下文预算、完整工具目录/挂载矩阵、策略与 Harness 取舍、严格传输和恢复。P2/P3 必须先阅读该文；研究与路径主体切片进度见下方当前状态。


## 2026-09-17 实施对账

本计划 P1—P7 的运行能力已落地，阶段提交与原始通过/失败日志见[全阶段账本](../../acceptance/staged-agent-implementation/README.md)，完整验收见[最终报告](../../acceptance/staged-agent-implementation/final-report.md)。勾选表示行为已实现并有对应测试，不表示已在业务环境启用。以下测试文件名是原规划；实施时按职责合并，映射如下，不能直接复制不存在的旧文件名执行。

| 阶段 | 实际主要测试文件（backend/src/tests/course_preparation/） |
| --- | --- |
| P1 | test_contracts.py、test_repository.py、test_migration.py |
| P2 | test_runtime_foundation.py、test_lifecycle_guards.py、test_stage_api_runner.py、test_runtime_migration.py、test_research_persistence.py |
| P3 | test_research_adapters.py、test_research_flow.py、test_context_memory.py、test_shared_memory_runtime.py、test_source_policy.py、test_document_adapter.py、test_citation_locator.py |
| P4 | test_generation_adapter.py、test_resource_reuse.py、test_native_classroom.py |
| P5 | test_quality_stages.py、test_delivery.py、test_local_manifest.py、test_publication_overlay.py、test_prepared_learning.py |
| P6 | frontend/tests/live-learning/preparation.spec.ts、agent-full.spec.ts；真实上传课程全资料浏览器验收 |
| P7 | test_notifications.py、test_route_adjustment.py、test_publication_overlay.py；学习侧 test_preparation_adapter.py；真实补充、修订、共享个人修订、路线调整 |

实现落点有意收敛：独立 lifecycle_repository/后台 worker 负责整课状态，子资源复用 durable task 队列；模型严格适配沿用 research/model 路径；只改时间且明确保留资料的路线调整使用旧版本证据和正文审阅，不强制重新搜索。服务端引用句柄代替模型重抄引文。课堂为实际可播放 DSL，并不包含未要求的外部配音采购。PDF/DOC 真实解析与 MD 真实上传有独立日志，DOCX、空扫描/缺页使用固定样本测试，未宣称扫描识别普遍成功。

最终真实面试准备一次 attempt 完成四节点、12 份资料；保留了运行内 5 次有界协议/规划纠正，无人工修改该任务。后续学习侧“选定后再提交”澄清修复不改变准备代码。来源质量和样本量限制仍列在最终报告，运行验收通过不等于内容已达到出版标准。

## 全局约束

- 准备中无人工大纲确认和隐含保存审批；默认全部核心内容满足门禁后才提供新课程学习入口。
- 只复用现有服务，不增加总控 Agent，不让两个 Agent 递归聊天。
- 请求身份来自服务端；模型和上传正文不提供授权；每次读取与写入都校验当前权限。
- 个人交付不等于公共发布；共享课程修订保存为个人 overlay。
- 所有版本与学习事实可追溯；重排不重建稳定节点 ID，不把资源生成解释为学习完成。
- PostgreSQL 为新任务事实源；SQLite 只用于单元测试，不是部署降级路径。
- 保留当前工作区既有改动；每阶段只修改其明确涉及的文件。阶段验证通过才更新状态，不预填验收成绩。

## 1. 阶段总表与依赖

早期优先切片（历史记录，已由整课流程覆盖）：先实现“意图→真实检索/正文读取→证据汇总→学习路径→独立审阅”。它是 P2/P3 的研究路径阶段，不提前实现资源生成。独立 `research-runs` 任务保存检查点、预算、租约与结果，状态成功仅代表研究路径完成，返回 `course_ready=false`；后续整课准备可消费该阶段产物。首版仅接新需求和开放网络来源，上传/已有课程调整在入口明确拒绝，不擅自降为无资料规划。

- [x] 研究契约与测试：要求、证据及原文定位、汇总、路径节点/先修/时间/覆盖映射。
- [x] 严格模型与检索适配：一轮一个 schema 工具动作，实际取得正文才能引用，有限搜索与修正。
- [x] 主循环：理解意图、研究、汇总、规划、独立审阅；保存每步状态并按有效检查点恢复。
- [x] 持久化后台任务：原子接收/去重、租约、取消、预算跨恢复、owner 隔离；不依赖页面存活。
- [x] HTTP 创建/状态/取消接口和命令行真实模型 smoke，保存完整路径与来源供验收。

验收与启动方式：[研究与学习路径阶段](../../acceptance/2026-09-17-course-preparation-research-path-cn.md)。整课后续阶段已实施；最新结果见下方实施对账。

| 阶段 | 目标及交付 | 依赖 | 状态 |
| --- | --- | --- | --- |
| P1 | 强类型请求/manifest/事件契约；授权端口；任务、首次 attempt、接收事件的原子持久化；迁移 | 无 | 已完成本地验证，见 [P1 验收](../../acceptance/2026-09-17-course-preparation-agent-p1-cn.md) |
| P2 | API、运行契约、工具注册/分发、执行租约、检查点、取消/重试、动作与预算及事件恢复 | P1、运行核心设计 | 已实施并隔离验证，见整体验收 |
| P3 | 严格模型传输、记忆生命周期接入、上下文/策略装配、文件输入、两类研究与规划 | P2 | 已实施，含上传、记忆失效和真实研究 |
| P4 | 按节点复用/生成资源、准确版本回读、子任务并发和局部修复 | P3 | 已实施并隔离验证 |
| P5 | 分层检查、版本冲突、manifest/overlay 存储与原子交付 | P4 | 已实施并隔离验证 |
| P6 | 首页提交/上传/真实状态/恢复/完整课程入口 | P5 | 已实施并隔离验证 |
| P7 | 学习 Agent 补充、修订和课程调整；版本通知与学习连续性 | P5、P6 | 已实施并隔离验证 |

技术设计原阶段 A 的契约与存储基础落在 P1，实际版本提交落在 P5；原 B→P2，C→P3，D 拆为 P4/P5，E→P6，F→P7。此拆分使每阶段可单独验收，避免提前实现尚无输入证据的提交服务。

阶段完成含义：代码和所列本地验证完成。真实供应商、前端联调和部署迁移分别记录，不以基础单元测试代替整套 Agent 验收。

## 2. 文件与接口边界

新增 `backend/src/app/course_preparation/`，P1 只创建 `schemas.py`（请求）、`manifest.py`（交付清单）、`contracts.py`（任务/事件/授权端口）、`app/database/models.py`（准备任务 ORM，沿用项目集中定义）、`repository.py`（事务接收与查询）及包入口。

P2 增加 `service.py`、`runner.py`、`runtime_contracts.py`、`tool_registry.py`、`tool_dispatcher.py`、`policy.py`、`api/course_preparations.py`。P3 增加 `model_adapter.py`、`context.py`、`working_memory.py`、`summary_service.py`、`tools.py`、`adapters/memory.py`、`adapters/sources.py` 与版本化 `prompts/`；共用记忆生命周期扩展归 `app/chat/memory/`。P4 增加 `adapters/generation.py`。P5 增加 `quality.py`、`delivery.py` 和版本仓储。P6 修改 `frontend/src/liveLearning/` 的真实入口。P7 增加学习侧 `preparation_adapter.py`。

P1 仓储接口：

```python
accept(*, owner_user_id: str, request: PreparationRequest) -> PreparationSnapshot
get(*, owner_user_id: str, preparation_id: str) -> PreparationSnapshot
events(*, owner_user_id: str, preparation_id: str,
       after: int = 0, limit: int = 100) -> list[PreparationEvent]
```

它是服务内部端口，调用前必须由服务端身份派生 owner，并通过 `PreparationAuthorizer.authorize(owner_user_id, request)` 校验引用。P1 不注册生产 API，不提供通用状态任意写入口，不执行模型或创建课程。

## 3. P1：契约与原子接收

### P1.1 请求和课程产物

文件：`course_preparation/schemas.py`、`manifest.py`、`contracts.py`；测试 `tests/course_preparation/test_contracts.py`。

- [x] 先写拒绝非法组合的测试，再实现四种 operation 的输入约束。新建不允许 target；补充必须有节点及 manifest 基准；资源修订增加准确资源及版本；路线调整增加路线基准和明确变更。嵌套对象均拒绝未知字段，特别是 owner、公共写入、execution_mode。
- [x] 来源缺省按上传存在与否解析为 `uploads_preferred/open`；`uploaded_only` 无文件拒绝。上传版本为正整数，同一 document 不重复加入。规范化后计算 SHA-256，幂等比较整个请求，不只比较 goal。
- [x] 定义 manifest 的稳定节点、目标、资源准确版本、检查定位。拒绝重复 ID/顺序、不存在先修、逆序/循环、未知目标、核心内容或检查不覆盖目标、检查指向错误资源版本。
- [x] 定义 accepted/running/checking/succeeded/failed/canceled 与具体阶段；事件信封和快照固定 schema 版本。

关键行为测试：

```python
def test_client_cannot_supply_owner():
    with pytest.raises(ValidationError):
        PreparationRequest.model_validate({
            'request_id': str(uuid4()), 'operation': 'create_course',
            'goal': '学习递归', 'owner_user_id': 'someone-else',
        })
```

执行 `python -m pytest tests/course_preparation/test_contracts.py -q`；首次因模块缺失失败，实现后全部通过。schema 校验只验证结构，不代表内容正确或资源存在。

### P1.2 持久化与授权端口

文件：`app/database/models.py`、`course_preparation/repository.py`、`database/__init__.py`；测试 `tests/course_preparation/test_repository.py`。

- [x] 三张表保存 preparations、attempts、events。用户/请求 ID 唯一，attempt 为 `(preparation_id, attempt_no)` 复合主键，事件 `(preparation_id, sequence)` 唯一且通过复合外键绑定 attempt。
- [x] `accept` 在同一事务写任务、首次 attempt 和 accepted 事件；异常回滚，服务端生成 preparation/event ID，禁止产生半条任务。
- [x] 在任何接受/重放前执行 authorizer；查询按 owner 过滤再复核资源访问。未找到与他人任务均抛 `PreparationNotFound`，不泄漏他人任务存在性。
- [x] PostgreSQL 并发插入依赖唯一约束决出唯一任务；冲突后回读规范化哈希，同内容返回同任务，不同内容抛 `IdempotencyConflict`。异常处理不能吞掉与幂等无关的完整性错误。
- [x] `events` 使用严格大于 after 的 sequence 游标并限制页大小；返回值为 schema 对象，无 ORM 会话泄漏。

关键测试：

```python
first = repo.accept(owner_user_id='alice', request=request)
again = repo.accept(owner_user_id='alice', request=request)
assert first.preparation_id == again.preparation_id
assert len(repo.events(owner_user_id='alice', preparation_id=first.preparation_id)) == 1
```

### P1.3 迁移和验收记录

文件：`alembic/versions/20260917_0022_course_preparation_intake.py`；测试 `tests/course_preparation/test_migration.py`。

- [x] 新迁移从当前 head `20260910_0021` 追加，只建立准备接收表；历史课程、材料和任务不改写。
- [x] 在独立 PostgreSQL 测试 schema 执行本次 upgrade、仓储测试、downgrade；同时编译离线 PostgreSQL DDL。不可对用户业务库执行破坏性测试。
- [x] 验证多线程同请求只建一个 preparation/attempt/event、任一插入失败全部回滚、进程/引擎重新打开仍可恢复、权限撤销后无法重放。
- [x] 验收记录列出运行环境、命令、通过数和未覆盖项；不注册尚无 worker 的公开创建接口。

## 4. P2：可恢复后台执行

先按运行核心设计定义 `ExecutionContext/ToolSpec/ContextPacket/ModelDecision` 及工具结果信封。P2 使用可控假模型验证调度与副作用，不将现有 Harness 会话直接作为长期任务。

- [x] `test_tool_registry.py` 验证阶段×operation×source_policy×能力×预算筛选，未挂载工具不可执行，schema/handler 配对完整；实现冻结 `tool_set_digest`。
- [x] `test_tool_dispatcher.py` 验证全部参数先校验，再记录意图/额度；一响应最多一个写动作或四个只读动作，混合批次整体拒绝且零副作用。身份/租约由 ExecutionContext 注入。
- [x] `test_runner_no_progress.py` 验证只说计划、反复相同读取、空工作记忆补丁不能无限运行；每 step 上限与整任务预算分别累计。
- [x] 阶段转换统一经 `propose_next_stage` 对应服务核验，程序跳过无上传阶段也记录原因。来源撤权后公开状态仍允许 owner 读取经脱敏的错误，内部上下文继续严格拒绝失效来源。

任务及接口：`PreparationService.submit/get/cancel/retry`；`PreparationRunner.run_step(preparation_id, attempt_no, lease_token)`；仓储扩展 `claim/heartbeat/save_checkpoint/finish_attempt`。schema 均复用 P1，新增字段单独迁移。

- [x] `tests/course_preparation/test_lifecycle.py` 写合法/非法状态转换、终态禁止改写、重试保留旧 attempt、revision 冲突、取消先于提交的用例；实现 service 和状态转换表。公开请求经现有登录依赖和真实引用 authorizer。
- [x] `test_runner_recovery.py` 写 worker 租约过期后旧 token 写入失败、检查点输入变化失效、空闲时释放 worker 的测试；实现 claim、fencing token 和有界步骤。
- [x] `test_action_dispatch.py` 模拟子任务已提交但返回未记录时崩溃；持久化 action 意图和唯一副作用键，恢复先查询已有任务再提交。
- [x] `test_budget.py` 并发预留额度不能超支，重试不重置总时限，子生成内部修订计入相同账本。实现时间/tokens/调用次数/估算费用的 reserved/consumed 结算。
- [x] `test_events_api.py` 验证 after 游标、重复通知、迟到 attempt 状态不会覆盖新状态。实现事件流与状态快照；子任务完成与周期对账唤醒父运行。
- [x] 在 `durable_job_runtime.py` 注册步骤 handler，在 `bootstrap.py` 注册路由；发布功能开关默认关闭，在测试应用打开。

恢复不变量：

```python
assert late_worker_save(old_token).error_code == 'STALE_LEASE'
assert recovered_action.child_job_id == previously_submitted_job_id
assert canceled_attempt.result_ref is None
```

验收命令：`python -m pytest tests/course_preparation/test_lifecycle.py tests/course_preparation/test_runner_recovery.py tests/course_preparation/test_action_dispatch.py tests/course_preparation/test_budget.py tests/course_preparation/test_events_api.py -q`。正常情况从 202 响应后由后台继续，HTTP 断线不取消任务。

新增门槛命令：`python -m pytest tests/course_preparation/test_tool_registry.py tests/course_preparation/test_tool_dispatcher.py tests/course_preparation/test_runner_no_progress.py -q`。以上未完成不能只以任务能排队宣称 P2 运行骨架完成。

## 5. P3：输入、研究和规划 Agent

以下运行核心任务先于真实研究主链路启用：

- [x] `test_model_adapter.py` 覆盖正常 tool_calls、流截断、损坏参数、重复 ID、超时、取消和 fallback；补强现有网关严格传输路径，不把坏 JSON 转空对象，也不执行未完整响应。
- [x] `test_preparation_prompts.py` 验证独立根角色、按阶段加载受控策略、不带旧确认流程、不加载通用 Skills/MCP；代码保存策略版本和内容哈希。
- [x] `test_context_packet.py` 验证工具 schema 与协议开销计数、低预算时保留硬约束、工具调用对不拆开、中文来源分块和有界回读。
- [x] `test_preparation_memory.py` 验证工作记忆 CAS、假设不升格为用户事实、读偏好但无长期写工具、跨课程默认不读、摘要失败以结构化记录恢复。
- [x] `test_preparation_memory_invalidation.py` 与共用记忆测试验证旧 API 更正/删除同样增加 epoch、来源抑制生效、旧候选提取不复活偏好、迟到子生成只留草稿、影响范围内重新检查；生命周期未完成前不启用旧历史偏好作为替代。

共用 `memory_epoch`、偏好修订和依赖仓储由记忆域实现，准备/学习 adapter 共享，不能各自增加一套全局记忆表或重复 Alembic 迁移。

接口：`SourceAdapter.read/search/fetch` 返回版本化 EvidenceRecord；`ContextBuilder.build` 返回本步骤材料；`Planner.decide` 返回受限动作。所有结果经服务端 schema 和权限校验。

- [x] `test_source_policy.py` 检验仅文件模式禁止网络/其他库，抓取失败不能标记正文已读；实现来源策略与证据仓储。
- [x] `test_document_adapter.py` 使用 PDF/DOC/DOCX/MD 固定样本核对定位与解析状态；扫描失败、部分缺页必须进入缺陷记录，核心缺页阻止继续。复用解析服务，不伪造扫描成功。
- [x] `test_context.py` 检验当前请求覆盖偏好，删除偏好使派生缓存失效，其他节点全文不默认进入上下文；实现 brief 和相关记忆装配。
- [x] `test_planner.py` 用可控模型响应覆盖正常计划、非法工具、JSON 错误、不可满足时间预算与先修缺口。实现独立准备角色、每步可用工具集合与动作上限。
- [x] `test_research.py` 验证材料充分时不机械追加网络检索，第一轮产出结构、第二轮只补节点缺口；模型输出的 source_id 必须回查实际证据。

关键流程：

```text
normalize → ingest → research_scope → plan → research_nodes
plan 结构失败 → 带错误路径重规划（计入预算）
核心来源失败 → failed(CORE_SOURCE_UNREADABLE)
```

验收运行上述五组测试，并用一句需求、仅上传文件、解析失败三种真实样本保存 brief/证据/路线及消耗。模型调用配置不固定厂商，日志不含凭据。

## 6. P4：资源制作与回读

接口：`GenerationAdapter.submit(spec, action_key)` 返回已有 durable 子任务引用；`read_result(job_id)` 返回确切 material/version/hash；`ResourceSpec` 固定节点目标、证据、类型、必须性与输出语言。

- [x] `test_generation_adapter.py` 校验准备自动策略由服务端构造，不伪造 confirmed outline，不改变旧工作台确认行为。
- [x] `test_resource_reuse.py` 校验复用需准确版本、目标覆盖及当前权限；找不到任务和任务查询失败不能自动重生成。
- [x] `test_resource_dispatch.py` 验证并发最多配置上限、父等待释放执行槽、失败资源不影响无依赖的制作、重复唤醒不重复生成。
- [x] `test_resource_readback.py` 子任务 succeeded 但正文缺失、附件不可读或版本不符时不得标记产物 ready。
- [x] 实现局部重新生成规格 revision，旧规格产物保留；生成器内部的审阅/修订调用接父预算账本。

关键断言：

```python
assert completed_job_with_missing_artifact.resource_ready is False
assert old_workspace_requires_confirmation is True
assert resource_revision_changes_action_key is True
```

验收除适配测试外，对报告、习题、课堂三类真实产物回读结构和引用；独立媒体失败在 P5 门禁判定其是否可降级。

## 7. P5：质量与原子版本交付

接口：`QualityService.review(target_ref, input_digest)`、`DeliveryService.commit(candidate, expected_manifest_version, lease_token)`。新增 manifest、个人 overlay、活动指针、检查/问题表；不得使用可随意写 succeeded 的通用方法。

- [x] `test_quality.py` 覆盖来源/路线/内容/技术/课程整体五层检查；审阅不可用不是通过，blocking issue 无法被总分覆盖。
- [x] `test_check_invalidation.py` 验证正文、证据、路线、规则版本改变使关联检查失效；定向修订后重新审阅实际结果。
- [x] `test_delivery.py` 验证全部核心资源及明确要求类型必须就绪，可选媒体失败记录 limitation；文件存在检查和版本哈希绑定使用真实资源适配。
- [x] `test_delivery_races.py` PostgreSQL 中竞争执行取消/提交、同基准两次修订，最多一个成功，失败不切活动版本。
- [x] `test_personal_overlay.py` 验证共享原版未变、个人结果归属正确、旧 manifest 可读、知识点重排稳定 ID。
- [x] 同一事务写新 manifest/overlay、绑定、指针、attempt 成功和 outbox。投递失败靠 outbox 重试，不回滚已交付课程，不重复挂载。

交付判定：

```text
当前权限有效 AND 基准匹配 AND 当前租约有效 AND 未取消
AND 候选版本检查摘要一致 AND 所有阻塞项消除
→ 提交 manifest、指针、终态、完成事件
```

验收真实课程逐节点打开核心资源，同时对缺失资源、错误版本和取消竞争做故障注入。直到此阶段完成，准备任务成功才具备产品交付含义。

## 8. P6：首页完整闭环

文件：真实前端 `frontend/src/liveLearning/` 新增准备 API 客户端与状态组件，接入首页；课程页读取 manifest。现有演示/旧入口不作为新功能验证证据。

- [x] `frontend/tests/live-learning/preparation.spec.ts` 先写开始、刷新、离开返回、重复点击、失败重试、取消六条路径；通过 API fixture 验证精确状态。
- [x] 首页收集 goal、私有上传引用及折叠配置，使用稳定 request_id 重试；202 后保存 preparation_id。
- [x] 只展示真实阶段和缺项，不伪造百分比；终态允许查看原因和有效操作。未完成新课无学习入口。
- [x] 成功后经 manifest 打开课程，目录/推荐顺序/来源/限制可读；后台完成只展示通知，不抢导航。
- [x] 接真实后端运行上传与无上传两条完整链路，记录网络响应和所有核心资源可打开的证据。

验收同时运行前端构建、该 Playwright 用例及原 live-learning 关键路径；旧工作台和共享课程入口不可回归。

## 9. P7：学习 Agent 的局部闭环

接口：`LearningPreparationAdapter.submit` 把当前服务端用户、知识点、原请求消息与资源基准提交给准备服务；结果采用 P1 事件信封和 P5 交付引用。

- [x] `test_learning_handoff.py` 验证“解释一下”直接回答，“保存练习/改稿”才提交；目标不唯一时提交前定位，不在后台引入确认等待。
- [x] `test_scoped_operations.py` 验证补充只写指定节点，修订只写目标资源，课程调整只覆盖请求范围；模型无法扩大为公共修改或整课重排。
- [x] `test_version_continuity.py` 验证旧证据仍指旧版本；资源生成不写已学完/掌握，可靠位置映射失败时提示从章节恢复。
- [x] 前端验收通知到达时用户已切节点或正在发问：只记录原节点结果，忽略重复事件，不切回、不打断。
- [x] 联调共享课个人修订、并发版本冲突和失败重试，保留原公共内容及原学习记录。

退出条件：完整支持主设计四类请求。记录真实模型质量、耗时、费用和有限修复结果，再校准运行预算；不能将用户显式要求自动降为可选。

## 10. 后续执行规则

每次开始读取主设计、本文和上一阶段验收；核对工作区变化；先复现本阶段失败用例再实现；运行本阶段测试及受影响的现有测试；记录命令与结果后更新阶段状态。发现接口必须调整时同步请求/学习交接 schema 和两侧测试，不单边修改协议。

不需要重新询问用户是否继续已授权的阶段内工作。阶段之间以验收记录交接，尚未接真实供应商、尚未迁移业务数据库或未启用前端的能力必须明示。
