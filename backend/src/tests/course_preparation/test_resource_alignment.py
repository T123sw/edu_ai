from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.course_preparation.resource_alignment import (validate_artifact, resource_checks, resolve_locator, duration_summary)
from app.course_preparation.quality import candidate_manifest, check_digest, QualityStages
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.tool_registry import digest


def test_node_requirements_are_covered_across_resources_without_cross_node_substitution():
    from app.course_preparation.resource_alignment import node_requirement_issues
    a=quiz(); b=deepcopy(a)
    for item,rid in [(a,'req1'),(b,'req2')]:
        context=item['spec']['teaching_context']
        context['requirements'] += [{'requirement_id':'req2','text':'解释进位'}, {'requirement_id':'other','text':'后续节点内容'}]
        context['requirement_ids']=['req1','req2']
        meta=item['content']['generation_state']['preparation']
        meta['applied_requirements'][0]['requirement_id']=rid
        item['spec_digest']=meta['spec_digest']=digest(item['spec'])
        meta['teaching_context_digest']=digest(context)
        item['content_digest']=digest(item['content'])
        validate_artifact(item)
    b['artifact_id']='b'; b['resource_id']='b-resource'
    nodes=[{'node_key':'n','requirement_ids':['req1','req2']}]
    assert node_requirement_issues([a,b],nodes)==[]
    assert node_requirement_issues([a],nodes)[0]['reason']=='NODE_REQUIREMENT_COVERAGE_MISSING:req2'
    b['spec']['node_id']='other-node'
    assert node_requirement_issues([a,b],nodes)[0]['reason']=='NODE_REQUIREMENT_COVERAGE_MISSING:req2'


def quiz():
    context={'node_id':'n','objective_ids':['n:o1'], 'requirements':[{'requirement_id':'req1','text':'练习加法'}]}
    spec={'schema_version':2,'node_id':'n','title':'加法','resource_type':'quiz','required':True,'revision':1,
          'objective_ids':['n:o1'],'objectives':['加法'],'teaching_context':context,'evidence':[{'source_id':'s'}]}
    body={'questions':[{'id':'q-add','question':'1+1=?','options':['1','2','3'],'answer':'2','analysis':'1+1=2'}]}
    meta={'schema_version':1,'spec_digest':digest(spec),'teaching_context_digest':digest(context),
          'objective_bindings':[{'objective_id':'n:o1','role':'check','locator':{'question_id':'q-add'}}],
          'applied_requirements':[{'requirement_id':'req1','locator':{'question_id':'q-add'},'explanation':'加法练习'}],
          'duration':{'value_minutes':3,'basis':'estimated','method':'每题作答与反馈共3分钟'}}
    content={'content':body,'generation_state':{'preparation':meta}}
    return {'artifact_id':'a','resource_id':'r','resource_version':1,'resource_type':'quiz','status':'draft',
            'spec':spec,'spec_digest':digest(spec),'content':content,'content_digest':digest(content)}


def checkpoint(artifact):
    return {'artifacts':[artifact], 'brief':{'audience':'初学者'}, 'node_evidence':{'n':[]},
            'plan':{'nodes':[{'node_key':'n','title':'加法','objectives':['加法'],'prerequisite_keys':[],'minutes':10}]}}


def test_generated_quiz_manifest_checks_resolve_real_questions():
    artifact=quiz();validate_artifact(artifact)
    value=candidate_manifest(SimpleNamespace(preparation_id='prep-x',owner_user_id='alice'),checkpoint(artifact),
        PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习加法')).model_dump(mode='json')
    node=value['nodes'][0];question_ids={q['id'] for q in artifact['content']['content']['questions']}
    checks=[c for c in node['checks'] if c['mode']=='practice']
    assert checks and all(c['locator']['question_id'] in question_ids for c in checks)


@pytest.mark.parametrize('mutation', ['objective','question','requirement','context','body','empty'])
def test_mapping_and_digest_tampering_rejected(mutation):
    a=quiz();meta=a['content']['generation_state']['preparation']
    if mutation=='objective':meta['objective_bindings'][0]['objective_id']='other:o1'
    if mutation=='question':meta['objective_bindings'][0]['locator']['question_id']='missing'
    if mutation=='requirement':meta['applied_requirements'][0]['requirement_id']='invented'
    if mutation=='context':meta['teaching_context_digest']=digest('old')
    if mutation=='empty':meta['objective_bindings'][0]['locator']={}
    if mutation=='body':a['content']['content']['questions'][0]['answer']='wrong'
    else:a['content_digest']=digest(a['content'])
    with pytest.raises(ValueError):validate_artifact(a)


def test_scene_and_action_must_belong_together_and_never_become_quiz_check():
    body={'scenes':[{'id':'s1','actions':[{'id':'a1'}]},{'id':'s2','actions':[{'id':'a2'}]}]}
    with pytest.raises(ValueError,match='ACTION_SCENE'):resolve_locator('classroom',body,{'scene_id':'s1','action_id':'a2'})
    with pytest.raises(ValueError):resolve_locator('classroom',body,{'question_id':'s1'})
    with pytest.raises(ValueError):resolve_locator('classroom',body,{'page':1})


def test_no_report_check_is_fabricated_from_a_missing_fixed_heading():
    a=quiz();a['resource_type']='report';a['spec'].pop('schema_version');a['content']={'content':'## 原理\n内容'}
    assert resource_checks(a,'n')==[]


def test_duration_summary_preserves_overrun_and_unknown_without_blocking():
    a = quiz(); nodes = checkpoint(a)['plan']['nodes']
    nodes[0]['minutes'] = 1
    summary = duration_summary([a], nodes, hard_limit=2)
    assert summary['required_known_minutes'] == 3
    assert summary['target_minutes'] == 2 and summary['enforcement'] == 'advisory'
    a['content']['generation_state']['preparation']['duration'] = {'basis': 'unknown', 'value_minutes': None, 'method': ''}
    assert duration_summary([a], nodes, hard_limit=1)['unknown_artifact_ids'] == ['a']



def test_old_pass_digest_changes_for_context_body_and_exact_version():
    a=quiz();cp=checkpoint(a);original=check_digest(cp)
    for field in ('content','spec','resource_version'):
        changed=deepcopy(cp)
        if field=='resource_version':changed['artifacts'][0][field]=2
        else:changed['artifacts'][0][field]['tampered']=True
        assert check_digest(changed)!=original


def test_content_repair_changes_only_affected_spec_and_preserves_body_baseline():
    a=quiz();b=deepcopy(a);b['artifact_id']='b';b['spec']['title']='另一个资源';b['spec_digest']=digest(b['spec'])
    cp=checkpoint(a);cp.update(artifacts=[a,b],resource_specs=[a['spec'],b['spec']],
        quality={'issues':[{'artifact_ids':['a'],'reason':'选项解析错误'}]})
    stage=QualityStages(None,None,SimpleNamespace(validate=lambda *_:None),None)
    result=stage.repair(SimpleNamespace(checkpoint=cp,preparation_id='p'))
    assert result.checkpoint['resource_specs'][1]==b['spec']
    fixed=result.checkpoint['resource_specs'][0]
    assert fixed['revision']==2 and fixed['original_content']==a['content']['content']
    assert 'quality' not in result.checkpoint and result.next_stage=='produce'


def audit_fixture():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[4]
    return json.loads((root/'docs/acceptance/artifacts/2026-09-19-preparation-agent-audit/quality-counterexamples.json').read_text())


def test_real_generated_quiz_checks_have_individual_objective_locations():
    record=audit_fixture()
    a=next(a for a in record['artifacts'] if a['resource_type']=='quiz')
    node=next(n for n in record['plan']['nodes'] if n['node_key']==a['spec']['node_id'])
    # Explicit mapping of the archived questions to their actual objectives, not
    # a cross product assigning every question to every node objective.
    mappings=zip(a['spec']['objective_ids'],('q1','q2','q3','q5'))
    a['content']['generation_state']['preparation']={'objective_bindings':[
        {'objective_id':oid,'locator':{'question_id':qid},'role':'check'} for oid,qid in mappings]}
    cp={'artifacts':[a],'plan':{'nodes':[node]},'brief':{'audience':a['spec']['audience']},'node_evidence':{node['node_key']:[]}}
    manifest=candidate_manifest(SimpleNamespace(owner_user_id='alice',preparation_id='audit-quiz'),cp,
        PreparationRequest.model_validate(record['request'])).model_dump(mode='json')
    question_ids={q['id'] for q in a['content']['content']['questions']}
    checks=[c for c in manifest['nodes'][0]['checks'] if c['mode']=='practice']
    assert checks and all(c['locator']['question_id'] in question_ids for c in checks)
    assert all(len(c['objective_ids'])==1 for c in checks)


@pytest.mark.parametrize('kind,reason', [('report','先例后理要求未落实，首个解释先于首个例子')])
def test_archived_semantic_failure_targets_only_bad_resource(monkeypatch,kind,reason):
    import app.course_preparation.quality as module
    record=audit_fixture();artifacts=record['artifacts']
    bad=next(a for a in artifacts if a['resource_type']==kind)
    cp={'artifacts':artifacts,'resource_specs':[a['spec'] for a in artifacts],
        'generation_receipts':{a['spec_digest']:{'artifact_id':a['artifact_id']} for a in artifacts},
        'research_state':{},'plan':record['plan'],'brief':{},
        'node_evidence':{n['node_key']:[] for n in record['plan']['nodes']}}
    monkeypatch.setattr(module.ResearchState,'model_validate',lambda _:SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent,'_validate_path',lambda *_:None)
    monkeypatch.setattr(module,'candidate_manifest',lambda *_:None)
    # This test checks semantic-review rejection plumbing with a scripted critic,
    # not live model accuracy. The original hard limit is separately tested.
    request=PreparationRequest.model_validate(record['request']).model_copy(update={
        'overrides':PreparationRequest.model_validate(record['request']).overrides.model_copy(update={'total_minutes':None})})
    class Critic:
        def decide(self,context,tools,**kwargs):
            seen=next(a for a in context['artifacts'] if a['kind']==bad['resource_type'])
            assert seen['content']==bad['content']['content']
            assert '先用 12 加 30 的例子' in context['request']['goal']
            return 'review_course_delivery',{'decision':'fail','checked_node_ids':[bad['spec']['node_id']],
                'issues':[{'artifact_ids':[seen['artifact_id']],'reason':reason}]}
    generation=SimpleNamespace(read_result=lambda owner,receipt:next(a for a in artifacts if a['artifact_id']==receipt['artifact_id']))
    stages=QualityStages(SimpleNamespace(get=lambda **_:SimpleNamespace(request=request)),generation,
        SimpleNamespace(validate=lambda *_:None),lambda *_:SimpleNamespace(model=Critic()))
    context=SimpleNamespace(checkpoint=cp,preparation_id='audit',owner_user_id='alice')
    reviewed=stages.review(context)
    assert reviewed.next_stage=='repair' and reviewed.checkpoint['quality']['decision']=='fail'
    context.checkpoint=reviewed.checkpoint
    repaired=stages.repair(context)
    for old,new in zip(cp['resource_specs'],repaired.checkpoint['resource_specs']):
        assert (new['revision']==old['revision']+1) if old==bad['spec'] else (new==old)


def test_real_classroom_question_locator_stays_in_review_metadata():
    body={'scenes':[{'id':'s1','content':{'questions':[{'id':'q1'}]}},
                    {'id':'s2','content':{'questions':[{'id':'q2'}]}}]}
    resolve_locator('classroom',body,{'scene_id':'s1','question_id':'q1'})
    with pytest.raises(ValueError,match='QUESTION_SCENE'):
        resolve_locator('classroom',body,{'scene_id':'s1','question_id':'q2'})
    a=quiz();a['resource_type']='classroom';a['content']['content']=body
    a['content']['generation_state']['preparation']['objective_bindings']=[{
        'objective_id':'n:o1','role':'check','locator':{'scene_id':'s1','question_id':'q1'}}]
    assert resource_checks(a,'n')==[]


def test_v2_classroom_cannot_hide_failed_render_in_limitations():
    a=quiz();a['resource_type']='classroom'
    meta=a['content']['generation_state']['preparation']
    meta['render_checks']={'passed':False,'issues':['required image unavailable']}
    a['content']['generation_state']['limitations']=['未提供必须的图片']
    a['content_digest']=digest(a['content'])
    with pytest.raises(ValueError,match='RENDER_UNVERIFIED'):validate_artifact(a)
