from types import SimpleNamespace
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
