from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from app.database.models import User,CourseMembership,PreparedCoursePointer
from app.course_preparation.publication import PreparedPublication
from app.course_preparation.adapters.targets import TargetStore
from app.course_preparation.schemas import PreparationRequest
from app.self_learning.prepared_courses import PreparedCourses
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation


def test_shared_snapshot_is_readable_without_moving_private_pointer(ready):
    repo,context,delivery=ready
    course=delivery.commit(context).result_ref['course_id']
    with Session(repo.engine) as db,db.begin():
        db.get(User,'alice').role='teacher'
        db.add(CourseMembership(course_id=course,user_id='bob',role='viewer'))
    publisher=PreparedPublication(repo.engine)
    public=publisher.publish('alice',course)
    assert publisher.publish('alice',course)==public
    bridge=PreparedCourses(repo.engine)
    assert bridge.manifest('alice',course)['space']=='personal'
    assert bridge.manifest('bob',course)['space']=='course'
    resource=public['nodes'][0]['resources'][0]
    assert bridge.material('bob',course,resource['resource_type'],resource['resource_id'],resource['version'])['visibility']=='course'
    request=PreparationRequest(request_id=uuid4(),operation='revise_resource',goal='增加个人面试案例',target={'course_id':course,'base_manifest_version':1,'node_id':'tools','resource_id':resource['resource_id'],'base_resource_version':1})
    snapshot=TargetStore(repo.engine).read('bob',request.target)
    assert snapshot['source_owner']=='alice' and snapshot['resource_content']
    with Session(repo.engine) as db:
        assert db.get(PreparedCoursePointer,('alice',course)).version==1
        assert db.get(PreparedCoursePointer,('bob',course)) is None
    with pytest.raises(PermissionError):publisher.publish('bob',course)


def test_personal_revision_of_shared_course_keeps_public_and_old_refs(ready):
    from app.course_preparation.artifact_store import ArtifactStore
    from app.course_preparation.runtime_contracts import BudgetCost
    from app.course_preparation.quality import candidate_manifest,check_digest,RULE_VERSION
    from app.self_learning.contracts import ManifestRef
    repo,first,delivery=ready;course=delivery.commit(first).result_ref['course_id']
    with Session(repo.engine) as db,db.begin():
        db.get(User,'alice').role='teacher';db.add(CourseMembership(course_id=course,user_id='bob',role='viewer'))
    publisher=PreparedPublication(repo.engine);public=publisher.publish('alice',course);old=deepcopy(public)
    resource=public['nodes'][0]['resources'][0]
    request=PreparationRequest(request_id=uuid4(),operation='revise_resource',goal='个人面试案例',target={'course_id':course,'base_manifest_version':1,'node_id':'tools','resource_id':resource['resource_id'],'base_resource_version':1})
    task=repo.submit('bob',request);context=repo.claim('bob-worker',preparation_id=task['preparation_id'])
    cp=deepcopy(first.checkpoint);cp['memory_subject']='bob';cp['memory_refs']={};cp['memory_view']={'memory_epoch':0}
    spec={**cp['artifacts'][0]['spec'],'memory_subject':'bob'}
    action=repo.begin_action(context,'personal-revision','generate_resource',spec,BudgetCost(calls=1))
    store=ArtifactStore(repo);draft=store.create(context,action['action_id'],spec);child=store.claim('bob',draft['artifact_id']);store.save(child,cp['artifacts'][0]['content'])
    cp['artifacts']=[store.get('bob',draft['artifact_id'],content=True)]
    cp['target_snapshot']=TargetStore(repo.engine).read('bob',request.target)
    cp['quality']={'decision':'pass','input_digest':check_digest(cp),'rule_version':RULE_VERSION}
    cp['candidate_manifest']=candidate_manifest(context,cp,request).model_dump(mode='json');repo.checkpoint(context,cp)
    for stage in ('research_scope','plan','research_nodes','produce','review','commit'):
        context=repo.transition(context,stage,reason='NO_UPLOADS' if stage=='research_scope' else None)
    delivery.commit(context)
    bridge=PreparedCourses(repo.engine);personal=bridge.manifest('bob',course)
    assert personal['space']=='personal' and personal['nodes'][0]['resources'][0]['resource_id']!=resource['resource_id']
    assert bridge.manifest('bob',course,ManifestRef(manifest_id=old['manifest_id'],version=1))==old
    with Session(repo.engine) as db:
        assert PreparedPublication.current(db,course).payload==old
        assert db.get(PreparedCoursePointer,('alice',course)).version==1
