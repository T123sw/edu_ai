# 窗口 A：阶段参数与教学上下文贯通 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 每个复选框只在代码与验证完成后勾选。

**Goal:** 将用户真实要求、基础、偏好、节点活动与时间语义完整传到生成器，并保留旧任务可恢复性。

**Architecture:** 新增小型纯函数上下文构建模块和 v2 资源规格，接到既有 produce 阶段。保留当前资源类型选择规则，不新增规划阶段。

**Tech Stack:** Python、Pydantic、现有 SQL 检查点及 pytest。

**Spec:** [总计划](../2026-09-19-preparation-chain-optimization.md)、[共享契约](00-shared-contracts.md)、[审查证据](../../../acceptance/2026-09-19-preparation-agent-code-audit.md)。

## Global Constraints

- 本次明确要求优先于记忆；保留偏好值和 revision，不把记忆当事实来源。
- 旧持久化规格、摘要、action key 和原始内容不可因新增默认字段被静默改变。
- 不修改资源类型组合、必学规则或前端风格输入；节点时间不是每份资源的分配时间。

## 文件范围与交接

- 新建：`backend/src/app/course_preparation/teaching_context.py`、`generation_context.py`。
- 修改：`generation_contracts.py`、`production_stages.py`。
- 新建测试：`backend/src/tests/course_preparation/test_generation_context.py`、`test_spec_compatibility.py`。
- 不编辑 `adapters/generation.py`：把兼容 wrapper 和新 builder 调用要求交给 B。不编辑 `research_contracts.py` 或 intake：brief schema 需求交给 C。
- 输出接口：共享契约的 `TeachingContext`、`build_teaching_context()`、`automatic_payload()`；A0 提交须包含完整字段样例和旧规格 fixture。

## Task A1：锁定参数缺失反例，交付可独立使用的上下文构建器

- [ ] 从审查的 `quality-counterexamples.json` 固化用户要求、路径活动、生成报告首章不一致的样例；不复制运行凭据或无关数据。
- [ ] 新增以下契约测试，先执行确认当前没有新模块或无法保留字段，再实现纯构建函数。测试输入直接写在测试文件中：

```python
def test_node_activities_and_memory_values_survive_context_build():
    from uuid import uuid4
    from app.course_preparation.schemas import PreparationRequest
    from app.course_preparation.teaching_context import build_teaching_context
    request = PreparationRequest(request_id=uuid4(), operation='create_course',
        goal='我会 Python，请先用 12 加 30 的例子再讲原理。')
    node = dict(node_key='n1', title='工具调用', objectives=['解释分工'],
        prerequisite_keys=[], minutes=10, requirement_ids=['r1'],
        learning_activities=['先追踪 12 加 30，再解释模型和程序分工'],
        self_check='指出谁实际执行工具')
    checkpoint = dict(plan={'nodes': [node]}, brief={
        'language': 'zh-CN', 'prior_knowledge': '会 Python',
        'requirements': [{'requirement_id': 'r1', 'text': '先例后理',
                          'source_quote': '请先用 12 加 30 的例子再讲原理'}],
        'desired_outcomes': ['解释分工'], 'exclusions': [], 'assumptions': []},
        memory_view={'memory_epoch': 1, 'preferences': {'learning_style': {
            'value': '解释简洁', 'memory_id': 'm1', 'revision': 'v1'}}})
    context = build_teaching_context(request=request, checkpoint=checkpoint, node=node)
    assert context.learning_activities == node['learning_activities']
    assert context.effective_preferences['learning_style']['value'] == '解释简洁'
    assert context.node_budget_minutes == 10
    assert context.resource_target_minutes is None
```

- [ ] 严格校验节点来自已审阅路径、先修真实存在、目标与 ID 顺序一致；不存在引用时抛出明确契约错误，不能删引用后继续。
- [ ] 保留当前 request 原始目标和 requirement 出处，不用固定关键词分类代替原要求。白名单传递有关偏好，缺失基础标为空/未知。
- [ ] 增加空记忆、冲突要求、无先修、存在先修、无 depth、限制来源和局部目标样例；原输入不被函数原地修改。
- [ ] 执行 `test_generation_context.py`，提交 A0 接口、样例和测试给 B/D/E/F/G。

## Task A2：版本化规格与恢复兼容

- [ ] 在 `test_spec_compatibility.py` 固化一个真实 v1 spec、存储的 spec_digest、对应 action key；断言旧记录只读/恢复后这些值完全相同。
- [ ] v2 规格必须含结构化 teaching_context；保留旧字段的兼容含义，禁止把省略字段解释为用户明确要求。
- [ ] 在 `production_stages.py` 仍按现有 kinds 创建资源，将已审阅上下文放入每份规格；同一节点各资源共享节点语义，不赋予各自整节点时间。
- [ ] 接口示例，A 实现此调用，具体资源身份/权限字段继续使用现有服务器构建值：

```python
teaching = build_teaching_context(request=request, checkpoint=checkpoint, node=node)
# v2 创建时传入；不能原地修改已有 resource_specs 或它们的 digest。
spec_fields.update(schema_version=2, teaching_context=teaching.model_dump(mode='json'))
```

- [ ] 区分新任务与旧规格恢复：旧任务继续走已标明的 v1 语义；需要升级时由 F 创建有记录的新修订，不补空字段假装已满足 v2。
- [ ] 测试 v1 完全相同摘要、v2 上下文变化导致新摘要、局部修订保留目标范围、记忆变化不误复用；提交兼容策略给 F/G。

## Task A3：生成 payload 去固定模板，交给 B 接线

- [ ] 新 `generation_context.automatic_payload()` 传结构化 teaching_context、完整节点证据和明确执行策略；兼容旧生成器需要的 title、subject、audience、focus 等字段，但不把 focus 作为唯一上下文。
- [ ] v2 不填“案例与面试表达”等固定章节。D 负责在生成器中根据活动组织正文；不能删除章节后让旧 `generate_reviewed_report` 直接报缺大纲。
- [ ] 测试用代码约束这一交接：

```python
def assert_v2_payload(payload, expected_context):
    assert payload.teaching_context == expected_context
    assert not getattr(payload, 'confirmed_outline', None)
    assert '案例与面试表达' not in str(getattr(payload, 'harness_chapters', []))
```

- [ ] 与 B 集成后检查 handler 的实际输入；与 D/E/G 验证相反教学顺序确实改变产物，不能以字段进入 prompt 宣布参数有效。
- [ ] 运行新测试以及既有 `test_contracts.py`、`test_resource_reuse.py`、`test_route_adjustment.py`；独立提交 A 的文件。

## 完成门槛与交付记录

必须同时有：来源可追踪的上下文、v1 恢复证据、v2 参数消费样例、B 主流程接线回执、D/E 的实际产物定位。不以新建 dataclass 或复制字段作为最终完成。

- [ ] 基线 SHA、模块 SHA、测试命令/结果、参数追踪表、兼容策略、对 B/F 的明确交接已写入模块验收文档。
