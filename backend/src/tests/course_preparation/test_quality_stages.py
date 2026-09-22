import pytest
from types import SimpleNamespace
from app.course_preparation.quality import QualityStages
from app.course_preparation.tool_registry import digest
from app.course_preparation.schemas import PreparationRequest
from uuid import uuid4


def test_duration_repair_persists_fractional_cap_without_changing_prior_spec():
    from copy import deepcopy
    from tests.course_preparation.test_resource_alignment import quiz
    artifact = quiz()
    spec = artifact['spec']; spec['revision'] = 1
    artifact['spec_digest'] = digest(spec)
    before = deepcopy(spec)
    cp = {'resource_specs': [spec], 'artifacts': [artifact], 'generation_receipts': {},
          'quality': {'issues': [{'artifact_ids': [artifact['artifact_id']], 'reason': 'shorten actual content',
                                 'resource_duration_cap_minutes': 2.37}]}}
    stages = QualityStages(None, None, SimpleNamespace(validate=lambda *_: None), None)
    result = stages.repair(SimpleNamespace(checkpoint=cp, preparation_id='prep'))
    revised = result.checkpoint['resource_specs'][0]
    assert spec == before
    assert revised['teaching_context']['resource_target_minutes'] is None
    assert revised['teaching_context']['resource_repair_target_minutes'] == 2.37
    assert revised['revision'] == 2 and digest(revised) != digest(spec)


def test_full_bodies_are_reviewed_one_node_at_a_time_before_course_gate(monkeypatch):
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState, 'model_validate', lambda _: SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent, '_validate_path', lambda *_: None)
    monkeypatch.setattr(module, 'candidate_manifest', lambda *_: SimpleNamespace(model_dump=lambda **_: {'checked':True}))
    specs = [{'node_id':key,'objectives':[key]} for key in ('a','b')]
    artifacts = [{'artifact_id':key, 'spec':spec, 'spec_digest':digest(spec), 'status':'draft', 'content_digest':digest(key),
                  'resource_type':'report', 'content':{'content':key*60000, 'generation_state': {'resource_review': {
                      'decision':'pass','content_sha256':digest(key), 'history':['past audit '*20000]}}}}
                 for key,spec in zip(('a','b'),specs)]
    checkpoint = {'research_state':{}, 'resource_specs':specs, 'generation_receipts':{digest(spec):{'id':i} for i,spec in enumerate(specs)},
                  'brief':{}, 'plan':{'nodes':[{'node_key':key} for key in ('a','b')]}, 'node_evidence':{'a':[], 'b':[]}}
    calls=[]
    class Model:
        def decide(self, context, tools, **kw):
            from app.course_preparation.context import context_packet
            # Stored audit history must not displace complete teaching bodies.
            context_packet(context, tools, max_tokens=128000, native_skill=True)
            calls.append(context)
            node=context.get('node')
            if node:
                assert context['review_mode'] == 'node'
                assert context['artifacts'][0]['content'] == node['node_key']*60000
            else:
                assert context['review_mode'] == 'course'
                assert len(context['node_reviews']) == 2 and all('content' not in a for a in context['artifacts'])
                assert '不重复正文审阅' in tools[0]['function']['description']
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


@pytest.mark.parametrize('minutes', [None, 11.41, 30])
@pytest.mark.parametrize('decision', ['pass', 'fail'])
def test_advisory_duration_reaches_semantic_review_without_rewriting(monkeypatch, minutes, decision):
    import app.course_preparation.quality as module
    from tests.course_preparation.test_resource_alignment import quiz, checkpoint
    from copy import deepcopy
    monkeypatch.setattr(module.ResearchState, 'model_validate', lambda _: SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent, '_validate_path', lambda *_: None)
    artifact = quiz()
    meta = artifact['content']['generation_state']['preparation']
    meta['duration'] = {'basis': 'unknown' if minutes is None else 'estimated',
                        'value_minutes': minutes, 'method': 'uncalibrated estimate'}
    artifact['content_digest'] = digest(artifact['content'])
    original = deepcopy(artifact)
    cp = checkpoint(artifact)
    cp.update(research_state={}, resource_specs=[artifact['spec']],
              generation_receipts={artifact['spec_digest']: {}})
    request = PreparationRequest(request_id=uuid4(), operation='create_course', goal='学习加法',
                                 overrides={'total_minutes': 10})
    calls = []
    class Model:
        def decide(self, context, tools, **kwargs):
            calls.append(context)
            return 'review_course_delivery', {'decision': decision, 'checked_node_ids': ['n'],
                'issues': [] if decision == 'pass' else [{'artifact_ids': ['a'], 'reason': '答案错误'}]}
    stages = QualityStages(SimpleNamespace(get=lambda **_: SimpleNamespace(request=request)),
        SimpleNamespace(read_result=lambda *_: artifact), SimpleNamespace(validate=lambda *_: None),
        lambda *_: SimpleNamespace(model=Model()))
    ctx = SimpleNamespace(checkpoint=cp, owner_user_id='alice', preparation_id='prep')
    result = stages.review(ctx)
    if decision == 'pass':
        ctx.checkpoint = result.checkpoint
        result = stages.review(ctx)
        assert result.next_stage == 'commit' and len(calls) == 2
    else:
        assert result.next_stage == 'repair' and len(calls) == 1
        assert result.checkpoint['quality']['issues'][0]['reason'] == '答案错误'
    assert artifact == original
    assert result.checkpoint['duration_summary']['enforcement'] == 'advisory'


def test_node_review_shares_context_without_losing_resource_specific_requirements():
    from copy import deepcopy
    from app.course_preparation.quality import node_review_artifacts
    from tests.course_preparation.test_resource_alignment import quiz
    from app.course_preparation.context import context_packet
    rows = [quiz() for _ in range(3)]
    for i, row in enumerate(rows):
        row['artifact_id'] = str(i)
        row['spec']['teaching_context']['request_goal'] = '完整教学要求' * 2000
    rows[-1]['spec']['teaching_context']['resource_target_minutes'] = 2.5
    original = deepcopy(rows)
    packet = node_review_artifacts(rows)
    assert len(packet['teaching_contexts']) == 2
    assert packet['artifacts'][0]['teaching_context_ref'] == packet['artifacts'][1]['teaching_context_ref']
    assert packet['artifacts'][2]['teaching_context_ref'] != packet['artifacts'][0]['teaching_context_ref']
    for row, source in zip(packet['artifacts'], rows):
        assert row['content'] == source['content']['content']
        assert row['preparation'] == source['content']['generation_state']['preparation']
        assert packet['teaching_contexts'][row['teaching_context_ref']] == source['spec']['teaching_context']
    assert rows == original
    result = context_packet({'phase': 'course_review', **packet}, [], max_tokens=128000, native_skill=True)
    assert result['input_token_upper_bound'] + result['output_token_limit'] <= 128000
