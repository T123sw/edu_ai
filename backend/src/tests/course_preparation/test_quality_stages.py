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
