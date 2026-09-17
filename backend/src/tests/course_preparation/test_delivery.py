from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import select,func,event
from sqlalchemy.orm import Session
from app.database import Base
from app.database.models import PreparedManifestVersion,PreparedCoursePointer,PreparationDeliveryEvent,Material,Course
from app.course_preparation.delivery import DeliveryService
from app.course_preparation.quality import candidate_manifest,check_digest,RULE_VERSION
from app.course_preparation.tool_registry import digest
from app.course_preparation.lifecycle_repository import StaleLease
from tests.course_preparation.test_generation_adapter import generation,submit,spec


@pytest.fixture
def ready(generation):
    repo,ctx,adapter=generation
    Base.metadata.create_all(repo.engine,tables=[Base.metadata.tables[n] for n in (
        'courses','course_memberships','materials','material_versions','artifact_files',
        'prepared_manifest_versions','prepared_course_pointers','preparation_delivery_events')])
    _,receipt=submit(generation); child=adapter.artifacts.claim('alice',receipt['artifact_id'])
    body='## 概念与机制\n工具由服务端执行。\n## 案例与面试表达\n举例。\n## 学习检查\n解释工具执行的职责。'
    artifact={'artifact_type':'report','title':'工具调用','content':body,'generation_state':{'report_review':{'decision':'pass'}}}
    adapter.artifacts.save(child,artifact)
    record=adapter.artifacts.get('alice',receipt['artifact_id'],content=True)
    checkpoint={**ctx.checkpoint,'memory_subject':'alice','memory_refs':{},'memory_view':{'memory_epoch':0},
        'brief':{'audience':'面试者','assumptions':[]},'research_summary':{'findings':[]},
        'plan':{'title':'Agent 面试','nodes':[{'node_key':'tools','title':'工具调用','objectives':['解释工具调用'],
            'prerequisite_keys':[],'minutes':10}]},'node_evidence':{'tools':spec()['evidence']},'artifacts':[record]}
    checkpoint['quality']={'decision':'pass','input_digest':check_digest(checkpoint),'rule_version':RULE_VERSION}
    request=repo.get(owner_user_id='alice',preparation_id=ctx.preparation_id).request
    checkpoint['candidate_manifest']=candidate_manifest(ctx,checkpoint,request).model_dump(mode='json')
    repo.checkpoint(ctx,checkpoint)
    for stage in ('research_scope','plan','research_nodes','produce','review','commit'):
        ctx=repo.transition(ctx,stage,reason='NO_UPLOADS' if stage=='research_scope' else None)
    return repo,ctx,DeliveryService(repo)


def test_manifest_material_pointer_success_and_outbox_commit_together(ready):
    repo,context,delivery=ready
    receipt=delivery.commit(context)
    public=repo.get_public('alice',context.preparation_id)
    assert public['status']=='succeeded' and public['result_ref']==receipt.result_ref
    manifest=delivery.read('alice',receipt.result_ref['course_id'])
    assert manifest['nodes'][0]['node_id']=='tools'
    with Session(repo.engine) as session:
        assert session.scalar(select(func.count()).select_from(PreparedManifestVersion))==1
        assert session.scalar(select(func.count()).select_from(Material))==1
        assert session.scalar(select(func.count()).select_from(PreparationDeliveryEvent))==1
    with pytest.raises(StaleLease): delivery.commit(context)


def test_outbox_insert_failure_rolls_back_every_delivery_fact(ready):
    repo,context,delivery=ready
    def fail(mapper,connection,target): raise RuntimeError('outbox storage failure')
    event.listen(PreparationDeliveryEvent,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError,match='outbox storage'): delivery.commit(context)
    finally: event.remove(PreparationDeliveryEvent,'before_insert',fail)
    assert repo.get_public('alice',context.preparation_id)['status']=='running'
    with Session(repo.engine) as session:
        for model in (PreparedManifestVersion,PreparedCoursePointer,PreparationDeliveryEvent,Material,Course):
            assert session.scalar(select(func.count()).select_from(model))==0


def test_mutated_candidate_cannot_use_old_quality_pass(ready):
    repo,context,delivery=ready
    cp=dict(context.checkpoint); cp['candidate_manifest']={**cp['candidate_manifest'],'goal':'偷换目标'}
    repo.checkpoint(context,cp)
    with pytest.raises(ValueError,match='CANDIDATE_CHANGED'): delivery.commit(context)
    assert repo.get_public('alice',context.preparation_id)['result_ref'] is None


def test_cancel_and_commit_race_has_one_authoritative_outcome(ready):
    repo,context,delivery=ready
    if repo.engine.dialect.name!='postgresql': pytest.skip('PostgreSQL row lock competition')
    barrier=Barrier(2)
    def commit():
        barrier.wait()
        try: return delivery.commit(context)
        except StaleLease: return 'canceled-first'
    def cancel(): barrier.wait(); return repo.cancel('alice',context.preparation_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b=pool.submit(commit),pool.submit(cancel); a.result(); b.result()
    result=repo.get_public('alice',context.preparation_id)
    with Session(repo.engine) as session:
        count=session.scalar(select(func.count()).select_from(PreparedManifestVersion))
    assert (result['status'],count) in [('succeeded',1),('canceled',0)]
    assert (result['result_ref'] is not None)==(result['status']=='succeeded')
