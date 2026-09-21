# A：教学参数、版本规格与 payload 交付记录

2026-09-19。A 自有实现可供集成：上下文进入新建资源规格，v2 payload builder 可独立调用，旧规格恢复保持身份。**未通过全链路完成门槛**：B 的 handler 接线回执、D/E 的实际正文/课堂定位和 G 的端到端验收仍待集成。不把字段进入上下文视为产物已经遵守要求。

## 版本与范围

- 启动 HEAD / 临时代码基线：`67fc18b85ffbd82406c5ab33703eff8ea627c222`。
- 启动时主工作区包含上一轮未提交改动、其他模块修改和备份，G0 共同基线尚未发布。本窗口没有提交或复制这些生产代码，也没有替 G 宣布基线验证完成。
- 独立分支：`feat/preparation-parameters-20260919`。
- worktree：`/home/zxqs_ep/Edu_AI/.worktrees/preparation-parameters-20260919`。
- A0：`e3d3ce6b`，公开上下文、测试、完整 JSON 样例和历史规格 fixture。
- A2/A3：`d7d26fc8469ad1c915d12a3184153b8bf0eb2ee5`，版本化规格、produce 接入、payload 及兼容测试。
- 文档提交包含本记录和 A 模块复选框；精确文档 SHA 可用 `git log -1 -- docs/acceptance/2026-09-19-preparation-parameters.md` 获取。

生产文件仅 `teaching_context.py`、`generation_context.py`、`generation_contracts.py`、`production_stages.py`；测试仅 `test_generation_context.py`、`test_spec_compatibility.py` 及 `fixtures/parameters_*.json`。未改 adapters/generation.py、intake、research_contracts 或其他窗口文件。

## 参数来源与验证边界

| 输入来源 | 校验/变换 | 消费接口 | 当前证据与产物状态 |
| --- | --- | --- | --- |
| request.goal / requested_changes / learning_context | 原值保留，不按关键词改写要求 | teaching_context 对应字段 → B/D/E/F | 单元测试保留本次原话；真实产物定位待 D/E |
| brief.requirements | 保留 requirement_id、text、source_quote、source_document_id、source_ref；节点 ID 必须可解引用 | teaching_context.requirements / requirement_ids | 缺失引用明确失败；不以引用存在代替出处语义审阅 |
| brief.prior_knowledge / desired_outcomes / exclusions | 缺失基础为 `''`，缺失 depth 为 null；明确 override 优先 | D/E/F 规范上下文 | 空基础、无 depth 与 override 测试通过 |
| request.source_policy + 已验证 brief.source_policy | 与现有 intake 一致：只允许收紧为 uploaded_only，不放宽请求限制 | teaching_context.source_policy；服务端仍执行权限控制 | 仅附件与不得放宽测试通过 |
| memory_view.preferences | 白名单 language / response_detail / learning_style / resource_preference，保留完整条目的值、memory_id、revision、course_id 等来源信息 | effective_preferences；payload.execution 指定本次要求优先 | 空记忆、冲突保留、删除/修改导致 spec digest 改变；实际表达影响待 D/E |
| 已审阅 plan.nodes | 必须与对应节点完全相同；research_state 存在时要求 done、review=pass、path 与 plan 完全相同 | objectives / objective_ids / prerequisites / learning_activities / self_check | 拒绝路径变更、错误先修、乱序 ID；无持久化状态的纯函数调用由调用方提供已审阅 plan |
| target_snapshot.node.objectives | 局部请求保持原目标文本及原 objective_id 顺序；不得扩大到其他节点 | produce 及教学上下文 | 修订目标、原正文、准确资源版本测试通过 |
| node.minutes | 仅整节点约束；builder 不分配单资源时间 | node_budget_minutes；旧 minutes 同值；resource_target_minutes=null | 报告/习题/课堂共享节点时间语义，未声称实际用时 |
| plan.limitations / research_summary gaps / brief.material_gaps | 保留为 limitations，独立于 exclusions | D/E/F 上下文 | 缺材料不自动变为排除项测试通过 |
| node_evidence | 全字段深拷贝，包括 finding_id、source_id、quote、source_hash、url；原引用进入 research_context | payload.evidence / research_context | 完整证据与无原地修改测试通过；正文引用准确性待 D/F |
| original_content / source_resource_ref | 保留原正文、修订基线及版本，不充当新知识证据 | payload 的同名字段与 revision_feedback | SQL 恢复不改历史正文；局部修订快照测试通过 |

完整 TeachingContext JSON 位于 `backend/src/tests/course_preparation/fixtures/parameters_context_v1.json`；可用 `tests.course_preparation.test_spec_compatibility.v2_spec()` 获取可执行的完整 v2 规格样例。TeachingContext 版本为 1，ResourceSpec 版本为 2，二者分别标识不同契约。

审查反例引用原始 `quality-counterexamples.json` 的 request.goal、plan.nodes[0].learning_activities 和 artifacts[0].content.content 开头：原要求及活动为先 12+30 例子再解释，历史正文却以“概念与机制”开篇，并出现“案例与面试表达”。测试只固化必要文字，没有复制运行凭据。历史 spec fixture 为原值，包含复现原摘要所需的测试身份和证据 ID。

## 兼容与恢复策略

1. 未带 schema_version 的已持久化规格按 v1 解析；新字段的默认值不进入 v1 序列化，因此不改变历史 spec_digest。显式版本及字段是否存在也予以保留。
2. `produce` 遇到已有 `resource_specs` 时直接使用原规格，不从新 request/brief 补字段，不升级旧 checkpoint，不改原摘要、action key 和 receipts 的键。尚未生成任何规格的任务首次建规格时使用 v2。
3. 历史 fixture 的 spec_digest 固定为 `4864a130d6b83eb359e5f9499591d52e3b83bc5e71fe1b6dd0eb4dc43c77cd5a`；action key 为 `generation:` 加该摘要。模型读取/序列化、produce 重放以及真实 SQLite ArtifactStore 创建/读回/reconcile 均保持相同值和原正文。
4. v2 必须包含 TeachingContext，且 node_id、objectives、objective_ids、language、learning_check、minutes 必须与上下文对应值完全一致。上下文或记忆值/revision/epoch 改变会改变规格摘要，不能命中旧的精确规格复用。
5. v1 payload 刻意保留旧章节及时间措辞，以兼容旧生成入口；v2 不发送 confirmed_outline 或 harness_chapters。历史任务需要升级时，由 F/G 通过显式新修订实施；不得直接覆盖旧 spec 或将旧通过审阅复用到 v2。
6. 无数据库迁移；旧权限、记忆依赖验证、租约、预算、取消和来源限制仍由现有服务端负责。builder 不是授权入口，也不将 config_snapshot 的运行配置或凭据放入教学上下文。

## 接口与明确交接

**B：**保留 `adapters/generation.py` 的公开 `automatic_payload(spec, artifact)` 入口，在其内部调用：

```python
from ..generation_context import automatic_payload as build_automatic_payload

def automatic_payload(spec, artifact):
    return build_automatic_payload(spec, artifact)
```

新 builder 自身已经处理 v1/v2，不回调旧 wrapper，避免递归。v2 的 `payload.teaching_context` 是 dict，`payload.evidence` 是完整节点证据列表，包含 `spec_digest` / `teaching_context_digest`、原文研究上下文和服务器提供的 owner/material_id。执行策略含 `preference_precedence='current_request_over_memory'`。B 仍负责实际 phase 绑定、runtime/Skill 使用回执、权限及服务端检查点端口。

**D/E：**必须在 B 启用 v2 主入口时同步接受结构化上下文并根据活动组织正文。v2 没有固定大纲，旧 generate_reviewed_report 若仍要求 harness_chapters 会拒绝，不能单独启用 A 的 produce 变更就宣布可运行。验证两种相反教学顺序时，回传实际 section_id / question_id / scene_id；同时核对需求、先修、活动、自测及估算/实测时间。A 未执行真实模型生成。

**C：**builder 消费现有 brief 的 prior_knowledge、desired_outcomes、depth、source_policy、requirements（含 source_ref）、material_gaps，不要求修改 brief schema。继续保证来源引文已经校验及 memory_view 为授权有效值；请勿用 audience 推断掌握事实。保留结构化用户背景缺失的空值。

**F：**继续以原始持久化 spec 为恢复身份。需要升级 v1 时创建有记录的新修订；新审阅绑定新 spec/context/content digest。参数变化、偏好删除后的内存重建与失效仍使用已有生命周期；实际候选审阅恢复由 F/B 提供。不得把节点预算复制成每份资源的独立用时。

**G：**两个代码提交应连同 B、D/E 消费者按依赖集成；先确认 G0 基线，再在同一最终 SHA 验证。无需采纳主目录的未提交备份/构建产物。公开 JSON 样例及测试均在 A 分支，其他窗口无需自行造另一套字段。当前没有 B 接线回执或 D/E 产物位置，模块全链路完成门槛保持未勾选。

TeachingContext 在共享契约“至少字段”之外增加 `requirement_ids`、`requested_changes`、`learning_context`，RequirementContext 增加已有上游 `source_ref`，均为保留来源的可选字段；没有删除既有约定入口。消费者为 B/D/E/F/G。

## 执行过的验证

- 基线：test_contracts、test_resource_reuse、test_route_adjustment，29 passed / 3 skipped。
- A1 先写测试：13 failed，均因 teaching_context 模块不存在；实现并增加限制来源测试后 14 passed。
- A2 先写测试：9 failed / 1 passed，缺少新规格字段及 produce 上下文；实现后连同指定回归 53 passed / 3 skipped。
- A3 先写测试：3 failed / 14 passed，均因 generation_context 模块不存在。
- 最终相关回归：**70 passed / 17 skipped，21.40 秒**。17 项跳过中，16 项因未配置 PREPARATION_TEST_DATABASE_URL，1 项明确仅 PostgreSQL 并发；SQLite 持久化与单元测试实际运行。无真实模型、联网、浏览器或 PostgreSQL 验证。
- `git diff --check` 通过。

在 A worktree 根目录运行：

```bash
COURSE_PREPARATION_ENABLED=false PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PY'
import dotenv, pytest
dotenv.load_dotenv = lambda *args, **kwargs: False
raise SystemExit(pytest.main([
    'backend/src/tests/course_preparation/test_generation_context.py',
    'backend/src/tests/course_preparation/test_spec_compatibility.py',
    'backend/src/tests/course_preparation/test_contracts.py',
    'backend/src/tests/course_preparation/test_resource_reuse.py',
    'backend/src/tests/course_preparation/test_route_adjustment.py',
    'backend/src/tests/course_preparation/test_generation_adapter.py',
    'backend/src/tests/course_preparation/test_local_manifest.py',
    '-q', '-ra',
]))
PY
```
