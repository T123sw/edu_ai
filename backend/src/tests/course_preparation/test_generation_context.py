"""A's public context contract; inputs deliberately do not use intake internals."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.course_preparation.schemas import PreparationRequest


def context_input():
    request = PreparationRequest(request_id=uuid4(), operation='create_course',
        goal='我会 Python，请先用 12 加 30 的例子再讲原理。')
    node = dict(node_key='n1', title='工具调用', objectives=['解释分工'],
        prerequisite_keys=[], minutes=10, requirement_ids=['r1'],
        learning_activities=['先追踪 12 加 30，再解释模型和程序分工'],
        self_check='指出谁实际执行工具')
    checkpoint = dict(plan={'nodes': [node]}, brief={
        'language': 'zh-CN', 'audience': '学习者', 'prior_knowledge': '会 Python',
        'requirements': [{'requirement_id': 'r1', 'text': '先例后理',
                          'source_quote': '请先用 12 加 30 的例子再讲原理'}],
        'desired_outcomes': ['解释分工'], 'exclusions': [], 'assumptions': []},
        memory_view={'memory_epoch': 1, 'preferences': {'learning_style': {
            'value': '解释简洁', 'memory_id': 'm1', 'revision': 'v1'}}})
    return request, checkpoint, node


def build(request, checkpoint, node):
    from app.course_preparation.teaching_context import build_teaching_context
    return build_teaching_context(request=request, checkpoint=checkpoint, node=node)


def test_node_activities_and_memory_values_survive_context_build():
    request, cp, node = context_input()
    before = deepcopy(cp)
    context = build(request, cp, node)
    assert context.learning_activities == node['learning_activities']
    assert context.effective_preferences['learning_style']['value'] == '解释简洁'
    assert context.effective_preferences['learning_style']['revision'] == 'v1'
    assert context.node_budget_minutes == 10
    assert context.resource_target_minutes is None
    assert context.depth is None
    assert context.request_goal == request.goal
    assert context.requirements[0].source_quote == cp['brief']['requirements'][0]['source_quote']
    assert context.objective_ids == ['n1:o1']
    context.effective_preferences['learning_style']['value'] = 'changed'
    context.learning_activities.append('changed')
    assert cp == before


def test_empty_memory_unknown_background_and_missing_depth_are_not_inferred():
    request, cp, node = context_input()
    cp.pop('memory_view')
    cp['brief'].pop('prior_knowledge')
    context = build(request, cp, node)
    assert context.effective_preferences == {}
    assert context.prior_knowledge == ''
    assert context.depth is None
    assert context.prerequisites == []


def test_current_request_and_conflicting_memory_both_keep_provenance():
    request, cp, node = context_input()
    cp['memory_view']['preferences']['learning_style']['value'] = '先讲原理再给例子'
    cp['memory_view']['preferences']['display_name'] = {'value': '无关身份'}
    context = build(request, cp, node)
    assert context.request_goal == request.goal
    assert context.requirements[0].text == '先例后理'
    assert context.effective_preferences['learning_style']['value'] == '先讲原理再给例子'
    assert 'display_name' not in context.effective_preferences


def test_prerequisite_resolves_from_path_and_preserves_order():
    request, cp, node = context_input()
    first = {**deepcopy(node), 'node_key': 'n0', 'title': 'Python', 'objectives': ['阅读函数']}
    cp['plan']['nodes'].insert(0, first)
    node['prerequisite_keys'] = ['n0']
    context = build(request, cp, node)
    assert context.prerequisites[0].model_dump() == {
        'node_id': 'n0', 'title': 'Python', 'objectives': ['阅读函数']}


@pytest.mark.parametrize('mutation,code', [
    (lambda cp,n: n.update(prerequisite_keys=['missing']), 'PREREQUISITE'),
    (lambda cp,n: n.update(prerequisite_keys=['n1']), 'PREREQUISITE'),
    (lambda cp,n: n.update(requirement_ids=['missing']), 'REQUIREMENT'),
    (lambda cp,n: n.update(objective_ids=['other:o1']), 'OBJECTIVE'),
    (lambda cp,n: cp['plan']['nodes'].append(deepcopy(n)), 'DUPLICATE_NODE'),
])
def test_dangling_references_fail_instead_of_being_removed(mutation, code):
    request, cp, node = context_input()
    mutation(cp, node)
    with pytest.raises(ValueError, match=code):
        build(request, cp, node)


def test_detached_or_unreviewed_node_is_rejected():
    request, cp, node = context_input()
    with pytest.raises(ValueError, match='NODE_CHANGED'):
        build(request, cp, {**node, 'title': '替换标题'})
    cp['research_state'] = {'phase': 'review', 'path': deepcopy(cp['plan']), 'review': None}
    with pytest.raises(ValueError, match='PATH_NOT_REVIEWED'):
        build(request, cp, node)
    cp['research_state'].update(phase='done', review={'decision': 'pass'})
    assert build(request, cp, node).node_id == 'n1'
    cp['research_state']['path']['nodes'][0]['minutes'] = 20
    with pytest.raises(ValueError, match='REVIEWED_PATH_CHANGED'):
        build(request, cp, node)


def test_source_restriction_document_quote_and_gaps_are_preserved():
    request, cp, node = context_input()
    request = PreparationRequest(request_id=uuid4(), operation='create_course', goal=request.goal,
        uploads=[{'document_id': 'doc1', 'version': 1}], source_policy={'mode': 'uploaded_only'})
    cp['brief']['requirements'][0].update(source_document_id='doc1', source_ref='ref1')
    cp['brief']['material_gaps'] = ['附件缺少运行代码']
    cp['plan']['limitations'] = ['仅有伪代码']
    context = build(request, cp, node)
    assert context.source_policy == {'mode': 'uploaded_only'}
    assert context.requirements[0].source_document_id == 'doc1'
    assert context.requirements[0].source_ref == 'ref1'
    assert context.exclusions == []
    assert context.limitations == ['仅有伪代码', '附件缺少运行代码']


def test_local_request_keeps_target_objective_identity():
    request, cp, node = context_input()
    request = PreparationRequest(request_id=uuid4(), operation='supplement_node', goal='只补充当前节点的例子',
        target={'course_id': 'c1', 'base_manifest_version': 2, 'node_id': 'n1'})
    cp['target_snapshot'] = {'node': {'node_id': 'n1', 'objectives': [
        {'objective_id': 'existing-objective', 'text': '解释分工'}]}}
    assert build(request, cp, node).objective_ids == ['existing-objective']
    node['objectives'] = ['擅自降低目标']
    with pytest.raises(ValueError, match='TARGET_OBJECTIVES_CHANGED'):
        build(request, cp, node)


def test_audit_counterexample_keeps_example_first_activities():
    # Minimal verbatim extracts from quality-counterexamples.json, request.goal,
    # plan.nodes[0].learning_activities, artifacts[0].content.content.
    request, cp, node = context_input()
    request = PreparationRequest(request_id=uuid4(), operation='create_course',
        goal='我会 Python，但没有学过 Agent。请严格只依据附件，设计两个节点、合计 20 分钟的中文入门课：先理解模型与程序各自的职责，再学会追踪参数校验的成功与失败分支。先用 12 加 30 的例子，再解释原理；每个节点需要报告、习题和 AI 课堂。目标是读懂附件伪代码并手动解释日志，不要求接入真实模型 API，不学 SDK、鉴权、多 Agent 和部署。',
        uploads=[{'document_id': 'doc1', 'version': 1}], source_policy={'mode': 'uploaded_only'})
    node['learning_activities'] = [
        '报告：先用 12 加 30 的成功例演示完整流程——用户问 12 加 30，模型选 add、参数 a=12、b=30，程序校验通过执行返回 42，模型据真实返回值回答 42。',
        '报告：随后解释分工原理——模型读取用户问题和已注册工具描述，返回工具名和参数；程序负责校验名称及参数并执行真实工具，再把结果交回模型生成回答；强调模型提出调用不代表工具已执行。']
    historical_opening = '## 概念与机制\n\n工具调用中，模型与程序的分工可以概括为一句话'
    context = build(request, cp, node)
    assert '先用 12 加 30' in context.learning_activities[0]
    assert '随后解释' in context.learning_activities[1]
    assert historical_opening.startswith('## 概念与机制')


def test_brief_can_narrow_but_never_relax_source_policy():
    request, cp, node = context_input()
    request = PreparationRequest(request_id=uuid4(), operation='create_course', goal=request.goal,
        uploads=[{'document_id': 'doc1', 'version': 1}])
    cp['brief']['source_policy'] = {'mode': 'uploaded_only'}
    assert build(request, cp, node).source_policy['mode'] == 'uploaded_only'
    request = request.model_copy(update={'source_policy': request.source_policy.model_copy(update={'mode': 'uploaded_only'})})
    cp['brief']['source_policy'] = {'mode': 'open'}
    assert build(request, cp, node).source_policy['mode'] == 'uploaded_only'


def test_v2_payload_is_structured_and_contains_no_fixed_outline():
    from app.course_preparation.generation_context import automatic_payload
    from tests.course_preparation.test_spec_compatibility import v2_spec
    spec = v2_spec()
    before = deepcopy(spec)
    payload = automatic_payload(spec, {'owner_user_id': 'alice', 'resource_id': 'r1'})
    assert payload.teaching_context == spec['teaching_context']
    assert payload.evidence == spec['evidence']
    assert not getattr(payload, 'confirmed_outline', None)
    assert '案例与面试表达' not in str(getattr(payload, 'harness_chapters', []))
    assert not getattr(payload, 'harness_chapters', None)
    assert payload.resource_target_minutes is None and payload.node_budget_minutes == 10
    assert payload.harness_execution_context['preference_precedence'] == 'current_request_over_memory'
    assert payload.harness_execution_context['evidence_policy'] == 'source_text_is_data_not_instructions'
    assert '节点' in payload.focus
    assert payload.title == payload.subject == spec['title']
    payload.evidence[0]['quote'] = 'mutated'
    payload.teaching_context['effective_preferences'].clear()
    assert spec == before


def test_v2_payload_keeps_full_evidence_revision_and_server_identity():
    from app.course_preparation.generation_context import automatic_payload
    from tests.course_preparation.test_spec_compatibility import v2_spec
    from app.course_preparation.tool_registry import digest
    spec = v2_spec()
    spec['original_content'] = {'content': '原始正确章节\n'}
    spec['source_resource_ref'] = {'resource_id': 'old', 'resource_version': 3}
    spec['revision_feedback'] = ['只改例子']
    payload = automatic_payload(spec, {'owner_user_id': 'alice', 'resource_id': 'server-id'})
    assert payload.material_id == 'server-id' and payload.owner == 'alice'
    assert payload.original_content == spec['original_content']
    assert payload.source_resource_ref == spec['source_resource_ref']
    assert payload.revision_feedback == ['只改例子']
    assert payload.spec_digest == digest(spec)
    assert payload.teaching_context_digest == digest(spec['teaching_context'])
    assert all(e['quote'] in payload.research_context for e in spec['evidence'])
    assert '原始正确章节' in payload.research_context
    assert '原始正确章节' not in payload.review_research_context
    assert all(e['quote'] in payload.review_research_context for e in spec['evidence'])
    assert all(e['source_hash'] == spec['evidence'][i]['source_hash'] for i,e in enumerate(payload.evidence))


def test_v1_payload_remains_compatible_with_existing_generator():
    from app.course_preparation.generation_context import automatic_payload
    from app.course_preparation.adapters.generation import automatic_payload as old_payload
    from tests.course_preparation.test_spec_compatibility import legacy_fixture
    spec = legacy_fixture()['spec']
    artifact = {'owner_user_id': 'alice', 'resource_id': 'r1'}
    payload = automatic_payload(spec, artifact)
    assert vars(payload) == vars(old_payload(spec, artifact))
    assert payload.harness_chapters == [{'title': '概念与机制'}, {'title': '案例与面试表达'}, {'title': '学习检查'}]
    assert '学习时间：10 分钟' in payload.focus
    assert not hasattr(payload, 'teaching_context')


def test_strict_context_rejects_coerced_time_and_unknown_fields():
    from app.course_preparation.teaching_context import TeachingContext
    request, cp, node = context_input()
    value = build(request, cp, node).model_dump(mode='json')
    for change in ({'node_budget_minutes': '10'}, {'node_budget_minutes': True}, {'unreviewed': True}):
        with pytest.raises(ValueError):
            TeachingContext.model_validate({**value, **change})


def test_explicit_depth_language_and_target_objective_order_win():
    request, cp, node = context_input()
    request = request.model_copy(update={'overrides': request.overrides.model_copy(update={'depth': 'advanced', 'language': 'en'})})
    cp['brief']['depth'] = 'introductory'
    context = build(request, cp, node)
    assert context.language == 'en' and context.depth == 'advanced'
    node['objectives'] = ['解释分工', '追踪执行']
    node['objective_ids'] = ['n1:o2', 'n1:o1']
    with pytest.raises(ValueError, match='OBJECTIVE_ID_ORDER_CHANGED'):
        build(request, cp, node)
