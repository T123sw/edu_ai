"""D unit/contract tests. Scripted completions test control flow, not model skill."""
import copy
import json
from types import SimpleNamespace

import pytest
from app.chat.harness import reviewed_report, reviewed_resource
from app.chat.harness.preparation_content import preparation_metadata, report_sections, value_digest
from tests.chat.test_reviewed_report import BODY, payload as legacy_payload, review


@pytest.mark.parametrize('heading', ['## <a id="example"></a>实例', "## 实例 <a id='example'></a>"])
def test_native_report_heading_anchor_resolves_without_rewriting_body(heading):
    body = heading + '\n真实示例。\n```html\n<a id="fake"></a>\n```'
    assert report_sections(body) == {'example': body}
    from app.chat.harness.preparation_content import resolve_locator
    assert resolve_locator('report', body, {'section_id': 'example'}) == body
    with pytest.raises(ValueError, match='duplicate_section'):
        report_sections(body + '\n' + heading + '\n重复位置。')


def context(order='example_first'):
    return dict(schema_version=1, request_goal='学习工具调用，不要面试话术',
        requirements=[{'requirement_id': 'req-order', 'text': '先例后理' if order == 'example_first' else '先理后例',
                       'source_quote': '本次要求', 'source_document_id': None}],
        prior_knowledge='会 Python，没有 Agent 基础', desired_outcomes=['解释工具职责'],
        exclusions=['面试话术'], language='zh-CN', depth='introductory', source_policy={'mode':'uploaded_only'},
        effective_preferences={}, node_id='tools', objective_ids=['tools:o1', 'tools:o2'],
        objectives=['解释工具职责', '检查缺失参数'], prerequisites=[],
        learning_activities=['追踪12+30例子', '解释模型与程序职责'] if order == 'example_first' else ['解释模型与程序职责', '追踪12+30例子'],
        self_check='程序是否执行了工具？', node_budget_minutes=10, resource_target_minutes=None,
        assumptions=[], limitations=[])


def payload(kind='report', order='example_first'):
    return SimpleNamespace(resource_type=kind, subject='工具调用', title='工具调用',
        teaching_context=context(order), spec_digest='a'*64, preparation_policy='automatic_personal_draft_v1',
        harness_chapters=[{'title':'概念与机制'}, {'title':'案例与面试表达'}])


def report_envelope(order='example_first'):
    example = '<a id="example"></a>\n## 追踪 12+30\n\n' + '用户请求12加30，模型提出add(a=12,b=30)，程序校验并执行得到42，模型根据结果回答。'*7
    theory = '<a id="theory"></a>\n## 职责原理\n\n' + '模型产出工具名和参数，程序检查权限、工具名和参数后实际执行。提出请求不代表工具已经运行。'*7
    body = '\n\n'.join([example,theory] if order == 'example_first' else [theory,example])
    return {'content':body, 'applied_requirements':[{'requirement_id':'req-order', 'locator':{'section_id':'example' if order == 'example_first' else 'theory'}, 'explanation':'正文按本次顺序展开'}],
        'objective_bindings':[{'objective_id':'tools:o1','locator':{'section_id':'theory'},'role':'explanation'}]}


def quiz_envelope():
    return {'content':{'title':'工具调用', 'questions':[{'id':'q-tools', 'type':'single_choice',
        'stem':'模型提出调用后谁执行工具？', 'options':['程序执行','模型执行'], 'answer':'A',
        'explanation':'A 正确，程序执行。B 错误，模型只提出调用。'}]},
        'applied_requirements':[{'requirement_id':'req-order','locator':{'question_id':'q-tools'},'explanation':'先追踪调用再解释职责'}],
        'objective_bindings':[{'objective_id':'tools:o1','locator':{'question_id':'q-tools'},'role':'check'}]}


def test_quiz_duration_uses_question_work_and_reading_not_node_budget():
    value=quiz_envelope()
    value['question_time_estimates']=[{'question_id':'q-tools','thinking_seconds':45,
                                      'reason':'追踪模型提出请求与程序执行两个步骤，再选择选项'}]
    teaching=context()
    meta=preparation_metadata('quiz',value['content'],value,teaching,'a'*64)
    assert meta['duration']['basis']=='estimated'
    assert 0.75 < meta['duration']['value_minutes'] < 2
    assert 'not measured or calibrated' in meta['duration']['method']
    teaching['node_budget_minutes']=30
    assert preparation_metadata('quiz',value['content'],value,teaching,'a'*64)['duration']==meta['duration']
    value['question_time_estimates'][0]['thinking_seconds']=0
    with pytest.raises(ValueError,match='quiz_time_estimate_invalid'):
        preparation_metadata('quiz',value['content'],value,teaching,'a'*64)


def test_node_scoped_resource_keeps_global_requirements_without_fake_locations():
    teaching=context();teaching['requirements'].append({'requirement_id':'later','text':'后续节点内容'})
    teaching['requirement_ids']=['req-order']
    value=report_envelope()
    meta=preparation_metadata('report',value['content'],value,teaching,'a'*64)
    assert [r['requirement_id'] for r in meta['applied_requirements']]==['req-order']


@pytest.mark.parametrize('kind',['true_false','short_answer'])
def test_non_choice_empty_options_are_valid_without_changing_content(kind):
    value={'questions':[{'id':'q1','type':kind,'stem':'谁执行工具？','options':[],
                         'answer':'程序','explanation':'程序校验参数并执行工具。'}]}
    before=copy.deepcopy(value)
    reviewed_resource.validate_resource('quiz',value)
    assert value==before
    value['questions'][0]['type']='single_choice'
    with pytest.raises(ValueError):reviewed_resource.validate_resource('quiz',value)


def completion_review(data, kind='report'):
    result = review(True)
    metadata = data.get('preparation') or data.get('specification', {}).get('preparation')
    if metadata:
        result['preparation_checks'] = [dict(binding_type=key,binding_id=item[key],locator=item['locator'],passed=True,reason='实际位置体现了对应教学要求。')
            for key, collection in [('requirement_id','applied_requirements'),('objective_id','objective_bindings')]
            for item in metadata[collection]]
    if kind == 'quiz':
        result['question_checks']=[dict(question_index=0,independent_solution='模型提出调用，程序校验并执行工具，因此答案是A。',answer_matches=True,explanation_valid=True,
            option_checks=[dict(option_index=0,reasoning='程序校验后负责实际执行',explanation_valid=True,independent_correct=True,explanation_reasoning="已独立逐句检查解析中的主张是否对应原选项。",explanation_excerpt='A 正确，程序执行。'),
                dict(option_index=1,reasoning='模型只负责提出调用请求',explanation_valid=True,independent_correct=False,explanation_reasoning="已独立逐句检查解析中的主张是否对应原选项。",explanation_excerpt='B 错误，模型只提出调用。')])]
    return result


def test_quiz_review_reports_all_inexact_excerpts_in_one_recovery():
    result = completion_review({}, 'quiz')
    for option in result['question_checks'][0]['option_checks']:
        option['explanation_excerpt'] = '这不是原文中的逐字引用'
    review = reviewed_resource.BoundQuizReview.model_validate(result)
    with pytest.raises(ValueError) as failure:
        reviewed_resource.bind_option_reviews(quiz_envelope()['content'], review)
    assert 'question_index=0, option_index=0' in str(failure.value)
    assert 'question_index=0, option_index=1' in str(failure.value)


class CountingGateway:
    def __init__(self, kind='report', malformed=0):
        self.kind, self.malformed = kind, malformed
        self.writer_calls = self.review_calls = 0
        self.phases = []
    def for_phase(self, phase, *, context):
        self.phases.append(phase)
        return self
    def chat(self, messages, **kwargs):
        data=json.loads(next(m['content'] for m in reversed(messages) if m['role']=='user' and m['content'].startswith('{')))
        if 'schema' in data:
            self.review_calls += 1
            if self.review_calls <= self.malformed:
                return '{}'
            return json.dumps(completion_review(data, self.kind),ensure_ascii=False)
        self.writer_calls += 1
        ctx=data['specification'].get('teaching_context')
        order='example_first' if ctx['learning_activities'][0].startswith('追踪') else 'theory_first'
        return json.dumps(report_envelope(order) if self.kind=='report' else quiz_envelope(),ensure_ascii=False)


@pytest.fixture
def phases(monkeypatch):
    # Native B runtime is tested separately; this fixture checks explicit routing.
    def bind(gateway, payload, phase):
        return gateway.for_phase(phase,context=payload.teaching_context)
    monkeypatch.setattr(reviewed_report,'phase_gateway',bind)
    monkeypatch.setattr(reviewed_resource,'phase_gateway',bind)


@pytest.mark.parametrize('order,first', [('example_first','example'),('theory_first','theory')])
def test_final_report_order_follows_activities_without_outline_template(phases,order,first):
    gateway=CountingGateway()
    body,state=reviewed_report.generate_reviewed_report(payload(order=order),gateway)
    assert list(report_sections(body))[0] == first
    assert '面试' not in body and '概念与机制' not in body
    assert state['preparation']['objective_bindings'][0]['locator']=={'section_id':'theory'}
    assert state['preparation']['duration']['basis']=='estimated'
    assert state['preparation']['duration']['value_minutes'] != 10
    assert gateway.phases==['resource_write','resource_review']
    assert gateway.writer_calls==1 and gateway.review_calls==1
    assert reviewed_report.verified_review({'content':body,'generation_state':state})
    state['preparation']['applied_requirements'][0]['locator']['section_id']='missing'
    assert not reviewed_report.verified_review({'content':body,'generation_state':state})


def test_quiz_objective_mapping_is_specific_and_options_are_bound(phases):
    gateway=CountingGateway('quiz')
    artifact=reviewed_resource.ReviewedResourceGenerator(gateway).generate(payload('quiz'),job_id='j',config_snapshot_id='c')['artifacts'][0]
    metadata=artifact['generation_state']['preparation']
    assert {x['objective_id'] for x in metadata['objective_bindings']}=={'tools:o1'}
    assert metadata['duration']['basis']=='unknown' and metadata['duration']['value_minutes'] is None
    checks=artifact['generation_state']['resource_review']['question_checks'][0]['option_checks']
    assert checks[0]['option_text']=='程序执行'
    assert checks[1]['explanation_excerpt']=='B 错误，模型只提出调用。'
    assert reviewed_resource.verified_resource(artifact,'quiz')
    checks[0]['option_text']='模型执行'
    assert not reviewed_resource.verified_resource(artifact,'quiz')


@pytest.mark.parametrize('mutation', ['missing','empty','foreign_objective','duplicate_id'])
def test_invalid_locator_or_identity_is_contract_error_before_review(phases,mutation):
    pytest.importorskip('app.course_preparation.generation_failures')
    from app.course_preparation.generation_failures import GenerationFailure
    envelope=report_envelope()
    if mutation=='missing': envelope['objective_bindings'][0]['locator']['section_id']='absent'
    if mutation=='empty': envelope['content']='<a id="theory"></a>\n## Empty\n'
    if mutation=='foreign_objective': envelope['objective_bindings'][0]['objective_id']='other:o1'
    if mutation=='duplicate_id': envelope['content']+='\n<a id="theory"></a>\n## Duplicate\ntext'
    class Gateway(CountingGateway):
        def chat(self,*a,**k):
            self.writer_calls+=1
            return json.dumps(envelope)
    gateway=Gateway()
    with pytest.raises(GenerationFailure) as error:
        reviewed_report.generate_reviewed_report(payload(),gateway)
    assert error.value.detail.category=='contract' and gateway.writer_calls==1


def test_teaching_context_accepts_A_strict_model(phases):
    module=pytest.importorskip('app.course_preparation.teaching_context')
    value=payload()
    value.teaching_context=module.TeachingContext.model_validate(context())
    # Use real phase helper outside this fixture only for B integration.
    monkey=CountingGateway()
    body,state=reviewed_report.generate_reviewed_report(value,monkey)
    assert state['preparation']['teaching_context_digest']==value_digest(value.teaching_context.model_dump(mode='json'))


@pytest.mark.parametrize('kind',['report','quiz'])
def test_removing_preparation_metadata_cannot_downgrade_a_receipt(phases,kind):
    gateway=CountingGateway(kind)
    if kind=='report':
        body,state=reviewed_report.generate_reviewed_report(payload(),gateway)
        artifact={'content':body,'generation_state':state}
        verify=reviewed_report.verified_review
    else:
        artifact=reviewed_resource.ReviewedResourceGenerator(gateway).generate(payload(kind),job_id='j',config_snapshot_id='c')['artifacts'][0]
        verify=lambda value:reviewed_resource.verified_resource(value,kind)
    assert verify(artifact)
    del artifact['generation_state']['preparation']
    assert not verify(artifact)


def test_mapping_only_quiz_repair_preserves_native_body(phases):
    class Gateway(CountingGateway):
        def chat(self,messages,**kwargs):
            data=json.loads(messages[-1]['content'])
            if 'schema' in data:
                self.review_calls+=1
                result=completion_review(data,'quiz')
                if self.review_calls==1:
                    # One objective is mapped to a real question but does not
                    # match what it checks. This is not a native-content error.
                    result['preparation_checks'][-1].update(passed=False,reason='该题检查职责，应绑定tools:o1，而不是缺失参数目标tools:o2。')
                return json.dumps(result)
            self.writer_calls+=1
            if data['previous_draft'] is not None:
                assert data['previous_preparation']['objective_bindings'][0]['objective_id']=='tools:o2'
                return json.dumps({'edits':[], 'objective_bindings':quiz_envelope()['objective_bindings']})
            envelope=quiz_envelope()
            envelope['objective_bindings'][0]['objective_id']='tools:o2'
            return json.dumps(envelope)
    gateway=Gateway('quiz')
    artifact=reviewed_resource.ReviewedResourceGenerator(gateway).generate(payload('quiz'),job_id='j',config_snapshot_id='c')['artifacts'][0]
    assert artifact['content']==quiz_envelope()['content']
    assert artifact['generation_state']['preparation']['objective_bindings']==quiz_envelope()['objective_bindings']
    assert gateway.phases==['resource_write','resource_review','resource_repair','resource_review']
    history=artifact['generation_state']['resource_review']['history']
    assert history[0]['content_sha256']==history[1]['content_sha256']
    assert reviewed_resource.verified_resource(artifact,'quiz')


@pytest.mark.skipif(__import__('os').getenv('D_CONTENT_REAL_MODEL')!='1',reason='opt-in real model quality experiment; not native B integration')
@pytest.mark.parametrize('order',['example_first','theory_first'])
def test_real_report_order_and_localized_requirements(monkeypatch,order):
    import os
    import dotenv
    from pathlib import Path
    from app.chat.harness.content_gateway import ContentGateway
    settings=dotenv.dotenv_values(os.environ['D_CONTENT_ENV_FILE'])
    gateway=ContentGateway(api_base=settings['DEEPSEEK_BASE_URL'],api_key=settings['DEEPSEEK_API_KEY'],
        model_name=settings.get('LLM_MODEL') or 'deepseek-v4-pro')
    # This experiment isolates real-model writing/review quality. B's native
    # Harness adapter is a separate integration gate and is never simulated
    # into a claim of native execution.
    monkeypatch.setattr(reviewed_report,'phase_gateway',lambda g,p,phase:g)
    value=payload(order=order)
    value.research_context=('已提供材料：模型输出工具名与参数，程序校验名称和参数后执行工具。'
        'add(a,b)计算两个数的和；add(a=12,b=30)得42；缺少b时校验失败，工具不执行。')
    body,state=reviewed_report.generate_reviewed_report(value,gateway)
    sections=list(report_sections(body).values())
    first=sections[0]
    if order=='example_first':
        assert '12' in first and '30' in first and '42' in first
        assert any('职责' in section or '原理' in section or '机制' in section for section in sections[1:])
    else:
        assert '职责' in first or '原理' in first or '机制' in first
        assert any('12' in section and '42' in section for section in sections[1:])
    assert '面试表达' not in body
    assert reviewed_report.verified_review({'content':body,'generation_state':state})
    root=os.getenv('D_CONTENT_EVIDENCE_DIR')
    if root:
        Path(root,f'real-report-{order}.json').write_text(json.dumps({'scope':'real model quality experiment; direct gateway, not native Harness',
            'teaching_context':value.teaching_context, 'content':body,'generation_state':state},ensure_ascii=False,indent=2))


def test_prepared_quiz_requires_complete_persisted_option_evidence(phases):
    artifact=reviewed_resource.ReviewedResourceGenerator(CountingGateway('quiz')).generate(payload('quiz'),job_id='j',config_snapshot_id='c')['artifacts'][0]
    for check in artifact['generation_state']['resource_review']['question_checks']:
        for option in check['option_checks']:
            for key in ['option_text','explanation_excerpt','independent_correct']:
                option.pop(key)
    assert not reviewed_resource.verified_resource(artifact,'quiz')


def test_report_repair_cannot_replace_stable_section_ids(phases):
    failures=pytest.importorskip('app.course_preparation.generation_failures')
    class Gateway(CountingGateway):
        def chat(self,messages,**kwargs):
            data=json.loads(messages[-1]['content'])
            if 'schema' in data:
                result=completion_review(data)
                result['blocking_issues']=['修正例子中的一句解释']
                return json.dumps(result)
            if data['previous_draft']:
                envelope=report_envelope()
                envelope.pop('content')
                envelope['edits']=[{'path':[],'before':'id="example"','after':'id="replacement"'}]
                return json.dumps(envelope)
            return json.dumps(report_envelope())
    with pytest.raises(failures.GenerationFailure,match='report_repair_changed_section_identity'):
        reviewed_report.generate_reviewed_report(payload(),Gateway())


@pytest.mark.skipif(__import__('os').getenv('D_CONTENT_NATIVE_MODEL')!='1',reason='opt-in real native Harness + provider integration')
@pytest.mark.parametrize('kind,order',[('report','example_first'),('report','theory_first'),('quiz','example_first')])
def test_native_harness_generates_and_reviews_real_content(kind,order):
    import os
    from datetime import datetime,timedelta,timezone
    from pathlib import Path
    import dotenv
    from app.chat.harness.content_gateway import ContentGateway
    from app.course_preparation.harness_generation import PreparationHarnessGateway
    settings=dotenv.dotenv_values(os.environ['D_CONTENT_ENV_FILE'])
    configured=ContentGateway(api_base=settings['DEEPSEEK_BASE_URL'],api_key=settings['DEEPSEEK_API_KEY'],
        model_name=settings.get('LLM_MODEL') or 'deepseek-v4-pro')
    class Ledger:
        def __init__(self): self.actions=[]
        def begin_action(self,context,key,kind,data,cost):
            action={'action_id':key,'reserved':cost.model_dump()}
            self.actions.append(action)
            return action
        def finish_action(self,context,action_id,receipt,actual=None,failed=False):
            action=next(a for a in self.actions if a['action_id']==action_id)
            response=receipt.get('model_response') or {}
            action.update(failed=failed,evidence={k:response.get(k) for k in ('runtime','phase','skill','provider','model','spec_digest')},
                          usage=(response.get('response') or {}).get('usage'))
    value=payload(kind,order)
    value.research_context=('提供的材料：模型输出工具名与参数，程序校验名称、权限和参数后执行工具。'
        'add(a,b)计算两个数的和；add(a=12,b=30)得42；缺少b时校验失败，工具不执行。')
    if kind=='quiz':
        value.teaching_context['requirements']=[{'requirement_id':'req-order','text':'每题先给具体调用例子，再问职责或缺失参数；总共两道单选题，每项都有对应解析','source_quote':'本次要求','source_document_id':None}]
    ledger=Ledger()
    root=PreparationHarnessGateway(configured,ledger,{'artifact_id':'d-native-test','spec_digest':value.spec_digest},
        deadline=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
    if kind=='report':
        body,state=reviewed_report.generate_reviewed_report(value,root)
        artifact={'content':body,'generation_state':state}
        assert reviewed_report.verified_review(artifact)
        sections=list(report_sections(body).values())
        if order=='example_first':
            assert '12' in sections[0] and '30' in sections[0] and '42' in sections[0]
        else:
            assert any('12' in s and '42' in s for s in sections[1:])
        assert '面试表达' not in body
    else:
        artifact=reviewed_resource.ReviewedResourceGenerator(root).generate(value,job_id='j',config_snapshot_id='c')['artifacts'][0]
        assert reviewed_resource.verified_resource(artifact,'quiz')
        assert len(artifact['content']['questions'])==2
    phases={a['evidence']['phase'] for a in ledger.actions}
    assert {'resource_write','resource_review'} <= phases
    for action in ledger.actions:
        assert not action['failed']
        assert action['evidence']['runtime']=='deepseek-harness'
        assert action['evidence']['skill']['loaded'] is True
        assert action['evidence']['skill']['sha256']
        assert action['usage']['total_tokens']>0
    destination=os.getenv('D_CONTENT_EVIDENCE_DIR')
    if destination:
        Path(destination,f'native-{kind}-{order}.json').write_text(json.dumps({'scope':'real native Harness SDK and provider; in-memory usage ledger; not full course delivery',
            'teaching_context':value.teaching_context, 'artifact':artifact,'calls':ledger.actions},ensure_ascii=False,indent=2))


@pytest.mark.parametrize('kind',['report','quiz'])
def test_A_payload_D_content_F_alignment_use_the_same_real_contract(phases,kind):
    from app.course_preparation.generation_context import automatic_payload
    from app.course_preparation.generation_contracts import ResourceSpec
    from app.course_preparation.resource_alignment import validate_artifact
    from tests.course_preparation.test_generation_adapter import spec as legacy_spec
    specification=ResourceSpec.model_validate({**legacy_spec(), 'schema_version':2, 'resource_type':kind,
        'teaching_context':context(), 'objectives':context()['objectives'], 'objective_ids':context()['objective_ids'],
        'learning_check':context()['self_check']}).model_dump(mode='json')
    value=automatic_payload(specification,{'owner_user_id':'alice','resource_id':'resource-tools'})
    gateway=CountingGateway(kind)
    if kind=='report':
        body,state=reviewed_report.generate_reviewed_report(value,gateway)
        content={'content':body,'generation_state':state}
    else:
        content=reviewed_resource.ReviewedResourceGenerator(gateway).generate(value,job_id='j',config_snapshot_id='c')['artifacts'][0]
    artifact={'spec':specification,'spec_digest':value_digest(specification),'resource_type':kind,
              'content':content,'content_digest':value_digest(content)}
    validate_artifact(artifact)
    assert content['generation_state']['preparation']['spec_digest']==artifact['spec_digest']
