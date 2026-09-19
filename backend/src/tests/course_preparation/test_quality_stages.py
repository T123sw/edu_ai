from types import SimpleNamespace
from app.course_preparation.quality import QualityStages
from app.course_preparation.tool_registry import digest
from app.course_preparation.schemas import PreparationRequest
from uuid import uuid4


def test_full_bodies_are_reviewed_one_node_at_a_time_before_course_gate(monkeypatch):
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState, 'model_validate', lambda _: SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent, '_validate_path', lambda *_: None)
    monkeypatch.setattr(module, 'candidate_manifest', lambda *_: SimpleNamespace(model_dump=lambda **_: {'checked':True}))
    specs = [{'node_id':key,'objectives':[key]} for key in ('a','b')]
    artifacts = [{'artifact_id':key, 'spec':spec, 'spec_digest':digest(spec), 'status':'draft', 'content_digest':digest(key),
                  'resource_type':'report', 'content':{'content':key*60000}} for key,spec in zip(('a','b'),specs)]
    checkpoint = {'research_state':{}, 'resource_specs':specs, 'generation_receipts':{digest(spec):{'id':i} for i,spec in enumerate(specs)},
                  'brief':{}, 'plan':{'nodes':[{'node_key':key} for key in ('a','b')]}, 'node_evidence':{'a':[], 'b':[]}}
    calls=[]
    class Model:
        def decide(self, context, tools, **kw):
            calls.append(context)
            node=context.get('node')
            if node: assert context['artifacts'][0]['content'] == node['node_key']*60000
            else: assert len(context['node_reviews'])==2 and all('content' not in a for a in context['artifacts'])
            return 'review_course_delivery', {'decision':'pass','checked_node_ids':[node['node_key']] if node else ['a','b']}
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习')
    stages=QualityStages(SimpleNamespace(get=lambda **_:SimpleNamespace(request=request)),
        SimpleNamespace(read_result=lambda owner, receipt:artifacts[receipt['id']]),
        SimpleNamespace(validate=lambda *_:None),lambda *_:SimpleNamespace(model=Model()))
    context=SimpleNamespace(checkpoint=checkpoint,owner_user_id='alice',preparation_id='prep-test')
    for expected in (None,None,'commit'):
        result=stages.review(context)
        assert result.next_stage==expected
        context.checkpoint=result.checkpoint
    assert len(calls)==3


def test_malformed_review_is_repaired_before_any_commit(monkeypatch):
    import app.course_preparation.quality as module
    from app.course_preparation.research_agent import ResearchError
    import pytest
    monkeypatch.setattr(module.ResearchState,'model_validate',lambda _:SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent,'_validate_path',lambda *_:None)
    monkeypatch.setattr(module,'candidate_manifest',lambda *_:SimpleNamespace(model_dump=lambda **_:{'checked':True}))
    spec={'node_id':'a','objectives':['a']}
    artifact={'artifact_id':'a','spec':spec,'spec_digest':digest(spec),'status':'draft','content_digest':digest('body'),'resource_type':'report','content':{'content':'body'}}
    cp={'research_state':{},'resource_specs':[spec],'generation_receipts':{digest(spec):{}},'brief':{},'plan':{'nodes':[{'node_key':'a'}]},'node_evidence':{'a':[]}}
    calls=[]
    class Model:
        valid=False
        def decide(self,context,tools,**kwargs):
            calls.append(context)
            return 'review_course_delivery',({'decision':'pass','checked_node_ids':['a']} if self.valid else {'json':'{"decision":"pass"}'})
    model=Model();request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习')
    stages=QualityStages(SimpleNamespace(get=lambda **_:SimpleNamespace(request=request)),SimpleNamespace(read_result=lambda *_:artifact),SimpleNamespace(validate=lambda *_:None),lambda *_:SimpleNamespace(model=model))
    context=SimpleNamespace(checkpoint=cp,owner_user_id='alice',preparation_id='prep')
    first=stages.review(context);assert first.next_stage is None and not first.checkpoint.get('quality')
    context.checkpoint=first.checkpoint
    second=stages.review(context);context.checkpoint=second.checkpoint
    assert calls[-1]['last_schema_error']
    with pytest.raises(ResearchError,match='COURSE_REVIEW_INVALID'):stages.review(context)
    model.valid=True
    result=stages.review(context)
    assert 'a' in result.checkpoint['node_quality_reviews'] and result.next_stage is None


def test_format_repair_updates_job_receipt_without_spec_revision():
    from copy import deepcopy
    spec={'node_id':'a','revision':1}
    failure={'code':'MISSING_OPTIONS','phase':'resource_review','category':'review_format','message':'缺少选项审阅',
             'retry_scope':'review','artifact_id':'a','content_digest':None}
    artifact={'artifact_id':'a','spec_digest':digest(spec),'failure_detail':failure,'content':{'_review_candidate':{'content':'saved'}}}
    cp={'resource_specs':[spec],'artifacts':[artifact],'generation_receipts':{digest(spec):{'job_id':'failed-job'}},
        'quality':{'issues':[{'artifact_ids':['a'],'reason':'missing fields'}]}}
    calls=[]
    def resume(context,artifact_id,**kwargs):
        calls.append((artifact_id,kwargs))
        return {'artifact_id':artifact_id,'job_id':'review-job-1'}
    stages=QualityStages(None,SimpleNamespace(resume_review=resume),SimpleNamespace(validate=lambda *_:None),None)
    result=stages.repair(SimpleNamespace(checkpoint=deepcopy(cp),preparation_id='prep'))
    assert result.checkpoint['resource_specs']==[spec]
    assert result.checkpoint['generation_receipts'][digest(spec)]['job_id']=='review-job-1'
    assert calls and result.next_stage=='produce'
