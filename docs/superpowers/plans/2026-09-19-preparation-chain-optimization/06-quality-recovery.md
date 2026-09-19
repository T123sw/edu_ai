# 窗口 F：课程验收、故障恢复与交付 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用真实正文及参数落实证据验收课程，按失败原因最小范围恢复，最终只交付准确版本的有效资源。

**Architecture:** 增强既有 review/repair/commit 阶段，复用预算、租约和原子交付。引入私有审阅候选检查点，区分 provider、审阅格式、内容、渲染和终止错误；不新增资源规划状态。

**Tech Stack:** Python、Pydantic、SQLAlchemy/PostgreSQL、现有耐久任务和原生 Harness 审阅。

**Spec:** [总计划](../2026-09-19-preparation-chain-optimization.md)、[共享契约](00-shared-contracts.md)、[审查报告](../../../acceptance/2026-09-19-preparation-agent-code-audit.md)。

## Global Constraints

- 模型通过不代替版本/内容/定位校验；不把节点全部目标机械赋给所有资源和检查。
- 旧审阅必须绑定所审阅的 spec、teaching_context 与 content；任一变化后重新校验。
- 保持现有局部补充/修订/调整范围、公共原件保护、记忆失效和原子交付。
- 重试有界；取消、失权、预算耗尽不能进入自动继续生成。

## 文件范围与接口

- 修改：`backend/src/app/course_preparation/quality.py`、`artifact_store.py`、`delivery.py`、`manifest.py`；确有需要时修改 `runner.py`、`lifecycle_repository.py` 和预算相关实现，保持公共接口兼容。
- 新建：`generation_failures.py`、`resource_checkpoint.py`、必要的 `resource_alignment.py`。
- 新 Skill：`skills/review-course-delivery/SKILL.md`；注册和 course_review SDK 路由交 B。
- 测试：`test_quality_stages.py`、`test_delivery.py`、`test_local_manifest.py`、`test_lifecycle_guards.py`、新 `test_review_resume.py`、`test_resource_alignment.py`。
- `adapters/generation.py` / `test_generation_adapter.py` 由 B 拥有；F 提供失败保存和恢复入口及测试用例，不并行编辑。迁移与 pipeline 装配交 G。

## Task F1：候选持久化与准确失败分类

- [ ] 实现共享契约中的 `FailureDetail`、`GenerationFailure` 和 `ResourceCheckpointPort`。写正文后先保存私有候选再审阅，不能以已有 draft/ready 状态冒充已审阅。
- [x] 私有候选绑定 owner、preparation、artifact、spec_digest、content_digest、审阅状态与失败原因；授权端口由服务器构造，模型拿不到存储写权限。
- [ ] 建立以下恢复矩阵并测试实际分支：

| 类别 | 行为 | 不得发生 |
| --- | --- | --- |
| provider 临时故障 | 剩余配额内重试本次调用，已有候选继续保留 | 抹掉正文、无界重复请求 |
| review_format | 保留正文，补完整审阅 | 因缺选项检查项而重新写整份习题 |
| content | 定向修改受影响资源，重新审阅 | 复用旧通过摘要、重做整课 |
| render | 修复对应场景/媒体并重新校验 | 将损坏必需媒体默认为可选 |
| contract | 明确指出不合法字段/悬空引用，有限纠正 | 删除硬约束或返回假映射 |
| permission/budget/canceled | 终止，结算已发生成本 | 自动重试绕过失败 |

- [x] 恢复入口先核验父 attempt/lease、取消、记忆和目标版本；失效候选保留审计但不可用于新的交付。
- [ ] `review_format` 跨进程恢复必须保持资源身份、正文 digest 与资源版本，另记有限审阅 attempt。协调 B 为新审阅任务生成幂等 job 引用并更新 generation_receipts，避免读到旧失败 job 就再次判失败。
- [ ] 测试两个 worker 同时恢复、任务队列回执丢失、进程写候选后退出、取消竞争；断言至多一次有效交付，费用可结清。

## Task F2：验收实际要求和内容对应关系

- [ ] course_review 使用 B 的原生 Harness 和本模块 Skill；保留逐节点完整正文＋最终整课衔接结构，避免把整课所有正文重复塞入同一上下文。
- [ ] 节点审阅带 A 的 teaching_context 和原始本次要求，校核 D/E 的 applied_requirements 与实际位置；“先例后理”不能只看路径说明，要核对首个解释/例子出现顺序。
- [x] 确定性验证所有 objective_bindings 中节点、目标、section/question/scene/action 引用真实存在；语义充分性由独立审阅补充。未知 ID、空定位、旧摘要一律不通过。
- [ ] manifest 的 checks 对接真实题目或场景检查；报告自测存在时可保留，不再凭固定章节名把全部目标标为已检查。以下断言加入由真实生成 fixture 驱动的集成测试：

```python
def assert_quiz_checks_resolve(node, quiz_questions):
    question_ids = {question['id'] for question in quiz_questions}
    checks = [c for c in node['checks'] if c['mode'] == 'practice']
    assert checks
    assert all(c['locator']['question_id'] in question_ids for c in checks)
```

- [x] 当前 manifest 的 CheckLocator 只有 section_id/question_id/page。若将课堂检查作为正式 manifest check，必须增加兼容字段并交 G 接好学习端读取；尚未支持时，场景对应关系保存在审阅元数据，正式 checks 使用真实习题，不能把 scene_id 塞进 question_id 或伪造页码。
- [ ] 汇总时间时区分 node_budget_minutes、各资源 estimated/measured、交互学习时间和未知项。超出用户硬约束时用现有 repair 缩减内容/冗余检查，不伪造更小数字；未知用时披露未验证。用户明确硬时限但没有可信估算或实测依据时，不得把该项判为已满足，应修复或明确失败。
- [ ] 保留资源自身限制（如未配音、无图片）和来源/路径限制到课程验收；必须媒体缺失不能用 limitations 声明代替补齐。
- [ ] 固化审查的顺序错误与干扰项解析错误，质量门禁应拒绝未修复版本。不要通过放宽门禁来减少模型调用。

## Task F3：最终提交、旧版本与学习端衔接

- [ ] 提交前验证全部必需资源的内容/上下文/规格摘要、实际版本、检查位置、来源权限和父任务状态；仍用现有单事务保存 manifest、指针、材料和成功事件。
- [x] v1 任务保留原摘要身份；v2 新门禁不允许旧审阅自动冒充。升级/重新生成必须有明确新修订记录，旧版本继续可读。
- [ ] `supplement_node` 不改变其他节点；`revise_resource` 保留未要求修改部分、生成正确新版本；`adjust_course` 的保留资源仍可回读，公共课程个人修改不覆盖公共原件。
- [ ] 测试资源内容被篡改、记忆删除、基准版本变化、提交事务回滚、取消与 commit 竞争、worker 失租；失败/取消不能留下 course_ready=true。
- [ ] 执行本模块测试、既有 prepared_learning/merge_learning_integration、PostgreSQL 并发分支，并交 G 做真实浏览器回读。学习进度不能因生成成功被写成已掌握。

## 完成门槛与交付记录

- [ ] 已真实展示“审阅格式失败保留正文恢复”和“正文错误只修问题资源”两种路径，身份/计量/版本正确。
- [ ] 用户要求落实到可定位内容，manifest 的检查引用真实资源，过期通过回执无法提交。
- [ ] 发布给 B 的错误/候选接口、给 D/E 的 checkpoint 适配样例、给 G 的迁移与局部操作验收脚本；明确有限重试上限及停止原因。


## F 模块交付进展（2026-09-19）

共同基线 `18080783`；模块分支 `feat/preparation-quality-20260919`，隔离 worktree 为 `.worktrees/preparation-quality-20260919`。详细接口、参数追踪、测试命令与剩余集成项见 [F 验收与交接记录](../../../acceptance/2026-09-19-preparation-quality-recovery.md)。

- [x] 发布 FailureDetail / GenerationFailure、私有 ResourceCheckpointPort 及 SQL ArtifactResourceCheckpoint；无需迁移。
- [x] 实现最多两次的恢复意图和独立 job 引用；支持候选落盘退出、父回执丢失、子任务先保存、双 worker、取消竞争，恢复不改变正文与资源版本。
- [x] 逐节点审阅加入实际教学上下文/要求落实/用时/资源限制；新门禁校验真实定位与全部摘要，定向内容修复保留正文基线。
- [x] 使用真实审查 fixture 校验 quiz check 回读，并测试顺序错误与干扰项解析错误只触发对应资源修复；语义 critic 为脚本化，不能当作真实模型效果验收。
- [x] commit 复核持久化原文/规格/版本/权限与保留原件；事务回滚、失租、取消、版本冲突、记忆失效和 prepared_learning/merge_learning 回归已执行。
- [x] 向 B/D/E/G 提供接口与装配样例，保留原工作区和公共文件所有权。
- [ ] B 将新的 recovery job 接入耐久队列、回读和 handler，注册 course_review Skill；缺失接口时明确停止，不重写正文。
- [ ] A/B/D/E/G 合并后做真实 Harness 语义失败恢复、费用全链路、课堂媒体播放及浏览器局部操作验收。

上方尚未勾选的跨模块条目不能由本模块数据库/脚本化测试代替。旧已提交版本可读；新任务必须重新接受当前门禁。最终模块提交 SHA 和测试数字写入交接记录，G 按提交 cherry-pick。
