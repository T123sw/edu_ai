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
