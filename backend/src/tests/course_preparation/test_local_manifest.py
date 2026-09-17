from types import SimpleNamespace
from uuid import uuid4
from copy import deepcopy
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.quality import candidate_manifest
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation


def test_supplement_preserves_route_and_old_resources(ready):
    repo, context, delivery = ready
    result = delivery.commit(context).result_ref
    base=delivery.read('alice',result['course_id'])
    cp=deepcopy(context.checkpoint)
    cp['target_snapshot']={'manifest':base,'node':base['nodes'][0],'resource':None,'source_owner':'alice'}
    cp['artifacts'][0].update(resource_id='supplement-report',artifact_id='new-artifact',resource_version=1)
    request=PreparationRequest(request_id=uuid4(),operation='supplement_node',goal='增加一个面试案例',
        target={'course_id':base['course_id'],'base_manifest_version':1,'node_id':'tools'})
    manifest=candidate_manifest(SimpleNamespace(owner_user_id='alice',preparation_id='prep-supplement'),cp,request).model_dump(mode='json')
    assert manifest['version']==2 and manifest['route_version']==base['route_version']
    assert manifest['goal']==base['goal']
    assert manifest['nodes'][0]['resources'][0]==base['nodes'][0]['resources'][0]
    assert not manifest['nodes'][0]['resources'][-1]['required']
    assert manifest['nodes'][0]['checks']==base['nodes'][0]['checks']


def test_supplement_delivery_keeps_old_exact_resource_and_advances_pointer(ready):
    from app.course_preparation.adapters.generation import GenerationAdapter
    from app.course_preparation.adapters.targets import TargetStore
    from app.course_preparation.runtime_contracts import BudgetCost
    from app.course_preparation.quality import check_digest,RULE_VERSION
    from app.course_preparation.tool_registry import digest
    repo, first_context, delivery=ready
    course=delivery.commit(first_context).result_ref['course_id']
    original=delivery.read('alice',course)
    request=PreparationRequest(request_id=uuid4(),operation='supplement_node',goal='增加面试案例',
        target={'course_id':course,'base_manifest_version':1,'node_id':'tools'})
    task=repo.submit('alice',request)
    context=repo.claim('supplement',preparation_id=task['preparation_id'])
    from app.course_preparation.artifact_store import ArtifactStore
    store=ArtifactStore(repo)
    cp=deepcopy(first_context.checkpoint)
    spec={**cp['artifacts'][0]['spec'],'required':False}
    action=repo.begin_action(context,'supplement','generate_resource',spec,BudgetCost(calls=1))
    draft=store.create(context,action['action_id'],spec)
    child=store.claim('alice',draft['artifact_id'])
    store.save(child,cp['artifacts'][0]['content'])
    record=store.get('alice',draft['artifact_id'],content=True)
    cp['artifacts']=[record]
    cp['target_snapshot']=TargetStore(repo.engine).read('alice',request.target)
    cp['quality']={'decision':'pass','input_digest':check_digest(cp),'rule_version':RULE_VERSION}
    cp['candidate_manifest']=candidate_manifest(context,cp,request).model_dump(mode='json')
    repo.checkpoint(context,cp)
    for stage in ('research_scope','plan','research_nodes','produce','review','commit'):
        context=repo.transition(context,stage,reason='NO_UPLOADS' if stage=='research_scope' else None)
    assert delivery.commit(context).result_ref['manifest_version']==2
    latest=delivery.read('alice',course)
    assert latest['nodes'][0]['resources'][0]==original['nodes'][0]['resources'][0]
    assert len(latest['nodes'][0]['resources'])==2
    assert delivery.read('alice',course,1)==original


def test_two_local_deliveries_from_same_base_have_one_winner(ready):
    import pytest
    from threading import Barrier
    from concurrent.futures import ThreadPoolExecutor
    from app.course_preparation.adapters.targets import TargetStore
    from app.course_preparation.artifact_store import ArtifactStore
    from app.course_preparation.runtime_contracts import BudgetCost
    from app.course_preparation.quality import check_digest,RULE_VERSION
    from app.course_preparation.lifecycle_repository import RevisionConflict
    repo,original_context,delivery=ready
    if repo.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL concurrent version commit')
    course=delivery.commit(original_context).result_ref['course_id']
    def candidate():
        request=PreparationRequest(request_id=uuid4(),operation='supplement_node',goal='增加案例',target={'course_id':course,'base_manifest_version':1,'node_id':'tools'})
        task=repo.submit('alice',request);context=repo.claim('race',preparation_id=task['preparation_id'])
        cp=deepcopy(original_context.checkpoint);spec={**cp['artifacts'][0]['spec'],'required':False}
        action=repo.begin_action(context,'supplement','generate_resource',spec,BudgetCost(calls=1))
        store=ArtifactStore(repo);draft=store.create(context,action['action_id'],spec);child=store.claim('alice',draft['artifact_id'])
        if child:store.save(child,cp['artifacts'][0]['content'])
        cp['artifacts']=[store.get('alice',draft['artifact_id'],content=True)]
        cp['target_snapshot']=TargetStore(repo.engine).read('alice',request.target)
        cp['quality']={'decision':'pass','input_digest':check_digest(cp),'rule_version':RULE_VERSION}
        cp['candidate_manifest']=candidate_manifest(context,cp,request).model_dump(mode='json');repo.checkpoint(context,cp)
        for stage in ('research_scope','plan','research_nodes','produce','review','commit'):
            context=repo.transition(context,stage,reason='NO_UPLOADS' if stage=='research_scope' else None)
        return context
    first,second=candidate(),candidate();barrier=Barrier(2)
    def commit(context):
        barrier.wait()
        try:delivery.commit(context);return 'succeeded'
        except RevisionConflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(commit,context) for context in (first,second)]
        assert sorted(f.result() for f in futures)==['conflict','succeeded']
    latest=delivery.read('alice',course)
    assert latest['version']==2 and len(latest['nodes'][0]['resources'])==2
    assert delivery.read('alice',course,1)['version']==1


def test_route_only_adjustment_keeps_exact_resources_and_goal(ready):
    repo,context,delivery=ready
    course=delivery.commit(context).result_ref['course_id'];base=delivery.read('alice',course)
    cp=deepcopy(context.checkpoint);old=base['nodes'][0]
    cp['target_snapshot']={'manifest':base,'node':None,'resource':None,'source_owner':'alice'}
    cp['plan']['nodes'][0].update(minutes=20,title='面试重点：工具调用')
    cp['retained_node_ids']=[old['node_id']];cp['artifacts']=[]
    request=PreparationRequest(request_id=uuid4(),operation='adjust_course',goal='调整时间并保留原资料',requested_changes=['调整工具调用学习时长到20分钟'],target={'course_id':course,'base_manifest_version':1,'base_route_version':1})
    value=candidate_manifest(SimpleNamespace(owner_user_id='alice',preparation_id='route-only'),cp,request).model_dump(mode='json')
    assert value['nodes'][0]['resources']==old['resources'] and value['nodes'][0]['checks']==old['checks']
    assert value['goal']==base['goal'] and value['route_version']==2 and value['nodes'][0]['estimated_minutes']==20


def test_route_only_production_submits_no_generation_jobs(ready):
    from app.course_preparation.production_stages import ProductionStages
    from app.course_preparation.adapters.targets import TargetStore
    repo,original,delivery=ready;course=delivery.commit(original).result_ref['course_id']
    request=PreparationRequest(request_id=uuid4(),operation='adjust_course',goal='调整时间',requested_changes=['时长改为20分钟'],target={'course_id':course,'base_manifest_version':1,'base_route_version':1})
    task=repo.submit('alice',request);context=repo.claim('route-only',preparation_id=task['preparation_id'])
    cp=deepcopy(original.checkpoint);cp['plan']['nodes'][0]['minutes']=20;cp['target_snapshot']=TargetStore(repo.engine).read('alice',request.target)
    context=context.model_copy(update={'checkpoint':cp})
    generation=SimpleNamespace()
    result=ProductionStages(repo,generation,SimpleNamespace(validate=lambda *_:None)).produce(context)
    assert result.next_stage=='review' and result.checkpoint['resource_specs']==[] and result.checkpoint['artifacts']==[]
    assert result.checkpoint['retained_node_ids']==['tools']


def test_preserving_resources_rejects_expanded_route(ready):
    import pytest
    from app.course_preparation.production_stages import ProductionStages
    from app.course_preparation.adapters.targets import TargetStore
    from app.course_preparation.research_agent import ResearchError
    repo,original,delivery=ready;course=delivery.commit(original).result_ref['course_id']
    request=PreparationRequest(request_id=uuid4(),operation='adjust_course',goal='调整时间，保留原资料',requested_changes=['时长改为20分钟'],target={'course_id':course,'base_manifest_version':1,'base_route_version':1})
    task=repo.submit('alice',request);context=repo.claim('route-only',preparation_id=task['preparation_id'])
    cp=deepcopy(original.checkpoint);cp['plan']['nodes'][0]['objectives']=['未经要求的新目标'];cp['target_snapshot']=TargetStore(repo.engine).read('alice',request.target)
    context=context.model_copy(update={'checkpoint':cp})
    with pytest.raises(ResearchError,match='保留原资料'):
        ProductionStages(repo,SimpleNamespace(),SimpleNamespace(validate=lambda *_:None)).produce(context)
