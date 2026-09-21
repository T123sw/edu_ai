from types import SimpleNamespace
import copy
import re
from uuid import uuid4
import pytest
from tests.course_preparation.test_resource_alignment import quiz, checkpoint
from app.course_preparation.quality import QualityStages
from app.course_preparation.tool_registry import digest
from app.course_preparation.schemas import PreparationRequest


def test_missing_manifest_check_is_repaired_on_quiz_without_lowering_gate(monkeypatch):
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState,'model_validate',lambda _:SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent,'_validate_path',lambda *_:None)
    a=quiz();a['content']['generation_state']['preparation']['objective_bindings'][0]['role']='explanation'
    a['content_digest']=digest(a['content']); cp=checkpoint(a)
    cp.update(research_state={},resource_specs=[a['spec']],generation_receipts={a['spec_digest']:{}})
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习加法')
    stages=QualityStages(SimpleNamespace(get=lambda **_:SimpleNamespace(request=request)),
        SimpleNamespace(read_result=lambda *_:a),SimpleNamespace(validate=lambda *_:None),
        lambda *_:pytest.fail('do not spend a model call before deterministic coverage validation'))
    context=SimpleNamespace(checkpoint=cp,owner_user_id='alice',preparation_id='prep-x')
    result=stages.review(context)
    assert result.next_stage=='repair'
    issue=result.checkpoint['quality']['issues'][0]
    assert issue['artifact_ids']==['a'] and 'n:o1' in issue['reason']


def test_all_overbudget_nodes_are_repaired_in_one_round(monkeypatch):
    from copy import deepcopy
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState,'model_validate',lambda _:SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent,'_validate_path',lambda *_:None)
    rows=[];nodes=[]
    for key in ('a','b'):
        a=quiz();a['artifact_id']=key;a['resource_id']=key
        spec=a['spec'];spec['node_id']=key;spec['objective_ids']=[key+':o1']
        ctx=spec['teaching_context'];ctx['node_id']=key;ctx['objective_ids']=spec['objective_ids']
        meta=a['content']['generation_state']['preparation'];meta['objective_bindings'][0]['objective_id']=key+':o1'
        meta['spec_digest']=a['spec_digest']=digest(spec);meta['teaching_context_digest']=digest(ctx);a['content_digest']=digest(a['content']);rows.append(a)
        nodes.append({'node_key':key,'title':key,'objectives':['加法'],'prerequisite_keys':[],'minutes':2})
    cp={'artifacts':rows,'brief':{'audience':'初学者'},'node_evidence':{'a':[],'b':[]},'plan':{'nodes':nodes},
        'research_state':{},'resource_specs':[r['spec'] for r in rows],'generation_receipts':{r['spec_digest']:{'id':i} for i,r in enumerate(rows)}}
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习加法')
    stages=QualityStages(SimpleNamespace(get=lambda **_:SimpleNamespace(request=request)),
        SimpleNamespace(read_result=lambda owner,receipt:rows[receipt['id']]),SimpleNamespace(validate=lambda *_:None),
        lambda *_:pytest.fail('deterministic checks precede model calls'))
    result=stages.review(SimpleNamespace(checkpoint=cp,owner_user_id='alice',preparation_id='prep-x'))
    assert result.next_stage=='repair'
    assert {i['artifact_ids'][0] for i in result.checkpoint['quality']['issues']}=={'a','b'}


def test_joint_duration_repair_targets_are_feasible_without_changing_estimates():
    rows=[]
    for node,values in [('n1',[3.5,3.1,7.5]),('n2',[3.7,7.86,8.42])]:
        for kind,value in zip(['report','quiz','classroom'],values):
            rows.append({'artifact_id':node+kind,'spec':{'node_id':node,'required':True},
                'content':{'generation_state':{'preparation':{'duration':{'basis':'estimated','value_minutes':value}}}}})
    before=copy.deepcopy(rows)
    issues=QualityStages._duration_issues(rows,[{'node_key':'n1','minutes':10},{'node_key':'n2','minutes':10}],20)
    assert rows==before
    limits={}
    for issue in issues:
        assert len(issue['artifact_ids'])==1
        limit=float(re.search(r'本资源.*不超过 ([0-9.]+) 分钟',issue['reason']).group(1))
        assert limit > 0
        assert issue['artifact_ids'][0] not in limits
        limits[issue['artifact_ids'][0]]=limit
    assert set(limits)=={a['artifact_id'] for a in rows}
    for issue in issues:
        assert issue['resource_duration_cap_minutes'] == limits[issue['artifact_ids'][0]]
    assert limits['n2classroom'] > 4
    for node in ['n1','n2']:
        assert sum(limits.get(a['artifact_id'],a['content']['generation_state']['preparation']['duration']['value_minutes']) for a in rows if a['spec']['node_id']==node)<=10


def test_global_duration_cap_uses_proposed_node_reductions_once():
    rows=[]
    for node in ('a','b'):
        row=quiz();row['artifact_id']=node;row['spec']['node_id']=node
        row['content']['generation_state']['preparation']['duration']={'basis':'estimated','value_minutes':8}
        rows.append(row)
    before=copy.deepcopy(rows)
    issues=QualityStages._duration_issues(rows,[{'node_key':'a','minutes':6},{'node_key':'b','minutes':6}],10)
    assert rows==before and len(issues)==2
    targets={i['artifact_ids'][0]:float(re.search(r'不超过 ([0-9.]+) 分钟',i['reason']).group(1)) for i in issues}
    assert sum(targets.values())<=10 and max(targets.values())<=6


def test_duration_repair_keeps_retained_resources_fixed():
    rows=[]
    for key in ('retained:old', 'new'):
        row=quiz();row['artifact_id']=key;row['spec']['node_id']='n'
        row['content']['generation_state']['preparation']['duration']={'basis':'estimated','value_minutes':4}
        rows.append(row)
    issues=QualityStages._duration_issues(rows,[{'node_key':'n','minutes':6}],6)
    assert len(issues)==1 and issues[0]['artifact_ids']==['new']
    assert issues[0]['resource_duration_cap_minutes']==2


def test_fractional_duration_targets_are_valid_context_but_zero_and_nan_are_not():
    from app.course_preparation.teaching_context import TeachingContext
    from tests.course_preparation.test_generated_content_constraints import context
    assert TeachingContext.model_validate({**context(), 'resource_target_minutes': 2.37}).resource_target_minutes==2.37
    for value in (0,-1,float('inf'),float('nan')):
        with pytest.raises(ValueError):TeachingContext.model_validate({**context(), 'resource_target_minutes': value})
